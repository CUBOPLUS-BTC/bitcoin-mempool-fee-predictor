"""
FastAPI main application
Bitcoin Mempool Fee Prediction API
Provides real-time fee predictions for block inclusion.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from datetime import datetime
import logging
import sys
import os
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion import MempoolDataIngestion
from src.inference import FeeModelInference
from api.security import verify_api_key, SecurityLogger
from api.middleware.security_headers import SecurityHeadersMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
ingestion = None
inference = None
cached_prediction = None
cache_timestamp = None
CACHE_TTL = 60  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    global ingestion, inference

    # Startup
    logger.info(" Starting Mempool Fee Prediction API...")
    ingestion = MempoolDataIngestion()
    inference = FeeModelInference()
    inference.load_all_models()
    logger.info(f" Models loaded: {inference.get_loaded_models_info()}")

    yield

    # Shutdown
    logger.info(" Shutting down Fee Prediction API")


# Create FastAPI app
app = FastAPI(
    title="Bitcoin Mempool Fee Prediction API",
    description="ML-powered fee prediction for Bitcoin block inclusion. "
                "Predicts the optimal fee rate (sats/vByte) needed to get "
                "your transaction confirmed in the next 1, 3, or 6 blocks.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware - restrict to specific origins
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],  # Only GET needed for this API
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    max_age=600,
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "service": "Bitcoin Mempool Fee Prediction API",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "predict": "/fees/predict",
            "current": "/fees/current",
            "health": "/health",
            "models": "/models",
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint"""
    model_info = inference.get_loaded_models_info() if inference else {}
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": model_info.get('total_models', 0),
        "xgb_horizons": model_info.get('xgb_models', []),
        "lgb_horizons": model_info.get('lgb_models', []),
    }


@app.get("/fees/predict", tags=["Fee Prediction"])
@limiter.limit("30/minute")
async def predict_fees(
    request: Request,
    background_tasks: BackgroundTasks,
    use_ensemble: bool = Query(True, description="Use XGBoost + LightGBM ensemble"),
    api_key: str = Depends(verify_api_key),
):
    """
    Predict optimal fee rates for block inclusion.

    Returns predictions for multiple block horizons (1, 3, 6 blocks)
    with confidence intervals and a recommendation.

    No request body needed — fetches live mempool data automatically.
    """
    global cached_prediction, cache_timestamp

    # Check cache
    if (cached_prediction is not None and cache_timestamp is not None
            and (datetime.now() - cache_timestamp).total_seconds() < CACHE_TTL):
        return cached_prediction

    try:
        # Fetch live snapshot
        snapshot = ingestion.fetch_full_snapshot()
        if snapshot is None:
            raise HTTPException(status_code=503, detail="Could not fetch mempool data")

        # Load historical data for features
        snapshots_df = ingestion.load_snapshots()
        if snapshots_df is None or len(snapshots_df) < 10:
            # Minimal: use just the current snapshot
            import pandas as pd
            snapshots_df = pd.DataFrame([snapshot])
        else:
            import pandas as pd
            snapshots_df = pd.concat(
                [snapshots_df, pd.DataFrame([snapshot])],
                ignore_index=True
            )

        # Make predictions
        response = inference.predict_from_snapshot(snapshots_df, use_ensemble=use_ensemble)

        # Cache
        cached_prediction = response
        cache_timestamp = datetime.now()

        # Save snapshot in background
        background_tasks.add_task(ingestion.save_snapshot, snapshot)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        # Don't expose internal error details in production
        error_msg = "Prediction failed" if os.getenv("ENV", "production") == "production" else f"Prediction failed: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/fees/current", tags=["Fee Prediction"])
async def get_current_fees():
    """
    Get current mempool fees from mempool.space (no ML prediction).
    Raw fee data directly from the network.
    """
    try:
        fees = ingestion.fetch_recommended_fees()
        mempool = ingestion.fetch_mempool_state()

        if fees is None:
            raise HTTPException(status_code=503, detail="Could not fetch fee data")

        return {
            "timestamp": datetime.now().isoformat(),
            "fees": {
                "fastest": fees.get('fastestFee', 0),
                "half_hour": fees.get('halfHourFee', 0),
                "hour": fees.get('hourFee', 0),
                "economy": fees.get('economyFee', 0),
                "minimum": fees.get('minimumFee', 0),
            },
            "mempool": {
                "tx_count": mempool.get('count', 0) if mempool else 0,
                "vsize_mb": round(mempool.get('vsize', 0) / 1e6, 1) if mempool else 0,
                "total_fee_btc": round(mempool.get('total_fee', 0) / 1e8, 4) if mempool else 0,
            },
            "source": "mempool.space"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Current fees error: {e}")
        raise HTTPException(status_code=500, detail="Error fetching current fees")


@app.get("/fees/history", tags=["Fee Prediction"])
@limiter.limit("10/minute")
async def get_prediction_history(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    api_key: str = Depends(verify_api_key),
):
    """
    Get history of fee predictions and their validation results.
    """
    try:
        import pandas as pd

        log_file = Path("bitacora_fee_predictions.csv")
        if not log_file.exists():
            return {"predictions": [], "total": 0}

        df = pd.read_csv(log_file)
        df = df.sort_values('timestamp_pred', ascending=False).head(limit)

        records = df.to_dict('records')

        # Statistics
        validated = df[df['status'] == 'VALIDATED']
        stats = {}
        if len(validated) > 0:
            stats['total_validated'] = len(validated)
            stats['block_inclusion_accuracy'] = float(validated['would_confirm'].mean())
            stats['avg_overpay_sat_vb'] = float(validated['overpay_sat_vb'].mean())

        return {
            "predictions": records,
            "total": len(records),
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"History error: {e}")
        # Don't expose internal error details
        error_msg = "Error fetching prediction history" if os.getenv("ENV", "production") == "production" else f"Error fetching prediction history: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/models", tags=["Models"])
@limiter.limit("20/minute")
async def list_models(
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    """List all loaded model information"""
    return inference.get_loaded_models_info() if inference else {"error": "Models not loaded"}


@app.get("/mempool/blocks", tags=["Mempool"])
async def get_mempool_blocks():
    """Get projected mempool blocks with fee ranges"""
    try:
        blocks = ingestion.fetch_mempool_blocks()
        if blocks is None:
            raise HTTPException(status_code=503, detail="Could not fetch mempool blocks")

        return {
            "timestamp": datetime.now().isoformat(),
            "projected_blocks": blocks,
            "n_blocks": len(blocks)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    # Sanitize error messages in production
    detail = exc.detail
    if os.getenv("ENV", "production") == "production":
        # Remove potentially sensitive information from error messages
        sensitive_patterns = ["traceback", "stack", "file", "line", "module"]
        detail_lower = str(detail).lower()
        if any(pattern in detail_lower for pattern in sensitive_patterns):
            detail = "Request failed"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": detail,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    # Never expose exception details in production
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error" if os.getenv("ENV", "production") == "production" else str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    # Security: Never enable reload in production
    is_development = os.getenv("ENV", "production") == "development"
    
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=is_development,
        log_level=os.getenv("LOG_LEVEL", "info")
    )
