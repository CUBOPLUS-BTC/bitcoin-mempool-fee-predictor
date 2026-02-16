"""
Monitoring Service - Logs predictions and tracks metrics
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MonitoringService:
    """Monitors API predictions and model performance"""
    
    def __init__(self, log_file: str = "api_predictions.jsonl"):
        self.log_file = Path(log_file)
        self.metrics_cache = {}
    
    def log_prediction(self, request: dict, response: dict, client_id: str):
        """Log prediction to file"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id,
            "request": {
                "timeframe": request.timeframe,
                "use_volatility_filter": request.use_volatility_filter,
                "model_version": request.model_version
            },
            "response": {
                "predicted_price": response["predicted_price"],
                "current_price": response["current_price"],
                "direction": response["direction"],
                "change_pct": response["change_pct"],
                "confidence": response["confidence"],
                "model_version": response["model_version"],
                "volatility_allowed": response["volatility_allowed"]
            }
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to log prediction: {e}")
    
    def get_metrics(self, timeframe: str = None, days: int = 7) -> dict:
        """
        Calculate metrics from historical data
        
        Args:
            timeframe: Filter by specific timeframe
            days: Number of days to analyze
        
        Returns:
            Dictionary with metrics
        """
        try:
            # Leer del archivo de bitácora principal
            df = pd.read_csv('bitacora_new_models.csv')
            df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'])
            
            # Filtrar por fecha
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['timestamp_pred'] >= cutoff]
            
            # Filtrar por timeframe si se especifica
            if timeframe:
                df = df[df['timeframe'] == timeframe]
            
            # Solo completadas
            df_completed = df[df['status'] == 'COMPLETED'].copy()
            
            if len(df_completed) == 0:
                return self._empty_metrics()
            
            # Calcular métricas
            df_completed['error_pct'] = (
                df_completed['error_abs'] / df_completed['entry_price']
            ) * 100
            
            win_rate = (df_completed['error_pct'] < 2.0).sum() / len(df_completed) * 100
            avg_error_pct = df_completed['error_pct'].mean()
            avg_error_usd = df_completed['error_abs'].mean()
            outliers = (df_completed['error_pct'] > 5.0).sum()
            outliers_rate = (outliers / len(df_completed)) * 100
            
            return {
                "timeframe": timeframe,
                "total_predictions": len(df),
                "completed_predictions": len(df_completed),
                "win_rate": round(win_rate, 2),
                "avg_error_pct": round(avg_error_pct, 2),
                "avg_error_usd": round(avg_error_usd, 2),
                "outliers_count": int(outliers),
                "outliers_rate": round(outliers_rate, 2),
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return self._empty_metrics()
    
    def _empty_metrics(self) -> dict:
        """Return empty metrics structure"""
        return {
            "timeframe": None,
            "total_predictions": 0,
            "completed_predictions": 0,
            "win_rate": 0.0,
            "avg_error_pct": 0.0,
            "avg_error_usd": 0.0,
            "outliers_count": 0,
            "outliers_rate": 0.0,
            "period_days": 7
        }
    
    def save_metrics(self):
        """Save current metrics snapshot"""
        try:
            metrics = self.get_metrics()
            with open('api_metrics_snapshot.json', 'w') as f:
                json.dump(metrics, f, indent=2)
            logger.info("✅ Metrics snapshot saved")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
