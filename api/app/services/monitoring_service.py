"""
Monitoring Service for Fee Prediction API
Tracks prediction accuracy and model performance.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MonitoringService:
    """Monitors fee prediction performance"""

    def __init__(self):
        self.predictions_log = []
        self.metrics_file = Path("logs/api_metrics.json")
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def log_prediction(self, request: dict, response: dict, client_id: str = "anonymous"):
        """Log a prediction for monitoring"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id,
            "fee_predictions": response.get("fee_predictions", {}),
            "recommendation": response.get("recommendation", ""),
            "mempool_state": response.get("mempool_snapshot", {}),
        }
        self.predictions_log.append(entry)

        # Keep last 1000 entries in memory
        if len(self.predictions_log) > 1000:
            self.predictions_log = self.predictions_log[-1000:]

    def get_metrics(self, days: int = 7) -> dict:
        """Get performance metrics"""
        return {
            "total_predictions_logged": len(self.predictions_log),
            "period_days": days,
            "status": "operational"
        }

    def save_metrics(self):
        """Save metrics to disk"""
        try:
            metrics = {
                "saved_at": datetime.now().isoformat(),
                "total_predictions": len(self.predictions_log),
                "recent_predictions": self.predictions_log[-10:]
            }
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
