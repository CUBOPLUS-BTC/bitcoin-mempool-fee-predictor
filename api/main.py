"""
FastAPI main application
Production-ready BTC prediction API with model versioning
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from datetime import datetime
import logging

from app.schemas import PredictionRequest, PredictionResponse, HealthResponse, ModelMetrics
from app.services.prediction_service import PredictionService
from app.services.monitoring_service import MonitoringService
from app.utils.model_manager import ModelManager
from app.utils.rate_limiter import RateLimiter

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar servicios globales
model_manager = ModelManager()
monitoring_service = MonitoringService()
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    # Startup
    logger.info("🚀 Starting BTC Prediction API...")
    model_manager.load_models()
    logger.info(f"✅ Loaded models: {model_manager.get_available_versions()}")
    
    yield
    
    # Shutdown
    logger.info("📊 Saving final metrics...")
    monitoring_service.save_metrics()
    logger.info("👋 Shutting down BTC Prediction API")

# Create FastAPI app
app = FastAPI(
    title="BTC Prediction API",
    description="Production-ready API for Bitcoin price predictions with model versioning and monitoring",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection
def get_prediction_service():
    """Dependency: Prediction service"""
    return PredictionService(model_manager, monitoring_service)

async def check_rate_limit(x_client_id: str = Header(default="anonymous")):
    """Rate limiting"""
    if not rate_limiter.allow_request(x_client_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later."
        )
    return x_client_id

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "BTC Prediction API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": len(model_manager.get_available_versions()),
        "active_model": model_manager.get_active_version()
    }

@app.post("/predict", response_model=PredictionResponse, tags=["Predictions"])
async def predict(
    request: PredictionRequest,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(check_rate_limit),
    prediction_service: PredictionService = Depends(get_prediction_service)
):
    """
    Make BTC price predictions
    
    - **timeframe**: Prediction horizon (30m, 1h, 3h, 6h, 12h)
    - **current_price**: Current BTC price (optional, will fetch if not provided)
    - **use_volatility_filter**: Enable/disable volatility protection (default: true)
    - **model_version**: Specific model version to use (optional, uses active by default)
    """
    try:
        # Hacer predicción
        result = await prediction_service.predict(
            timeframe=request.timeframe,
            current_price=request.current_price,
            use_volatility_filter=request.use_volatility_filter,
            model_version=request.version,  # Fixed: use .version not .model_version
            client_id=client_id
        )
        
        # Log asíncrono en background
        background_tasks.add_task(
            monitoring_service.log_prediction,
            request=request,
            response=result,
            client_id=client_id
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/predict/batch", tags=["Predictions"])
async def predict_batch(
    requests: list[PredictionRequest],
    background_tasks: BackgroundTasks,
    client_id: str = Depends(check_rate_limit),
    prediction_service: PredictionService = Depends(get_prediction_service)
):
    """
    Make multiple predictions at once
    Max 10 predictions per batch
    """
    if len(requests) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 predictions per batch"
        )
    
    results = []
    for req in requests:
        try:
            result = await prediction_service.predict(
                timeframe=req.timeframe,
                current_price=req.current_price,
                use_volatility_filter=req.use_volatility_filter,
                model_version=req.version,  # Fixed: use .version not .model_version
                client_id=client_id
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            results.append({"error": str(e), "timeframe": req.timeframe})
    
    return {"predictions": results}

@app.get("/metrics", response_model=ModelMetrics, tags=["Monitoring"])
async def get_metrics(
    timeframe: str = None,
    days: int = 7
):
    """
    Get model performance metrics
    
    - **timeframe**: Filter by specific timeframe
    - **days**: Number of days to look back (default: 7)
    """
    try:
        metrics = monitoring_service.get_metrics(
            timeframe=timeframe,
            days=days
        )
        return metrics
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail="Error fetching metrics")

@app.get("/models", tags=["Models"])
async def list_models():
    """List all available model versions"""
    return {
        "available_versions": model_manager.get_available_versions(),
        "active_version": model_manager.get_active_version(),
        "candidate_version": model_manager.get_candidate_version()
    }

@app.post("/models/{version}/activate", tags=["Models"])
async def activate_model(
    version: str,
    api_key: str = Header(...)
):
    """
    Activate a specific model version
    Requires API key
    """
    # En producción, validar API key
    if api_key != "your-secret-api-key":  # Cambiar en producción
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        model_manager.set_active_version(version)
        logger.info(f"✅ Activated model version: {version}")
        return {
            "status": "success",
            "active_version": version,
            "message": f"Model {version} is now active"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/ab-test/status", tags=["A/B Testing"])
async def ab_test_status():
    """Get A/B test status"""
    return {
        "enabled": model_manager.ab_test_enabled,
        "active_model": model_manager.get_active_version(),
        "candidate_model": model_manager.get_candidate_version(),
        "traffic_split": model_manager.get_traffic_split()
    }

@app.post("/ab-test/enable", tags=["A/B Testing"])
async def enable_ab_test(
    candidate_version: str,
    traffic_percentage: int = 10,
    api_key: str = Header(...)
):
    """
    Enable A/B testing with candidate model
    
    - **candidate_version**: Version to test
    - **traffic_percentage**: % of traffic to send to candidate (1-50)
    """
    if api_key != "your-secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not 1 <= traffic_percentage <= 50:
        raise HTTPException(
            status_code=400,
            detail="Traffic percentage must be between 1 and 50"
        )
    
    try:
        model_manager.enable_ab_test(candidate_version, traffic_percentage)
        logger.info(f"✅ A/B test enabled: {traffic_percentage}% to {candidate_version}")
        return {
            "status": "success",
            "active": model_manager.get_active_version(),
            "candidate": candidate_version,
            "traffic_split": f"{100-traffic_percentage}% / {traffic_percentage}%"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ab-test/disable", tags=["A/B Testing"])
async def disable_ab_test(api_key: str = Header(...)):
    """Disable A/B testing"""
    if api_key != "your-secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    model_manager.disable_ab_test()
    logger.info("✅ A/B test disabled")
    return {"status": "success", "message": "A/B testing disabled"}

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.now().isoformat()
        }
    )

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Solo en desarrollo
        log_level="info"
    )
