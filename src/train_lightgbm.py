"""
LightGBM Training Module for Mempool Fee Prediction
Secondary model for ensemble with XGBoost.
LightGBM is faster and handles categorical features natively.
"""

import lightgbm as lgb
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import json
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from loguru import logger
from typing import Dict, List, Optional, Tuple


class LightGBMFeeTrainer:
    """
    Trains LightGBM models for Bitcoin mempool fee prediction.
    Used as secondary model in ensemble with XGBoost.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.models_dir = Path(self.config['model']['models_dir'])
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self.metrics = {}

    def _load_config(self, config_path: str) -> dict:
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        horizon: int
    ) -> lgb.LGBMRegressor:
        """Train LightGBM model for a specific block horizon"""
        logger.info(f"Training LightGBM for {horizon}-block horizon...")

        lgb_config = self.config['model'].get('lightgbm', {})

        model = lgb.LGBMRegressor(
            n_estimators=lgb_config.get('n_estimators', 500),
            max_depth=lgb_config.get('max_depth', 8),
            learning_rate=lgb_config.get('learning_rate', 0.03),
            subsample=lgb_config.get('subsample', 0.8),
            colsample_bytree=lgb_config.get('colsample_bytree', 0.7),
            min_child_weight=lgb_config.get('min_child_weight', 5),
            reg_alpha=lgb_config.get('reg_alpha', 0.5),
            reg_lambda=lgb_config.get('reg_lambda', 2.0),
            num_leaves=lgb_config.get('num_leaves', 63),
            random_state=lgb_config.get('random_state', 42),
            verbose=-1,
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(30, verbose=False)],
        )

        logger.info(f"✓ LightGBM trained. Best iteration: {model.best_iteration_}")
        return model

    def evaluate_model(
        self,
        model: lgb.LGBMRegressor,
        X_test: np.ndarray,
        y_test: np.ndarray,
        horizon: int
    ) -> Dict[str, float]:
        """Evaluate with fee-prediction-specific metrics (same as XGBoost trainer)"""
        y_pred = model.predict(X_test)
        y_pred = np.maximum(y_pred, 1.0)

        safe_y = np.where(y_test > 0, y_test, 1)
        overpay = np.maximum(y_pred - y_test, 0)
        underpay = np.maximum(y_test - y_pred, 0)
        relative_error = np.abs(y_pred - y_test) / safe_y

        alpha = self.config['model'].get('asymmetric_loss_alpha', 0.7)

        metrics = {
            'horizon_blocks': horizon,
            'model_type': 'lightgbm',
            'mse': float(mean_squared_error(y_test, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred)),
            'block_inclusion_accuracy': float(np.mean(y_pred >= y_test)),
            'avg_overpay_sat_vb': float(np.mean(overpay)),
            'avg_underpay_sat_vb': float(np.mean(underpay)),
            'within_10pct': float(np.mean(relative_error < 0.10)),
            'within_20pct': float(np.mean(relative_error < 0.20)),
            'within_50pct': float(np.mean(relative_error < 0.50)),
            'asymmetric_loss': float(np.mean(alpha * underpay ** 2 + (1 - alpha) * overpay ** 2)),
            'mape': float(np.mean(relative_error) * 100),
        }

        logger.info(f"LightGBM {horizon}-block: MAE={metrics['mae']:.2f}, "
                     f"Inclusion={metrics['block_inclusion_accuracy']:.2%}")

        return metrics

    def save_model(self, model: lgb.LGBMRegressor, horizon: int, metrics: Dict) -> str:
        """Save LightGBM model to disk"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "lgbm_fee"

        model_filename = f"{prefix}_{horizon}block_{timestamp}.txt"
        model_path = self.models_dir / model_filename
        model.booster_.save_model(str(model_path))

        metrics_path = self.models_dir / f"{prefix}_{horizon}block_{timestamp}_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        # Symlink to latest
        latest_link = self.models_dir / f"{prefix}_{horizon}block_latest.txt"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(model_filename)

        logger.info(f"✓ LightGBM saved to {model_path}")
        return str(model_path)

    def load_model(self, horizon: int) -> Optional[lgb.LGBMRegressor]:
        """Load LightGBM model for a specific horizon"""
        latest_path = self.models_dir / f"lgbm_fee_{horizon}block_latest.txt"

        if not latest_path.exists():
            logger.warning(f"No LightGBM model found for {horizon}-block")
            return None

        model = lgb.Booster(model_file=str(latest_path))
        logger.info(f"✓ Loaded LightGBM for {horizon}-block")
        return model

    def train_single_horizon(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        horizon: int
    ) -> Tuple[lgb.LGBMRegressor, Dict]:
        """Train for a single block horizon"""
        target_col = f'target_{horizon}block_fee'
        if target_col not in df.columns:
            raise ValueError(f"Target {target_col} not found")

        X = df[feature_cols].values
        y = df[target_col].values

        test_size = self.config['model']['test_size']
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, shuffle=False
        )

        model = self.train_model(X_train, y_train, X_test, y_test, horizon)
        metrics = self.evaluate_model(model, X_test, y_test, horizon)
        self.save_model(model, horizon, metrics)

        self.models[horizon] = model
        self.metrics[horizon] = metrics

        return model, metrics

    def train_all_horizons(
        self,
        df: pd.DataFrame,
        feature_cols: List[str]
    ) -> Dict[int, Tuple]:
        """Train LightGBM for all configured horizons"""
        horizons = self.config['model']['horizons']
        results = {}

        for horizon in horizons:
            try:
                model, metrics = self.train_single_horizon(df, feature_cols, horizon)
                results[horizon] = (model, metrics)
            except Exception as e:
                logger.error(f"Failed LightGBM training for {horizon}-block: {e}")

        return results


def main():
    import argparse
    from src.features import FeatureEngineer

    parser = argparse.ArgumentParser(description="Train LightGBM fee prediction models")
    parser.add_argument('--horizon', type=int, default=None)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--input', type=str, default=None)
    parser.add_argument('--config', type=str, default='config/config.yaml')
    args = parser.parse_args()

    logger.add("logs/train_lgbm.log", rotation="1 day", retention="7 days")

    if args.input:
        df = pd.read_parquet(args.input) if args.input.endswith('.parquet') else pd.read_csv(args.input)
    else:
        engineer = FeatureEngineer(config_path=args.config)
        df = engineer.load_latest_processed_data()

    if df is None:
        return 1

    engineer = FeatureEngineer(config_path=args.config)
    feature_cols = engineer.get_feature_columns(df)

    trainer = LightGBMFeeTrainer(config_path=args.config)

    if args.all:
        results = trainer.train_all_horizons(df, feature_cols)
        for h, (_, m) in results.items():
            print(f"  {h}-block: MAE={m['mae']:.2f}, Inclusion={m['block_inclusion_accuracy']:.2%}")
    elif args.horizon:
        _, m = trainer.train_single_horizon(df, feature_cols, args.horizon)
        print(f"  {args.horizon}-block: MAE={m['mae']:.2f}")
    else:
        print("Specify --horizon or --all")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
