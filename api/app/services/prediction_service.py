"""
Prediction Service for Fee Prediction API
Handles the core business logic of making fee predictions.
"""

from datetime import datetime
from typing import Optional
import logging
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ingestion import MempoolDataIngestion
from src.inference import FeeModelInference

logger = logging.getLogger(__name__)


class FeePredictionService:
    """Handles fee prediction logic"""

    def __init__(self):
        self.ingestion = MempoolDataIngestion()
        self.inference = FeeModelInference()
        self.inference.load_all_models()

    async def predict(
        self,
        use_ensemble: bool = True,
    ) -> dict:
        """
        Make fee prediction using live mempool data.

        Returns:
            Fee prediction response dictionary
        """
        # Fetch live snapshot
        snapshot = self.ingestion.fetch_full_snapshot()
        if snapshot is None:
            raise ValueError("Could not fetch mempool data")

        # Load historical snapshots for feature engineering
        snapshots_df = self.ingestion.load_snapshots()
        if snapshots_df is None or len(snapshots_df) < 10:
            snapshots_df = pd.DataFrame([snapshot])
        else:
            snapshots_df = pd.concat(
                [snapshots_df, pd.DataFrame([snapshot])],
                ignore_index=True
            )

        # Make predictions
        response = self.inference.predict_from_snapshot(snapshots_df, use_ensemble=use_ensemble)

        return response

    def get_model_info(self) -> dict:
        """Get information about loaded models"""
        return self.inference.get_loaded_models_info()
