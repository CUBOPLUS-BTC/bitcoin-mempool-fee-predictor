#!/usr/bin/env python3
"""
Automated Fee Model Retraining
Retrains every 1 hour with latest mempool data.
Validates new models against Block Inclusion Accuracy before deploying.

Usage:
    python scripts/retrain_fee_model.py
    python scripts/retrain_fee_model.py --no-validate
    python scripts/retrain_fee_model.py --horizon 1
"""

import sys
from pathlib import Path
import json
import shutil
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion import MempoolDataIngestion
from src.features import FeatureEngineer
from src.train import FeeModelTrainer
from src.train_lightgbm import LightGBMFeeTrainer
import pandas as pd
import numpy as np


class FeeModelRetrainer:
    """Automated retraining pipeline for fee prediction models"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.base_dir = Path(".")
        self.models_dir = self.base_dir / "models"
        self.logs_dir = self.base_dir / "logs"

        for d in [self.models_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Configure logging
        log_file = self.logs_dir / f"retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logger.add(log_file, rotation="10 MB")

        self.horizons = [1, 3, 6]

    def backup_current_models(self):
        """Backup current models before retraining"""
        logger.info(" Backing up current models...")
        backup_dir = self.models_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(exist_ok=True)

        for horizon in self.horizons:
            for pattern in [f"xgb_fee_{horizon}block_latest.json",
                            f"lgbm_fee_{horizon}block_latest.txt"]:
                model_file = self.models_dir / pattern
                if model_file.exists():
                    shutil.copy2(model_file, backup_dir / model_file.name)

        return backup_dir

    def load_training_data(self):
        """Load and prepare training data from collected snapshots"""
        logger.info(" Loading mempool snapshot data...")

        ingestion = MempoolDataIngestion(config_path=self.config_path)

        # Try Parquet first, then JSON snapshots
        df = ingestion.load_snapshots()
        if df is None:
            df = ingestion.load_all_snapshots_from_json()

        if df is None or len(df) == 0:
            raise ValueError("No training data available. Run collector_daemon.py first.")

        logger.info(f"   Loaded {len(df)} snapshots")

        # Check minimum samples
        min_samples = 500
        if len(df) < min_samples:
            logger.warning(f"   Only {len(df)} snapshots (recommended: {min_samples}+)")

        return df

    def prepare_features(self, df):
        """Generate features and targets"""
        logger.info(" Generating features...")

        engineer = FeatureEngineer(config_path=self.config_path)
        df_features = engineer.create_all_features(df)
        df_with_targets = engineer.create_block_horizon_targets(df_features)

        feature_cols = engineer.get_feature_columns(df_with_targets)

        logger.info(f"   {len(feature_cols)} features, {len(df_with_targets)} samples")
        return df_with_targets, feature_cols

    def retrain_all(self, validate: bool = True):
        """Main retraining pipeline"""
        logger.info("=" * 80)
        logger.info(" Starting Fee Model Retraining Pipeline")
        logger.info("=" * 80)

        start_time = datetime.now()

        # 1. Backup
        backup_dir = self.backup_current_models()

        # 2. Load data
        df_raw = self.load_training_data()

        # 3. Prepare features
        df, feature_cols = self.prepare_features(df_raw)

        if len(df) < 5:
            logger.warning(f" Not enough samples after feature engineering ({len(df)}). Retraining skipped.")
            return {}


        # 4. Train XGBoost models
        logger.info("\n Training XGBoost Models...")
        xgb_trainer = FeeModelTrainer(config_path=self.config_path)
        xgb_results = {}

        for horizon in self.horizons:
            try:
                model, metrics = xgb_trainer.train_single_horizon(df, feature_cols, horizon)
                xgb_results[horizon] = metrics
                logger.info(f"    XGB {horizon}-block: MAE={metrics['mae']:.2f}, "
                             f"Inclusion={metrics['block_inclusion_accuracy']:.2%}")
            except Exception as e:
                logger.error(f"    XGB {horizon}-block failed: {e}")

        # 5. Train LightGBM models
        logger.info("\n Training LightGBM Models...")
        lgb_trainer = LightGBMFeeTrainer(config_path=self.config_path)
        lgb_results = {}

        for horizon in self.horizons:
            try:
                model, metrics = lgb_trainer.train_single_horizon(df, feature_cols, horizon)
                lgb_results[horizon] = metrics
                logger.info(f"    LGB {horizon}-block: MAE={metrics['mae']:.2f}, "
                             f"Inclusion={metrics['block_inclusion_accuracy']:.2%}")
            except Exception as e:
                logger.error(f"    LGB {horizon}-block failed: {e}")

        # 6. Validate if requested
        if validate:
            self._validate_and_rollback(xgb_results, lgb_results, backup_dir)

        # 7. Generate Ensemble Predictions CSV
        logger.info("\n Generating Ensemble Predictions CSV...")
        self._generate_ensemble_csv(df, feature_cols, xgb_trainer, lgb_trainer)

        # 8. Summary
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(" Retraining Complete!")
        logger.info(f"  Duration: {duration:.1f}s")
        logger.info("=" * 80)

        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'xgb_results': {f"{h}block": m for h, m in xgb_results.items()},
            'lgb_results': {f"{h}block": m for h, m in lgb_results.items()},
        }

        results_file = self.logs_dir / f"retrain_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        return results

    def _generate_ensemble_csv(self, df, feature_cols, xgb_trainer, lgb_trainer):
        """
        Generate ensemble predictions CSV with XGB, LGB, and ensemble predictions.
        Ensemble uses weighted average: XGB (0.6) + LGB (0.4)
        """
        from sklearn.model_selection import train_test_split

        for horizon in self.horizons:
            target_col = f'target_{horizon}block_fee'
            if target_col not in df.columns:
                logger.warning(f"  Target column {target_col} not found, skipping ensemble CSV")
                continue

            try:
                X = df[feature_cols].values
                y = df[target_col].values

                test_size = 0.2
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, shuffle=False
                )

                # Get predictions from both models
                xgb_model = xgb_trainer.models.get(horizon)
                lgb_model = lgb_trainer.models.get(horizon)

                if xgb_model is None or lgb_model is None:
                    logger.warning(f"  Missing model for {horizon}-block, skipping ensemble CSV")
                    continue

                # Generate predictions
                xgb_pred = xgb_model.predict(X_test)
                lgb_pred = lgb_model.predict(X_test)

                # Floor at 1 sat/vB
                xgb_pred = np.maximum(xgb_pred, 1.0)
                lgb_pred = np.maximum(lgb_pred, 1.0)

                # Calculate ensemble prediction (weighted: XGB 0.6, LGB 0.4)
                ensemble_pred = xgb_pred * 0.6 + lgb_pred * 0.4
                ensemble_pred = np.maximum(ensemble_pred, 1.0)

                # Create DataFrame with all predictions
                test_df = df.iloc[-len(X_test):].copy()
                preds_df = pd.DataFrame({
                    'actual_fee': y_test,
                    'ensemble_fee': ensemble_pred,
                    'ensemble_fee_rounded': np.ceil(ensemble_pred).astype(int),
                    'xgb_fee': xgb_pred,
                    'xgb_fee_rounded': np.ceil(xgb_pred).astype(int),
                    'lgb_fee': lgb_pred,
                    'lgb_fee_rounded': np.ceil(lgb_pred).astype(int),
                    'xgb_weight': 0.6,
                    'lgb_weight': 0.4,
                })

                # Add metadata columns
                if 'timestamp' in test_df.columns:
                    preds_df.insert(0, 'timestamp', test_df['timestamp'].values)
                if 'block_height' in test_df.columns:
                    preds_df.insert(1, 'block_height', test_df['block_height'].values)

                # Add model agreement metric
                spread = np.abs(xgb_pred - lgb_pred)
                mean_pred = (xgb_pred + lgb_pred) / 2
                agreement = np.maximum(0, 1.0 - (spread / (mean_pred + 1e-10)))
                preds_df['model_agreement'] = np.round(agreement, 3)

                # Save to CSV
                preds_filename = f"ensemble_predictions_{horizon}block.csv"
                preds_df.to_csv(self.models_dir / preds_filename, index=False)
                logger.info(f"  ✓ Saved ensemble CSV: {preds_filename} ({len(preds_df)} rows)")

            except Exception as e:
                logger.error(f"  Failed to generate ensemble CSV for {horizon}-block: {e}")

    def _validate_and_rollback(self, xgb_results, lgb_results, backup_dir):
        """Validate new models and rollback if worse"""
        logger.info("\n Validating new models...")

        for horizon in self.horizons:
            # Check XGBoost
            if horizon in xgb_results:
                inclusion = xgb_results[horizon].get('block_inclusion_accuracy', 0)
                if inclusion < 0.7:  # Minimum 70% inclusion
                    logger.warning(f"  XGB {horizon}-block inclusion too low ({inclusion:.2%}). Rolling back.")
                    backup_file = backup_dir / f"xgb_fee_{horizon}block_latest.json"
                    target_file = self.models_dir / f"xgb_fee_{horizon}block_latest.json"
                    if backup_file.exists():
                        shutil.copy2(backup_file, target_file)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Retrain fee prediction models")
    parser.add_argument('--no-validate', action='store_true')
    parser.add_argument('--config', type=str, default='config/config.yaml')
    args = parser.parse_args()

    print("\n FEE MODEL RETRAINING\n")

    try:
        retrainer = FeeModelRetrainer(config_path=args.config)
        results = retrainer.retrain_all(validate=not args.no_validate)

        print("\n" + "=" * 80)
        print(" RETRAINING SUMMARY")
        print("=" * 80)

        for model_type in ['xgb_results', 'lgb_results']:
            model_label = 'XGBoost' if 'xgb' in model_type else 'LightGBM'
            print(f"\n{model_label}:")
            for key, metrics in results.get(model_type, {}).items():
                print(f"  {key}: MAE={metrics['mae']:.2f} sat/vB, "
                      f"Inclusion={metrics['block_inclusion_accuracy']:.2%}, "
                      f"Overpay={metrics['avg_overpay_sat_vb']:.1f}")

        print("\n Done!")

    except Exception as e:
        logger.error(f" Retraining failed: {e}")
        raise


if __name__ == '__main__':
    main()
