"""
Model Training Module for Mempool Fee Prediction
Trains XGBoost models for multi-horizon block fee prediction.
Uses asymmetric loss to penalize under-estimation (user's tx wouldn't confirm).
"""

import xgboost as xgb
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import joblib
import json
from datetime import datetime
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from loguru import logger
from typing import Dict, List, Optional, Tuple


class FeeModelTrainer:
    """
    Trains XGBoost models for Bitcoin mempool fee prediction.
    Supports multi-horizon training (1, 3, 6 blocks).
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize fee model trainer

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.models_dir = Path(self.config['model']['models_dir'])
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.models = {}
        self.metrics = {}

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def prepare_data(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare data for training with time-series aware split

        Args:
            df: DataFrame with features and targets
            feature_cols: List of feature column names
            target_col: Target column name

        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        # Extract features and target
        X = df[feature_cols].values
        y = df[target_col].values

        # Time-based split (NEVER shuffle for time series)
        test_size = self.config['model']['test_size']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            shuffle=False  # Critical for time series
        )

        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

        return X_train, X_test, y_train, y_test

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        horizon: int
    ) -> xgb.XGBRegressor:
        """
        Train XGBoost model for a specific block horizon

        Args:
            X_train: Training features
            y_train: Training targets (fee rates in sats/vB)
            X_test: Test features
            y_test: Test targets
            horizon: Prediction horizon in blocks

        Returns:
            Trained XGBoost model
        """
        logger.info(f"Training model for {horizon}-block horizon...")

        # Get XGBoost parameters from config
        xgb_config = self.config['model']['xgboost']

        # Create model
        model = xgb.XGBRegressor(
            n_estimators=xgb_config['n_estimators'],
            max_depth=xgb_config['max_depth'],
            learning_rate=xgb_config['learning_rate'],
            subsample=xgb_config['subsample'],
            colsample_bytree=xgb_config['colsample_bytree'],
            min_child_weight=xgb_config['min_child_weight'],
            gamma=xgb_config['gamma'],
            reg_alpha=xgb_config['reg_alpha'],
            reg_lambda=xgb_config['reg_lambda'],
            random_state=xgb_config['random_state'],
            tree_method='hist',
            verbosity=1,
            early_stopping_rounds=30,
            # Use absolute error objective (more robust for fee data with outliers)
            objective='reg:squarederror',
        )

        # Check for existing model to continue training
        prefix = self.config['model']['model_prefix']
        latest_path = self.models_dir / f"production/xgb_fee_{horizon}block.json"
        if not latest_path.exists():
            latest_path = self.models_dir / f"{prefix}_{horizon}block_latest.json"

        xgb_args = {}
        if latest_path.exists():
            try:
                # Validate feature count before continuing
                baseline_model = xgb.XGBRegressor()
                baseline_model.load_model(str(latest_path))
                if hasattr(baseline_model, 'n_features_in_') and baseline_model.n_features_in_ != X_train.shape[1]:
                    logger.warning(
                        f"Feature mismatch: baseline={baseline_model.n_features_in_}, new={X_train.shape[1]}. "
                        "Starting training from scratch."
                    )
                else:
                    logger.info(f"Continuing training from baseline: {latest_path.name}")
                    xgb_args['xgb_model'] = str(latest_path)
            except Exception as e:
                logger.warning(f"Could not load baseline model {latest_path.name}: {e}. Training from scratch.")

        # Train with early stopping
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
            **xgb_args
        )

        logger.info(f"✓ Model trained. Best iteration: {model.best_iteration}")

        return model

    def evaluate_model(
        self,
        model: xgb.XGBRegressor,
        X_test: np.ndarray,
        y_test: np.ndarray,
        horizon: int
    ) -> Dict[str, float]:
        """
        Evaluate model with fee-prediction-specific metrics.

        Key metrics:
        - MAE (sats/vB): How far off are we on average
        - Block Inclusion Accuracy: Would the predicted fee get confirmed?
        - Overpay Rate: How much extra would the user pay?
        - Underpay Rate: How much short would the user be?
        - Asymmetric Loss: Penalizes underpaying more than overpaying

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test targets (actual required fees in sats/vB)
            horizon: Prediction horizon in blocks

        Returns:
            Dictionary of metrics
        """
        y_pred = model.predict(X_test)

        # Ensure non-negative predictions
        y_pred = np.maximum(y_pred, 1.0)  # Minimum 1 sat/vB

        # === Standard regression metrics ===
        metrics = {
            'horizon_blocks': horizon,
            'mse': float(mean_squared_error(y_test, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred)),
        }

        # === Fee-specific metrics ===

        # 1. Block Inclusion Accuracy: % of times predicted fee >= actual required fee
        # This is the MOST important metric for users
        metrics['block_inclusion_accuracy'] = float(np.mean(y_pred >= y_test))

        # 2. Overpay: How much extra the user would pay on average (sats/vB)
        overpay = np.maximum(y_pred - y_test, 0)
        metrics['avg_overpay_sat_vb'] = float(np.mean(overpay))
        metrics['median_overpay_sat_vb'] = float(np.median(overpay))

        # 3. Underpay: How much short the user would be (sats/vB)
        underpay = np.maximum(y_test - y_pred, 0)
        metrics['avg_underpay_sat_vb'] = float(np.mean(underpay))

        # 4. Overpay MAPE: % overpay relative to actual fee
        safe_y = np.where(y_test > 0, y_test, 1)
        metrics['overpay_mape'] = float(np.mean(overpay / safe_y) * 100)

        # 5. Within-tolerance accuracy
        relative_error = np.abs(y_pred - y_test) / safe_y
        metrics['within_10pct'] = float(np.mean(relative_error < 0.10))
        metrics['within_20pct'] = float(np.mean(relative_error < 0.20))
        metrics['within_50pct'] = float(np.mean(relative_error < 0.50))

        # 6. Asymmetric loss (penalizes under-estimation more)
        alpha = self.config['model'].get('asymmetric_loss_alpha', 0.7)
        asymmetric_loss = np.mean(
            alpha * underpay ** 2 + (1 - alpha) * overpay ** 2
        )
        metrics['asymmetric_loss'] = float(asymmetric_loss)

        # 7. MAPE
        metrics['mape'] = float(np.mean(np.abs(y_pred - y_test) / safe_y) * 100)

        # Log key metrics
        logger.info(f"Metrics for {horizon}-block horizon:")
        logger.info(f"  MAE: {metrics['mae']:.2f} sats/vB")
        logger.info(f"  RMSE: {metrics['rmse']:.2f} sats/vB")
        logger.info(f"  Block Inclusion Acc: {metrics['block_inclusion_accuracy']:.2%}")
        logger.info(f"  Avg Overpay: {metrics['avg_overpay_sat_vb']:.2f} sats/vB")
        logger.info(f"  Avg Underpay: {metrics['avg_underpay_sat_vb']:.2f} sats/vB")
        logger.info(f"  Within 20%: {metrics['within_20pct']:.2%}")
        logger.info(f"  R²: {metrics['r2']:.4f}")

        return metrics

    def save_model(
        self,
        model: xgb.XGBRegressor,
        horizon: int,
        metrics: Dict[str, float]
    ) -> str:
        """
        Save model and metrics to disk

        Args:
            model: Trained model
            horizon: Prediction horizon in blocks
            metrics: Model metrics

        Returns:
            Path where model was saved
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = self.config['model']['model_prefix']

            # Model filename
            model_filename = f"{prefix}_{horizon}block_{timestamp}.json"
            model_path = self.models_dir / model_filename
            model.save_model(str(model_path))

            # Save metrics
            metrics_filename = f"{prefix}_{horizon}block_{timestamp}_metrics.json"
            metrics_path = self.models_dir / metrics_filename
            with open(metrics_path, 'w') as f:
                json.dump(metrics, f, indent=2)

            # Copy as latest model (avoid symlinks — they break in git/GitHub Actions)
            import shutil
            latest_copy = self.models_dir / f"{prefix}_{horizon}block_latest.json"
            if latest_copy.exists() or latest_copy.is_symlink():
                latest_copy.unlink()
            shutil.copy2(model_path, latest_copy)

            logger.info(f"✓ Model saved to {model_path}")
            logger.info(f"✓ Metrics saved to {metrics_path}")

            return str(model_path)

        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise

    def train_single_horizon(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        horizon: int
    ) -> Tuple[xgb.XGBRegressor, Dict[str, float]]:
        """
        Train model for a single block horizon

        Args:
            df: DataFrame with features and targets
            feature_cols: List of feature columns
            horizon: Prediction horizon in blocks

        Returns:
            Tuple of (model, metrics)
        """
        logger.info(f"{'=' * 80}")
        logger.info(f"Training {horizon}-block fee prediction model")
        logger.info(f"{'=' * 80}")

        # Target column
        target_col = f'target_{horizon}block_fee'

        if target_col not in df.columns:
            raise ValueError(f"Target column {target_col} not found in DataFrame")

        # Prepare data
        X_train, X_test, y_train, y_test = self.prepare_data(df, feature_cols, target_col)

        # Train model
        model = self.train_model(X_train, y_train, X_test, y_test, horizon)

        # Evaluate model
        metrics = self.evaluate_model(model, X_test, y_test, horizon)

        # Output predictions vs actuals to CSV
        y_pred = model.predict(X_test)
        y_pred = np.maximum(y_pred, 1.0)
        
        test_df = df.iloc[-len(X_test):].copy()
        preds_df = pd.DataFrame({
            'actual_fee': y_test,
            'predicted_fee': y_pred
        })
        if 'timestamp' in test_df.columns:
            preds_df.insert(0, 'timestamp', test_df['timestamp'].values)
        if 'block_height' in test_df.columns:
            preds_df.insert(1, 'block_height', test_df['block_height'].values)
            
        preds_filename = f"xgb_predictions_{horizon}block.csv"
        preds_df.to_csv(self.models_dir / preds_filename, index=False)
        logger.info(f"✓ Saved predictions CSV to {preds_filename}")

        # Save model
        self.save_model(model, horizon, metrics)

        # Store in memory
        self.models[horizon] = model
        self.metrics[horizon] = metrics

        return model, metrics

    def train_all_horizons(
        self,
        df: pd.DataFrame,
        feature_cols: List[str]
    ) -> Dict[int, Tuple[xgb.XGBRegressor, Dict[str, float]]]:
        """
        Train models for all configured block horizons

        Args:
            df: DataFrame with features and targets
            feature_cols: List of feature columns

        Returns:
            Dictionary mapping horizon to (model, metrics)
        """
        horizons = self.config['model']['horizons']
        logger.info(f"Training models for {len(horizons)} block horizons: {horizons}")

        results = {}

        for horizon in horizons:
            try:
                model, metrics = self.train_single_horizon(df, feature_cols, horizon)
                results[horizon] = (model, metrics)

            except Exception as e:
                logger.error(f"Failed to train model for {horizon}-block: {e}")
                continue

        # Save summary
        self._save_training_summary(results)

        logger.info("=" * 80)
        logger.info("✓ All models trained successfully!")
        logger.info("=" * 80)

        return results

    def _save_training_summary(self, results: Dict[int, Tuple]) -> None:
        """Save summary of all training results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_path = self.models_dir / f"training_summary_{timestamp}.json"

            summary = {
                'timestamp': timestamp,
                'horizons': {},
                'overall_metrics': {}
            }

            for horizon, (model, metrics) in results.items():
                summary['horizons'][f'{horizon}block'] = metrics

            # Calculate average metrics
            all_metrics = [metrics for _, metrics in results.values()]
            if all_metrics:
                summary['overall_metrics'] = {
                    'avg_mae_sat_vb': float(np.mean([m['mae'] for m in all_metrics])),
                    'avg_rmse_sat_vb': float(np.mean([m['rmse'] for m in all_metrics])),
                    'avg_block_inclusion_acc': float(np.mean([m['block_inclusion_accuracy'] for m in all_metrics])),
                    'avg_overpay_sat_vb': float(np.mean([m['avg_overpay_sat_vb'] for m in all_metrics])),
                    'avg_within_20pct': float(np.mean([m['within_20pct'] for m in all_metrics])),
                    'avg_r2': float(np.mean([m['r2'] for m in all_metrics])),
                }

            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)

            logger.info(f"✓ Training summary saved to {summary_path}")

        except Exception as e:
            logger.error(f"Failed to save training summary: {e}")

    def get_feature_importance(
        self,
        model: xgb.XGBRegressor,
        feature_cols: List[str],
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        Get feature importance for a trained model

        Args:
            model: Trained XGBoost model
            feature_cols: Feature column names
            top_n: Number of top features to return

        Returns:
            DataFrame with feature importances
        """
        importance = model.feature_importances_
        fi_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return fi_df.head(top_n)


def main():
    """CLI entry point for model training"""
    import argparse
    from src.features import FeatureEngineer

    parser = argparse.ArgumentParser(description="Train mempool fee prediction models")
    parser.add_argument('--horizon', type=int, default=None, help='Train specific block horizon (1, 3, or 6)')
    parser.add_argument('--all', action='store_true', help='Train all horizons')
    parser.add_argument('--input', type=str, default=None, help='Input file with features')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='Config file path')

    args = parser.parse_args()

    # Setup logging
    logger.add("logs/train.log", rotation="1 day", retention="7 days")

    # Load data
    if args.input:
        logger.info(f"Loading data from {args.input}")
        if args.input.endswith('.parquet'):
            df = pd.read_parquet(args.input)
        else:
            df = pd.read_csv(args.input)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
    else:
        logger.info("Loading latest processed data")
        engineer = FeatureEngineer(config_path=args.config)
        df = engineer.load_latest_processed_data()

    if df is None:
        logger.error("No data to train on")
        return 1

    # Get feature columns
    engineer = FeatureEngineer(config_path=args.config)
    feature_cols = engineer.get_feature_columns(df)

    logger.info(f"Using {len(feature_cols)} features for training")

    # Initialize trainer
    trainer = FeeModelTrainer(config_path=args.config)

    # Train
    if args.all:
        results = trainer.train_all_horizons(df, feature_cols)
        print(f"✓ Trained {len(results)} models successfully")
        for horizon, (model, metrics) in results.items():
            print(f"  {horizon}-block: MAE={metrics['mae']:.2f} sats/vB, "
                  f"Inclusion={metrics['block_inclusion_accuracy']:.2%}")

    elif args.horizon:
        model, metrics = trainer.train_single_horizon(df, feature_cols, args.horizon)
        print(f"✓ Model for {args.horizon}-block trained successfully")
        print(f"  MAE: {metrics['mae']:.2f} sats/vB")
        print(f"  Block Inclusion Acc: {metrics['block_inclusion_accuracy']:.2%}")
        print(f"  Avg Overpay: {metrics['avg_overpay_sat_vb']:.2f} sats/vB")

    else:
        logger.error("Specify --horizon or --all")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
