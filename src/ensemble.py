"""
Ensemble Module
Combines predictions from multiple models to improve performance
Supports different voting strategies and model weighting
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from loguru import logger
from pathlib import Path


class EnsemblePredictor:
    """
    Ensemble predictor that combines multiple models
    Supports: majority voting, weighted average, confidence-based
    """

    def __init__(self, strategy: str = "weighted"):
        """
        Initialize ensemble predictor

        Args:
            strategy: Ensemble strategy ("majority", "weighted", "confidence")
        """
        self.strategy = strategy
        self.models = {}  # Model name -> model/predictor object
        self.weights = {}  # Model name -> weight

    def add_model(self, name: str, predictor, weight: float = 1.0):
        """
        Add a model to the ensemble

        Args:
            name: Model identifier
            predictor: Model or predictor object (must have predict method)
            weight: Model weight for weighted strategies
        """
        self.models[name] = predictor
        self.weights[name] = weight
        logger.info(f"Added model '{name}' to ensemble with weight {weight}")

    def predict_single(
        self,
        predictions: Dict[str, Dict]
    ) -> Dict:
        """
        Combine predictions from multiple models for a single prediction

        Args:
            predictions: Dictionary mapping model name to prediction dict
                        Each prediction dict should have: predicted_price, signal, confidence

        Returns:
            Combined prediction dictionary
        """
        if len(predictions) == 0:
            logger.warning("No predictions to ensemble")
            return None

        if self.strategy == "majority":
            return self._majority_vote(predictions)
        elif self.strategy == "weighted":
            return self._weighted_average(predictions)
        elif self.strategy == "confidence":
            return self._confidence_weighted(predictions)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def _majority_vote(self, predictions: Dict[str, Dict]) -> Dict:
        """
        Majority voting: Most common signal wins
        """
        signals = [pred['signal'] for pred in predictions.values()]
        signal_counts = pd.Series(signals).value_counts()
        ensemble_signal = signal_counts.index[0]

        # Average price predictions
        predicted_prices = [pred['predicted_price'] for pred in predictions.values()]
        ensemble_price = np.mean(predicted_prices)

        # Calculate confidence as % of models agreeing
        confidence = signal_counts.iloc[0] / len(signals)

        result = {
            'predicted_price': ensemble_price,
            'signal': ensemble_signal,
            'confidence': confidence,
            'strategy': 'majority_vote',
            'n_models': len(predictions),
            'individual_signals': signals
        }

        return result

    def _weighted_average(self, predictions: Dict[str, Dict]) -> Dict:
        """
        Weighted average: Combine predictions using model weights
        """
        total_weight = sum(self.weights[name] for name in predictions.keys())

        # Weighted average of prices
        weighted_price = sum(
            pred['predicted_price'] * self.weights[name]
            for name, pred in predictions.items()
        ) / total_weight

        # Weighted signal (convert to numeric, average, convert back)
        signal_map = {'SELL': -1, 'HOLD': 0, 'BUY': 1}
        reverse_map = {-1: 'SELL', 0: 'HOLD', 1: 'BUY'}

        weighted_signal_value = sum(
            signal_map[pred['signal']] * self.weights[name]
            for name, pred in predictions.items()
        ) / total_weight

        # Round to nearest signal
        if weighted_signal_value > 0.3:
            ensemble_signal = 'BUY'
        elif weighted_signal_value < -0.3:
            ensemble_signal = 'SELL'
        else:
            ensemble_signal = 'HOLD'

        # Weighted average of confidences
        weighted_confidence = sum(
            pred.get('confidence', 1.0) * self.weights[name]
            for name, pred in predictions.items()
        ) / total_weight

        result = {
            'predicted_price': weighted_price,
            'signal': ensemble_signal,
            'confidence': weighted_confidence,
            'strategy': 'weighted_average',
            'n_models': len(predictions),
            'weights_used': {name: self.weights[name] for name in predictions.keys()}
        }

        return result

    def _confidence_weighted(self, predictions: Dict[str, Dict]) -> Dict:
        """
        Confidence-weighted: Weight by individual model confidence
        """
        total_confidence = sum(pred.get('confidence', 1.0) for pred in predictions.values())

        if total_confidence == 0:
            # Fallback to equal weighting
            return self._weighted_average(predictions)

        # Confidence-weighted average of prices
        weighted_price = sum(
            pred['predicted_price'] * pred.get('confidence', 1.0)
            for pred in predictions.values()
        ) / total_confidence

        # Confidence-weighted signal
        signal_map = {'SELL': -1, 'HOLD': 0, 'BUY': 1}

        weighted_signal_value = sum(
            signal_map[pred['signal']] * pred.get('confidence', 1.0)
            for pred in predictions.values()
        ) / total_confidence

        # Round to nearest signal
        if weighted_signal_value > 0.3:
            ensemble_signal = 'BUY'
        elif weighted_signal_value < -0.3:
            ensemble_signal = 'SELL'
        else:
            ensemble_signal = 'HOLD'

        # Use maximum confidence
        max_confidence = max(pred.get('confidence', 1.0) for pred in predictions.values())

        result = {
            'predicted_price': weighted_price,
            'signal': ensemble_signal,
            'confidence': max_confidence,
            'strategy': 'confidence_weighted',
            'n_models': len(predictions),
        }

        return result

    def predict_batch(
        self,
        predictions_df: pd.DataFrame,
        model_col: str = 'model',
        required_cols: List[str] = None
    ) -> pd.DataFrame:
        """
        Ensemble predictions from a DataFrame with multiple model predictions

        Args:
            predictions_df: DataFrame with predictions from multiple models
            model_col: Column name containing model identifier
            required_cols: Required columns in each prediction

        Returns:
            DataFrame with ensemble predictions
        """
        if required_cols is None:
            required_cols = ['predicted_price', 'signal', 'confidence']

        # Group by timestamp (or index)
        if 'timestamp' in predictions_df.columns:
            group_col = 'timestamp'
        else:
            group_col = predictions_df.index.name or 'index'

        ensemble_predictions = []

        for group_id, group_df in predictions_df.groupby(group_col):
            # Convert to dict format
            predictions = {}
            for _, row in group_df.iterrows():
                model_name = row[model_col]
                pred_dict = {col: row[col] for col in required_cols if col in row}
                predictions[model_name] = pred_dict

            # Combine
            ensemble_pred = self.predict_single(predictions)

            if ensemble_pred:
                ensemble_pred[group_col] = group_id
                ensemble_predictions.append(ensemble_pred)

        return pd.DataFrame(ensemble_predictions)


def combine_model_predictions(
    new_model_preds: pd.DataFrame,
    old_model_preds: pd.DataFrame,
    new_weight: float = 0.7,
    old_weight: float = 0.3
) -> pd.DataFrame:
    """
    Combine predictions from new XGBoost model and old model

    Args:
        new_model_preds: Predictions from new model (with directional accuracy)
        old_model_preds: Predictions from old model (with price accuracy)
        new_weight: Weight for new model (default 0.7 because better direction)
        old_weight: Weight for old model (default 0.3 because better MAE)

    Returns:
        DataFrame with ensemble predictions
    """
    logger.info(f"Combining predictions with weights: new={new_weight}, old={old_weight}")

    # Create ensemble
    ensemble = EnsemblePredictor(strategy="weighted")

    # Merge predictions on timestamp
    merged = new_model_preds.merge(
        old_model_preds,
        on='timestamp',
        how='inner',
        suffixes=('_new', '_old')
    )

    logger.info(f"Merged {len(merged)} predictions")

    ensemble_results = []

    for _, row in merged.iterrows():
        predictions = {
            'new_model': {
                'predicted_price': row['predicted_price_new'],
                'signal': row['signal_new'],
                'confidence': row.get('confidence_new', 1.0)
            },
            'old_model': {
                'predicted_price': row['predicted_price_old'],
                'signal': row['signal_old'],
                'confidence': row.get('confidence_old', 1.0)
            }
        }

        # Set weights
        ensemble.weights = {'new_model': new_weight, 'old_model': old_weight}

        # Combine
        ensemble_pred = ensemble.predict_single(predictions)

        if ensemble_pred:
            ensemble_pred['timestamp'] = row['timestamp']
            ensemble_pred['current_price'] = row.get('current_price_new', row.get('current_price_old'))
            ensemble_results.append(ensemble_pred)

    ensemble_df = pd.DataFrame(ensemble_results)

    logger.info(f"✓ Created {len(ensemble_df)} ensemble predictions")

    return ensemble_df


def main():
    """CLI entry point for ensemble predictions"""
    import argparse

    parser = argparse.ArgumentParser(description="Ensemble model predictions")
    parser.add_argument('--new-preds', type=str, required=True, help='New model predictions CSV')
    parser.add_argument('--old-preds', type=str, required=True, help='Old model predictions CSV')
    parser.add_argument('--new-weight', type=float, default=0.7, help='Weight for new model')
    parser.add_argument('--old-weight', type=float, default=0.3, help='Weight for old model')
    parser.add_argument('--output', type=str, default='ensemble_predictions.csv', help='Output file')

    args = parser.parse_args()

    # Load predictions
    new_preds = pd.read_csv(args.new_preds)
    new_preds['timestamp'] = pd.to_datetime(new_preds['timestamp'])

    old_preds = pd.read_csv(args.old_preds)
    old_preds['timestamp'] = pd.to_datetime(old_preds['timestamp'])

    # Combine
    ensemble_preds = combine_model_predictions(
        new_preds,
        old_preds,
        new_weight=args.new_weight,
        old_weight=args.old_weight
    )

    # Save
    ensemble_preds.to_csv(args.output, index=False)
    logger.info(f"✓ Ensemble predictions saved to {args.output}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
