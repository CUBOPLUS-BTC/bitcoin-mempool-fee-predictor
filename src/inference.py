"""
Inference Module for Mempool Fee Prediction
Loads trained models and makes fee predictions for block inclusion.
Replaces the previous price prediction inference.
"""

import xgboost as xgb
import lightgbm as lgb
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
from loguru import logger
from typing import Dict, List, Optional
from datetime import datetime


class FeeModelInference:
    """
    Handles model loading and fee prediction.
    Caches models in memory for fast inference.
    Supports both XGBoost and LightGBM models.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.models_dir = Path(self.config['model']['models_dir'])
        self.xgb_models = {}
        self.lgb_models = {}
        self.model_timestamps = {}

    def _load_config(self, config_path: str) -> dict:
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def load_xgb_model(self, horizon: int, force_reload: bool = False) -> Optional[xgb.XGBRegressor]:
        """Load XGBoost model for a specific block horizon"""
        if horizon in self.xgb_models and not force_reload:
            return self.xgb_models[horizon]

        try:
            latest_path = self.models_dir / f"production/xgb_fee_{horizon}block.json"

            if not latest_path.exists():
                latest_path = self.models_dir / f"production/best_fee_{horizon}block.json"
                if not latest_path.exists():
                    logger.error(f"No XGBoost model found for {horizon}-block in production")
                    return None

            model = xgb.XGBRegressor()
            model.load_model(str(latest_path))
            self.xgb_models[horizon] = model
            self.model_timestamps[f'xgb_{horizon}'] = datetime.now()

            logger.info(f"✓ Loaded XGBoost for {horizon}-block from {latest_path.name}")
            return model

        except Exception as e:
            logger.error(f"Failed to load XGBoost for {horizon}-block: {e}")
            return None

    def load_lgb_model(self, horizon: int, force_reload: bool = False) -> Optional[lgb.Booster]:
        """Load LightGBM model for a specific block horizon"""
        if horizon in self.lgb_models and not force_reload:
            return self.lgb_models[horizon]

        try:
            latest_path = self.models_dir / f"production/lgbm_fee_{horizon}block.txt"

            if not latest_path.exists():
                logger.debug(f"No LightGBM model for {horizon}-block in production")
                return None

            model = lgb.Booster(model_file=str(latest_path))
            self.lgb_models[horizon] = model
            self.model_timestamps[f'lgb_{horizon}'] = datetime.now()

            logger.info(f"✓ Loaded LightGBM for {horizon}-block")
            return model

        except Exception as e:
            logger.error(f"Failed to load LightGBM for {horizon}-block: {e}")
            return None

    def load_all_models(self) -> Dict:
        """Load all configured models (XGBoost + LightGBM)"""
        horizons = self.config['model']['horizons']
        loaded = {'xgb': {}, 'lgb': {}}

        for horizon in horizons:
            xgb_model = self.load_xgb_model(horizon)
            if xgb_model:
                loaded['xgb'][horizon] = xgb_model

            lgb_model = self.load_lgb_model(horizon)
            if lgb_model:
                loaded['lgb'][horizon] = lgb_model

        total = len(loaded['xgb']) + len(loaded['lgb'])
        logger.info(f"✓ Loaded {total} models ({len(loaded['xgb'])} XGB + {len(loaded['lgb'])} LGB)")
        return loaded

    def predict_single_horizon(
        self,
        features: pd.DataFrame,
        horizon: int,
        use_ensemble: bool = True
    ) -> Optional[Dict]:
        """
        Make fee prediction for a single block horizon.

        Args:
            features: DataFrame with feature columns (single row)
            horizon: Block horizon (1, 3, or 6)
            use_ensemble: Whether to combine XGBoost + LightGBM predictions

        Returns:
            Prediction result dictionary
        """
        try:
            feature_cols = [col for col in features.columns
                           if col not in ['timestamp', 'timestamp_unix']]
            X = features[feature_cols].values

            predictions = []

            # XGBoost prediction
            xgb_model = self.load_xgb_model(horizon)
            if xgb_model:
                xgb_pred = float(xgb_model.predict(X)[0])
                xgb_pred = max(xgb_pred, 1.0)  # Floor at 1 sat/vB
                predictions.append(('xgb', xgb_pred))

            # LightGBM prediction
            if use_ensemble:
                lgb_model = self.load_lgb_model(horizon)
                if lgb_model:
                    lgb_pred = float(lgb_model.predict(X)[0])
                    lgb_pred = max(lgb_pred, 1.0)
                    predictions.append(('lgb', lgb_pred))

            if not predictions:
                logger.error(f"No models available for {horizon}-block")
                return None

            # Combine predictions (weighted average, slight bias toward conservative/higher)
            if len(predictions) > 1:
                # XGBoost weight: 0.6, LightGBM weight: 0.4
                xgb_pred = next(p for name, p in predictions if name == 'xgb')
                lgb_pred = next(p for name, p in predictions if name == 'lgb')
                predicted_fee = xgb_pred * 0.6 + lgb_pred * 0.4
            else:
                predicted_fee = predictions[0][1]

            # Round to integer sats/vB (practical for Bitcoin transactions)
            predicted_fee_rounded = max(1, int(np.ceil(predicted_fee)))

            # Calculate confidence interval (simple approach: ±15% for 1-block, wider for longer)
            margin_pct = 0.15 * horizon  # 15% for 1-block, 45% for 3-block, 90% for 6-block
            margin_pct = min(margin_pct, 0.5)  # Cap at 50%
            ci_low = max(1, int(predicted_fee * (1 - margin_pct * 0.5)))
            ci_high = int(predicted_fee * (1 + margin_pct))

            # Assign priority label
            priority_map = {1: "high", 3: "medium", 6: "low"}
            priority = priority_map.get(horizon, "medium")

            # Confidence score (based on model agreement if ensemble)
            if len(predictions) > 1:
                preds_vals = [p for _, p in predictions]
                spread = max(preds_vals) - min(preds_vals)
                mean_pred = np.mean(preds_vals)
                confidence = max(0.5, 1.0 - (spread / (mean_pred + 1e-10)))
            else:
                confidence = 0.75  # Default for single model

            result = {
                'horizon_blocks': horizon,
                'predicted_fee_sat_vb': predicted_fee_rounded,
                'predicted_fee_exact': round(predicted_fee, 2),
                'confidence_interval': [ci_low, ci_high],
                'confidence_score': round(confidence, 3),
                'priority': priority,
                'models_used': [name for name, _ in predictions],
                'individual_predictions': {name: round(p, 2) for name, p in predictions},
                'timestamp': datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"Prediction failed for {horizon}-block: {e}")
            return None

    def predict_all_horizons(
        self,
        features: pd.DataFrame,
        use_ensemble: bool = True
    ) -> Dict[int, Dict]:
        """Make predictions for all configured block horizons"""
        horizons = self.config['model']['horizons']
        predictions = {}

        for horizon in horizons:
            result = self.predict_single_horizon(features, horizon, use_ensemble)
            if result is not None:
                predictions[horizon] = result

        return predictions

    def predict_from_snapshot(
        self,
        snapshot_df: pd.DataFrame,
        use_ensemble: bool = True
    ) -> Dict:
        """
        End-to-end prediction from raw mempool snapshot.

        Args:
            snapshot_df: DataFrame with raw snapshot data

        Returns:
            Full prediction response with mempool context
        """
        from src.features import FeatureEngineer

        # Create features (do not drop NaNs for inference with sparse history)
        engineer = FeatureEngineer()
        df_features = engineer.create_all_features(snapshot_df, drop_nans=False)

        # Get feature columns
        feature_cols = engineer.get_feature_columns(df_features)

        # Use last row (most recent snapshot)
        features = df_features[feature_cols].iloc[[-1]]

        # Make predictions
        fee_predictions = self.predict_all_horizons(features, use_ensemble)

        # Build response
        latest = snapshot_df.iloc[-1]

        # Determine overall recommendation
        recommendation = self._get_recommendation(fee_predictions, latest)

        response = {
            'timestamp': datetime.now().isoformat(),
            'mempool_snapshot': {
                'tx_count': int(latest.get('mempool_tx_count', 0)),
                'vsize_mb': round(latest.get('mempool_vsize', 0) / 1e6, 1),
                'total_fee_btc': round(latest.get('mempool_total_fee', 0) / 1e8, 4),
                'blocks_last_hour': int(latest.get('blocks_last_hour', 0)),
                'time_since_last_block_sec': int(latest.get('time_since_last_block', 0)),
            },
            'current_fees': {
                'fastest': int(latest.get('fee_fastest', 0)),
                'half_hour': int(latest.get('fee_half_hour', 0)),
                'hour': int(latest.get('fee_hour', 0)),
                'economy': int(latest.get('fee_economy', 0)),
                'minimum': int(latest.get('fee_minimum', 0)),
            },
            'fee_predictions': {
                f'{h}_block{"s" if h > 1 else ""}': pred
                for h, pred in fee_predictions.items()
            },
            'recommendation': recommendation,
        }

        return response

    def _get_recommendation(self, predictions: Dict, snapshot) -> str:
        """
        Generate an overall recommendation based on mempool state.

        Returns:
            One of: URGENT, NORMAL, LOW, WAIT
        """
        if not predictions:
            return "UNKNOWN"

        fee_fastest = snapshot.get('fee_fastest', 0)

        # If fees are very high, recommend waiting
        if fee_fastest > 100:
            return "WAIT"
        elif fee_fastest > 50:
            return "URGENT"
        elif fee_fastest > 15:
            return "NORMAL"
        else:
            return "LOW"

    def get_loaded_models_info(self) -> Dict:
        """Get information about loaded models"""
        return {
            'xgb_models': list(self.xgb_models.keys()),
            'lgb_models': list(self.lgb_models.keys()),
            'total_models': len(self.xgb_models) + len(self.lgb_models),
            'load_timestamps': {
                k: v.isoformat() for k, v in self.model_timestamps.items()
            }
        }


def main():
    """CLI entry point for inference"""
    import argparse
    from src.ingestion import MempoolDataIngestion

    parser = argparse.ArgumentParser(description="Make mempool fee predictions")
    parser.add_argument('--horizon', type=int, default=None, help='Predict specific block horizon')
    parser.add_argument('--all', action='store_true', help='Predict all horizons')
    parser.add_argument('--live', action='store_true', help='Fetch live mempool data')
    parser.add_argument('--config', type=str, default='config/config.yaml')

    args = parser.parse_args()

    logger.add("logs/inference.log", rotation="1 day", retention="7 days")

    inference = FeeModelInference(config_path=args.config)

    if args.live:
        # Fetch live data
        ingestion = MempoolDataIngestion(config_path=args.config)
        snapshot = ingestion.fetch_full_snapshot()
        if snapshot is None:
            print("✗ Failed to fetch live mempool data")
            return 1

        # Need some historical data for feature engineering
        df = ingestion.load_snapshots()
        if df is None or len(df) < 30:
            print("✗ Not enough historical snapshots for feature engineering")
            print("  Run the collector daemon first to gather data.")
            return 1

        # Append live snapshot
        snapshot_row = pd.DataFrame([snapshot])
        df = pd.concat([df, snapshot_row], ignore_index=True)

        # Make predictions
        response = inference.predict_from_snapshot(df)

        print("\n" + "=" * 80)
        print(" BITCOIN MEMPOOL FEE PREDICTIONS")
        print("=" * 80)

        ms = response['mempool_snapshot']
        print(f"\n Mempool State:")
        print(f"  Transactions: {ms['tx_count']:,}")
        print(f"  Size: {ms['vsize_mb']:.1f} MvB")
        print(f"  Blocks/hour: {ms['blocks_last_hour']}")

        cf = response['current_fees']
        print(f"\n Current Fees (mempool.space):")
        print(f"  Fastest: {cf['fastest']} sat/vB")
        print(f"  Half-hour: {cf['half_hour']} sat/vB")
        print(f"  Hour: {cf['hour']} sat/vB")
        print(f"  Economy: {cf['economy']} sat/vB")

        print(f"\n ML Predictions:")
        for label, pred in response['fee_predictions'].items():
            print(f"  {label}: {pred['predicted_fee_sat_vb']} sat/vB "
                  f"[{pred['confidence_interval'][0]}-{pred['confidence_interval'][1]}] "
                  f"({pred['priority']})")

        print(f"\n Recommendation: {response['recommendation']}")
        print("=" * 80)

    else:
        print("Specify --live to fetch and predict, or --help for options")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
