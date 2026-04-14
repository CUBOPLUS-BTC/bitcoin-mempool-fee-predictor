"""
Ensemble Module for Mempool Fee Prediction
Combines predictions from XGBoost and LightGBM models.
Uses conservative bias to ensure block inclusion (slightly prefer over-estimation).
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from loguru import logger


class FeeEnsemblePredictor:
    """
    Ensemble predictor for mempool fee predictions.
    Combines multiple model predictions with a conservative bias
    to maximize block inclusion probability.
    """

    def __init__(self, strategy: str = "weighted_conservative"):
        """
        Args:
            strategy: Ensemble strategy
                - "weighted": Simple weighted average
                - "weighted_conservative": Weighted average with upward bias
                - "max_safe": Always predict the higher fee (safest for user)
        """
        self.strategy = strategy
        self.weights = {}

    def set_weights(self, weights: Dict[str, float]):
        """Set model weights for ensemble"""
        self.weights = weights

    def combine_predictions(
        self,
        predictions: Dict[str, float],
        strategy: Optional[str] = None
    ) -> Dict:
        """
        Combine fee predictions from multiple models.

        Args:
            predictions: Dict mapping model_name -> predicted_fee (sats/vB)
            strategy: Override ensemble strategy

        Returns:
            Dict with ensemble prediction and metadata
        """
        strategy = strategy or self.strategy

        if not predictions:
            return None

        pred_values = list(predictions.values())
        pred_names = list(predictions.keys())

        if strategy == "weighted":
            return self._weighted_average(predictions)
        elif strategy == "weighted_conservative":
            return self._weighted_conservative(predictions)
        elif strategy == "max_safe":
            return self._max_safe(predictions)
        else:
            return self._weighted_average(predictions)

    def _weighted_average(self, predictions: Dict[str, float]) -> Dict:
        """Simple weighted average of predictions"""
        total_weight = 0
        weighted_sum = 0

        for name, pred in predictions.items():
            w = self.weights.get(name, 1.0)
            weighted_sum += pred * w
            total_weight += w

        ensemble_fee = weighted_sum / total_weight if total_weight > 0 else np.mean(list(predictions.values()))

        return {
            'ensemble_fee': round(ensemble_fee, 2),
            'ensemble_fee_rounded': max(1, int(np.ceil(ensemble_fee))),
            'strategy': 'weighted',
            'individual': predictions,
            'agreement': self._calc_agreement(predictions),
        }

    def _weighted_conservative(self, predictions: Dict[str, float]) -> Dict:
        """
        Weighted average with conservative (upward) bias.
        Adds a small safety margin to reduce under-estimation risk.
        """
        result = self._weighted_average(predictions)
        base_fee = result['ensemble_fee']

        # Add 5-10% safety margin based on disagreement
        agreement = result['agreement']
        safety_margin = 0.05 + (1 - agreement) * 0.10  # 5-15% margin
        conservative_fee = base_fee * (1 + safety_margin)

        result['ensemble_fee'] = round(conservative_fee, 2)
        result['ensemble_fee_rounded'] = max(1, int(np.ceil(conservative_fee)))
        result['strategy'] = 'weighted_conservative'
        result['safety_margin_pct'] = round(safety_margin * 100, 1)

        return result

    def _max_safe(self, predictions: Dict[str, float]) -> Dict:
        """Use the highest prediction (safest for user, but most expensive)"""
        max_fee = max(predictions.values())

        return {
            'ensemble_fee': round(max_fee, 2),
            'ensemble_fee_rounded': max(1, int(np.ceil(max_fee))),
            'strategy': 'max_safe',
            'individual': predictions,
            'agreement': self._calc_agreement(predictions),
        }

    def _calc_agreement(self, predictions: Dict[str, float]) -> float:
        """
        Calculate agreement score between models (0-1).
        1.0 = perfect agreement, 0.0 = high disagreement.
        """
        if len(predictions) < 2:
            return 1.0

        values = list(predictions.values())
        mean_val = np.mean(values)
        if mean_val == 0:
            return 1.0

        spread = max(values) - min(values)
        agreement = max(0, 1.0 - (spread / mean_val))

        return round(agreement, 3)

    def combine_multi_horizon(
        self,
        horizon_predictions: Dict[int, Dict[str, float]]
    ) -> Dict[int, Dict]:
        """
        Combine predictions for multiple horizons.

        Args:
            horizon_predictions: Dict mapping horizon -> {model_name: predicted_fee}

        Returns:
            Dict mapping horizon -> ensemble result
        """
        results = {}
        for horizon, preds in horizon_predictions.items():
            result = self.combine_predictions(preds)
            if result:
                result['horizon_blocks'] = horizon
                results[horizon] = result

        return results


def main():
    """Demo of ensemble prediction"""
    ensemble = FeeEnsemblePredictor(strategy="weighted_conservative")
    ensemble.set_weights({"xgb": 0.6, "lgb": 0.4})

    # Example predictions
    predictions = {
        "xgb": 42.5,
        "lgb": 38.2,
    }

    result = ensemble.combine_predictions(predictions)
    print(f"Ensemble fee: {result['ensemble_fee_rounded']} sat/vB")
    print(f"Strategy: {result['strategy']}")
    print(f"Agreement: {result['agreement']}")
    print(f"Individual: {result['individual']}")


if __name__ == "__main__":
    main()
