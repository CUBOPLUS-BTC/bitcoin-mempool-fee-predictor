"""
Auto-Retraining Script for Fee Prediction Models
Complete pipeline: fetch data → features → train → validate → deploy
Designed to run on a schedule (every 1 hour via cron or systemd timer).

Usage:
    python scripts/auto_retrain.py
    python scripts/auto_retrain.py --no-validate
"""

import sys
from pathlib import Path
import json
from datetime import datetime
import shutil
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))

from src.ingestion import MempoolDataIngestion
from src.features import FeatureEngineer
from src.train import FeeModelTrainer
from src.train_lightgbm import LightGBMFeeTrainer
import pandas as pd
import numpy as np


class AutoRetrainer:
    """Automated model retraining with validation and rollback"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.models_dir = self.base_dir / "models"
        self.logs_dir = self.base_dir / "logs"

        for directory in [self.models_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        log_file = self.logs_dir / f"auto_retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logger.add(log_file, rotation="10 MB")

        self.horizons = [1, 3, 6]  # Block horizons

    def backup_current_models(self):
        """Backup current models before retraining"""
        logger.info("📦 Backing up current models...")
        backup_dir = self.models_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(exist_ok=True)

        patterns = []
        for horizon in self.horizons:
            patterns.extend([
                f"xgb_fee_{horizon}block_latest.json",
                f"lgbm_fee_{horizon}block_latest.txt",
            ])

        for pattern in patterns:
            model_file = self.models_dir / pattern
            if model_file.exists():
                shutil.copy2(model_file, backup_dir / model_file.name)
                logger.info(f"   Backed up {model_file.name}")

        return backup_dir

    def fetch_latest_data(self):
        """Ensure we have the latest snapshot data"""
        logger.info("📊 Loading snapshot data...")

        ingestion = MempoolDataIngestion()

        # Consolidate JSON snapshots to Parquet
        df = ingestion.load_all_snapshots_from_json()

        if df is not None and len(df) > 0:
            # Save consolidated Parquet for faster future loads
            ingestion.save_snapshots_batch(df.to_dict('records'),
                                            filename="mempool_consolidated.parquet")
            logger.info(f"   Loaded {len(df)} snapshots")
            return df

        # Try existing Parquet
        df = ingestion.load_snapshots()
        if df is not None:
            logger.info(f"   Loaded {len(df)} snapshots from Parquet")
            return df

        raise ValueError("No snapshot data available")

    def prepare_features(self, df):
        """Generate features for training"""
        logger.info("🔧 Generating features...")

        fe = FeatureEngineer()
        df_features = fe.create_all_features(df)
        df_targets = fe.create_block_horizon_targets(df_features)
        feature_cols = fe.get_feature_columns(df_targets)

        logger.info(f"   {len(feature_cols)} features, {len(df_targets)} samples")
        return df_targets, feature_cols

    def train_and_validate(self, df, feature_cols, horizon, backup_dir):
        """Train both models for one horizon and validate"""
        results = {'horizon': horizon, 'xgb': None, 'lgb': None, 'status': 'unknown'}

        # Train XGBoost
        try:
            xgb_trainer = FeeModelTrainer()
            xgb_model, xgb_metrics = xgb_trainer.train_single_horizon(df, feature_cols, horizon)
            results['xgb'] = xgb_metrics
            logger.info(f"✅ XGB {horizon}-block: Inclusion={xgb_metrics['block_inclusion_accuracy']:.2%}")
        except Exception as e:
            logger.error(f"❌ XGB {horizon}-block failed: {e}")

        # Train LightGBM
        try:
            lgb_trainer = LightGBMFeeTrainer()
            lgb_model, lgb_metrics = lgb_trainer.train_single_horizon(df, feature_cols, horizon)
            results['lgb'] = lgb_metrics
            logger.info(f"✅ LGB {horizon}-block: Inclusion={lgb_metrics['block_inclusion_accuracy']:.2%}")
        except Exception as e:
            logger.error(f"❌ LGB {horizon}-block failed: {e}")

        # Validate: check if new models meet minimum quality
        min_inclusion = 0.70
        xgb_ok = results['xgb'] and results['xgb']['block_inclusion_accuracy'] >= min_inclusion
        lgb_ok = results['lgb'] and results['lgb']['block_inclusion_accuracy'] >= min_inclusion

        if xgb_ok or lgb_ok:
            results['status'] = 'updated'
        else:
            results['status'] = 'rolled_back'
            logger.warning(f"⚠️  Both models below {min_inclusion:.0%} inclusion. Rolling back {horizon}-block.")

            # Rollback
            for pattern in [f"xgb_fee_{horizon}block_latest.json",
                            f"lgbm_fee_{horizon}block_latest.txt"]:
                backup_file = backup_dir / pattern
                target_file = self.models_dir / pattern
                if backup_file.exists():
                    shutil.copy2(backup_file, target_file)

        return results

    def retrain_all_models(self, validate: bool = True):
        """Main retraining pipeline"""
        logger.info("=" * 80)
        logger.info("🔄 Starting Auto-Retraining Pipeline")
        logger.info("=" * 80)

        start_time = datetime.now()

        # 1. Backup
        backup_dir = self.backup_current_models()

        # 2. Fetch data
        df_raw = self.fetch_latest_data()

        # 3. Features
        df, feature_cols = self.prepare_features(df_raw)

        # 4. Train all horizons
        all_results = {}
        for horizon in self.horizons:
            logger.info("-" * 80)
            result = self.train_and_validate(df, feature_cols, horizon, backup_dir)
            all_results[f"{horizon}block"] = result

        # 5. Summary
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"✅ Auto-Retraining Complete! ({duration:.1f}s)")
        logger.info("=" * 80)

        # Save results
        results_file = self.logs_dir / f"retrain_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)

        return all_results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Auto-retrain fee prediction models")
    parser.add_argument("--no-validate", action="store_true")
    parser.add_argument("--dir", default=".", help="Base directory")

    args = parser.parse_args()

    try:
        retrainer = AutoRetrainer(base_dir=args.dir)
        results = retrainer.retrain_all_models(validate=not args.no_validate)

        print("\n" + "=" * 80)
        print("📊 RETRAINING SUMMARY")
        print("=" * 80)

        for key, result in results.items():
            status = result['status']
            print(f"\n{key}:")
            print(f"  Status: {'✅' if status == 'updated' else '⚠️'} {status}")

            if result.get('xgb'):
                m = result['xgb']
                print(f"  XGBoost: MAE={m['mae']:.2f}, Inclusion={m['block_inclusion_accuracy']:.2%}")
            if result.get('lgb'):
                m = result['lgb']
                print(f"  LightGBM: MAE={m['mae']:.2f}, Inclusion={m['block_inclusion_accuracy']:.2%}")

        print("\n✅ Pipeline completed!")

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()
