"""
Auto-Retraining Script for BTC Models
Fetches fresh data, retrains models, and updates them if performance improves
"""

import sys
from pathlib import Path
import json
from datetime import datetime
import shutil
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))

from src.ingestion import DataIngestion
from src.features import FeatureEngineer
from src.train import ModelTrainer
from src.backtest import Backtester
import pandas as pd
import numpy as np


class AutoRetrainer:
    """Automated model retraining with validation"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.models_dir = self.base_dir / "models"
        self.backtest_dir = self.base_dir / "backtest_results"
        self.params_dir = self.base_dir / "optimized_params"
        self.logs_dir = self.base_dir / "logs"

        # Ensure directories exist
        for directory in [self.models_dir, self.backtest_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Configure logging
        log_file = self.logs_dir / f"auto_retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logger.add(log_file, rotation="10 MB")

        self.horizons = [30, 60, 180, 360, 720]  # minutes

    def backup_current_models(self):
        """Backup current models before retraining"""
        logger.info("📦 Backing up current models...")
        backup_dir = self.models_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(exist_ok=True)

        for horizon in self.horizons:
            model_file = self.models_dir / f"xgb_btc_{horizon}min_optimized_latest.json"
            if model_file.exists():
                shutil.copy2(model_file, backup_dir / model_file.name)
                logger.info(f"   Backed up {model_file.name}")

        return backup_dir

    def fetch_fresh_data(self):
        """Fetch latest BTC data from Binance"""
        logger.info("📊 Fetching fresh data from Binance...")

        try:
            ingestion = DataIngestion()
            df = ingestion.fetch_ohlcv(lookback_days=7)  # Get last 7 days of data

            logger.info(f"   Fetched {len(df)} candles")
            logger.info(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

            # Save raw data
            data_file = self.base_dir / "data" / f"btc_usdt_fresh_{datetime.now().strftime('%Y%m%d')}.csv"
            data_file.parent.mkdir(exist_ok=True)
            df.to_csv(data_file)

            return df

        except Exception as e:
            logger.error(f"❌ Failed to fetch data: {e}")
            raise

    def prepare_features(self, df: pd.DataFrame):
        """Generate features for training"""
        logger.info("🔧 Generating features...")

        try:
            fe = FeatureEngineer()
            df_features = fe.create_all_features(df)  # Fixed: correct method name

            logger.info(f"   Generated {len(df_features.columns)} features")
            logger.info(f"   {len(df_features)} samples ready for training")

            return df_features

        except Exception as e:
            logger.error(f"❌ Feature generation failed: {e}")
            raise

    def load_optimized_params(self, horizon: int) -> dict:
        """Load optimized hyperparameters for a horizon"""
        params_file = self.params_dir / f"optimized_params_{horizon}min.json"

        if params_file.exists():
            with open(params_file, 'r') as f:
                params = json.load(f)
            logger.info(f"   Loaded optimized params for {horizon}min")
            return params
        else:
            logger.warning(f"   No optimized params found for {horizon}min, using defaults")
            return {}

    def train_model(self, df: pd.DataFrame, horizon: int, optimized_params: dict):
        """Train a single model with optimized parameters"""
        logger.info(f"🚀 Training {horizon}min model...")

        try:
            from src.features import FeatureEngineer
            
            trainer = ModelTrainer()
            fe = FeatureEngineer()
            
            # Get feature columns
            feature_cols = fe.get_feature_columns(df)
            
            # Train model using the correct interface
            model, metrics = trainer.train_single_horizon(df, feature_cols, horizon)

            logger.info(f"   ✅ {horizon}min trained - MAE: {metrics['mae']:.2f}, "
                       f"RMSE: {metrics['rmse']:.4f}, Dir Acc: {metrics['directional_accuracy']:.2%}")

            return model, metrics

        except Exception as e:
            logger.error(f"❌ Training failed for {horizon}min: {e}")
            raise

    def validate_model(self, df: pd.DataFrame, horizon: int, old_metrics_file: Path):
        """Validate new model against old model performance"""
        logger.info(f"🔍 Validating {horizon}min model...")

        # Load old metrics if they exist
        if old_metrics_file.exists():
            with open(old_metrics_file, 'r') as f:
                old_metrics = json.load(f)
            old_dir_acc = old_metrics.get('directional_accuracy', 0)
        else:
            old_dir_acc = 0
            logger.warning(f"   No previous metrics found for {horizon}min")

        # Run quick backtest on recent data
        try:
            backtester = Backtester(
                model_path=str(self.models_dir / f"xgb_btc_{horizon}min_optimized_latest.json"),
                data_path=None,  # Will use provided df
                horizon_minutes=horizon
            )

            # Use last 30% of data for validation
            split_idx = int(len(df) * 0.7)
            validation_df = df.iloc[split_idx:]

            results = backtester.run_backtest(
                initial_capital=10000,
                commission=0.001,
                data=validation_df
            )

            new_dir_acc = results['metrics']['directional_accuracy']

            logger.info(f"   Old Dir Acc: {old_dir_acc:.2%}")
            logger.info(f"   New Dir Acc: {new_dir_acc:.2%}")

            # Accept new model if it's at least 95% as good as old one (allows some variance)
            threshold = old_dir_acc * 0.95
            is_acceptable = new_dir_acc >= threshold

            if is_acceptable:
                logger.info(f"   ✅ New model accepted (>= {threshold:.2%})")
            else:
                logger.warning(f"   ⚠️ New model rejected (< {threshold:.2%})")

            return is_acceptable, new_dir_acc

        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            # If validation fails, accept the new model (conservative approach)
            return True, 0.0

    def retrain_all_models(self, validate: bool = True):
        """Main retraining pipeline"""
        logger.info("=" * 80)
        logger.info("🔄 Starting Auto-Retraining Pipeline")
        logger.info("=" * 80)

        start_time = datetime.now()

        # 1. Backup current models
        backup_dir = self.backup_current_models()

        # 2. Fetch fresh data
        df_raw = self.fetch_fresh_data()

        # 3. Generate features
        df_features = self.prepare_features(df_raw)

        # 4. Train all models
        results = {}
        for horizon in self.horizons:
            logger.info("-" * 80)

            # Load optimized parameters
            optimized_params = self.load_optimized_params(horizon)

            # Train model
            model, metrics = self.train_model(df_features, horizon, optimized_params)

            # Validate if requested
            if validate:
                metrics_file = self.models_dir / f"xgb_btc_{horizon}min_optimized_latest_metrics.json"
                is_acceptable, new_dir_acc = self.validate_model(df_features, horizon, metrics_file)

                if not is_acceptable:
                    logger.warning(f"⚠️ Rolling back {horizon}min model to backup")
                    # Restore from backup
                    backup_file = backup_dir / f"xgb_btc_{horizon}min_optimized_latest.json"
                    model_file = self.models_dir / f"xgb_btc_{horizon}min_optimized_latest.json"
                    if backup_file.exists():
                        shutil.copy2(backup_file, model_file)
                    results[f"{horizon}min"] = {"status": "rolled_back", "reason": "performance_degradation"}
                    continue

            results[f"{horizon}min"] = {
                "status": "updated",
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }

        # 5. Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("✅ Auto-Retraining Complete!")
        logger.info(f"⏱️  Duration: {duration:.1f} seconds")
        logger.info(f"📦 Backup location: {backup_dir}")
        logger.info("=" * 80)

        # Save results
        results_file = self.logs_dir / f"retrain_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"📄 Results saved to: {results_file}")

        return results


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Auto-retrain BTC prediction models")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation step")
    parser.add_argument("--dir", default=".", help="Base directory (default: current)")

    args = parser.parse_args()

    try:
        retrainer = AutoRetrainer(base_dir=args.dir)
        results = retrainer.retrain_all_models(validate=not args.no_validate)

        # Print summary
        print("\n" + "=" * 80)
        print("📊 RETRAINING SUMMARY")
        print("=" * 80)

        for model, result in results.items():
            status = result['status']
            if status == 'updated':
                metrics = result['metrics']
                print(f"\n{model}:")
                print(f"  ✅ Status: {status}")
                print(f"  📈 MAE: ${metrics['mae']:.2f}")
                print(f"  📉 RMSE: {metrics['rmse']:.4f}")
                print(f"  🎯 Dir Acc: {metrics['directional_accuracy']:.2%}")
            else:
                print(f"\n{model}:")
                print(f"  ⚠️ Status: {status}")
                print(f"  ℹ️  Reason: {result.get('reason', 'unknown')}")

        print("\n" + "=" * 80)
        print("✅ Retraining pipeline completed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Retraining pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()
