"""
Hyperparameter Optimization with Optuna
Optimizes XGBoost parameters to improve model performance
Focuses on directional accuracy (most important for trading)
"""

import optuna
import xgboost as xgb
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import yaml
import json
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def prepare_data(df: pd.DataFrame, feature_cols: list, target_col: str):
    """Prepare data for training"""
    X = df[feature_cols].values
    y = df[target_col].values

    # Time-based split (no shuffle for time series)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    return X_train, X_test, y_train, y_test


def objective(trial, X_train, y_train, X_test, y_test):
    """
    Optuna objective function
    Optimize for directional accuracy (most important for trading)
    """
    # Define hyperparameter search space
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.001, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'gamma': trial.suggest_float('gamma', 0.0, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 2.0),
        'random_state': 42,
        'tree_method': 'hist',
        'verbosity': 0,
        'early_stopping_rounds': 20
    }

    # Train model
    model = xgb.XGBRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    # Predict
    y_pred = model.predict(X_test)

    # Calculate directional accuracy (primary metric)
    y_test_direction = np.sign(y_test)
    y_pred_direction = np.sign(y_pred)
    directional_accuracy = (y_test_direction == y_pred_direction).mean()

    # Calculate RMSE (secondary metric)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    # Combined objective: maximize directional accuracy, minimize RMSE
    # Weight directional accuracy more heavily (70% vs 30%)
    # Normalize RMSE to 0-1 scale (assuming max RMSE ~0.1)
    normalized_rmse = min(rmse / 0.1, 1.0)

    # Higher is better
    score = (0.7 * directional_accuracy) + (0.3 * (1 - normalized_rmse))

    return score


def optimize_horizon(df: pd.DataFrame, feature_cols: list, horizon: int, n_trials: int = 50):
    """
    Optimize hyperparameters for a specific horizon

    Args:
        df: DataFrame with features and targets
        feature_cols: List of feature columns
        horizon: Prediction horizon in minutes
        n_trials: Number of Optuna trials

    Returns:
        Best parameters and study object
    """
    logger.info(f"=" * 80)
    logger.info(f"OPTIMIZING HYPERPARAMETERS FOR {horizon}min HORIZON")
    logger.info(f"=" * 80)

    target_col = f'target_{horizon}min_pct'

    if target_col not in df.columns:
        logger.error(f"Target column {target_col} not found")
        return None, None

    # Prepare data
    X_train, X_test, y_train, y_test = prepare_data(df, feature_cols, target_col)

    logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
    logger.info(f"Running {n_trials} optimization trials...")

    # Create study
    study = optuna.create_study(
        direction='maximize',
        study_name=f'xgb_{horizon}min',
        sampler=optuna.samplers.TPESampler(seed=42)
    )

    # Optimize
    study.optimize(
        lambda trial: objective(trial, X_train, y_train, X_test, y_test),
        n_trials=n_trials,
        show_progress_bar=True
    )

    # Get best parameters
    best_params = study.best_params
    best_score = study.best_value

    logger.info(f"\n✓ Optimization complete!")
    logger.info(f"Best score: {best_score:.4f}")
    logger.info(f"Best parameters:")
    for param, value in best_params.items():
        logger.info(f"  {param}: {value}")

    # Evaluate best model
    logger.info(f"\nEvaluating best model...")
    best_model = xgb.XGBRegressor(**best_params, random_state=42, tree_method='hist', early_stopping_rounds=20)
    best_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = best_model.predict(X_test)

    # Metrics
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    y_test_direction = np.sign(y_test)
    y_pred_direction = np.sign(y_pred)
    dir_acc = (y_test_direction == y_pred_direction).mean()

    logger.info(f"  RMSE: {rmse:.6f}")
    logger.info(f"  MAE: {mae:.6f}")
    logger.info(f"  Directional Accuracy: {dir_acc:.2%}")

    return best_params, study


def main():
    """Main optimization entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Optimize XGBoost hyperparameters")
    parser.add_argument('--horizon', type=int, default=720, help='Horizon to optimize (default: 720)')
    parser.add_argument('--trials', type=int, default=50, help='Number of Optuna trials')
    parser.add_argument('--all', action='store_true', help='Optimize all horizons')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='Config file path')

    args = parser.parse_args()

    # Setup logging
    logger.add("logs/optimization.log", rotation="1 day", retention="7 days")

    logger.info("=" * 80)
    logger.info("HYPERPARAMETER OPTIMIZATION WITH OPTUNA")
    logger.info("=" * 80)

    # Load config
    config = load_config(args.config)

    # Load data
    from src.features import FeatureEngineer
    engineer = FeatureEngineer(config_path=args.config)
    df = engineer.load_latest_processed_data()

    if df is None:
        logger.error("No processed data found")
        return 1

    # Get feature columns
    feature_cols = engineer.get_feature_columns(df)
    logger.info(f"Using {len(feature_cols)} features")

    # Create output directory
    output_dir = Path("optimized_params")
    output_dir.mkdir(exist_ok=True)

    # Optimize
    if args.all:
        horizons = config['model']['horizons']
    else:
        horizons = [args.horizon]

    all_results = {}

    for horizon in horizons:
        best_params, study = optimize_horizon(df, feature_cols, horizon, n_trials=args.trials)

        if best_params:
            # Save results
            results = {
                'horizon': horizon,
                'best_params': best_params,
                'best_score': study.best_value,
                'n_trials': len(study.trials),
                'timestamp': datetime.now().isoformat()
            }

            output_file = output_dir / f"optimized_params_{horizon}min.json"
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)

            logger.info(f"✓ Results saved to {output_file}")

            all_results[horizon] = results

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("OPTIMIZATION SUMMARY")
    logger.info("=" * 80)

    for horizon, results in all_results.items():
        logger.info(f"\n{horizon}min:")
        logger.info(f"  Best score: {results['best_score']:.4f}")
        logger.info(f"  Learning rate: {results['best_params']['learning_rate']:.4f}")
        logger.info(f"  Max depth: {results['best_params']['max_depth']}")
        logger.info(f"  N estimators: {results['best_params']['n_estimators']}")

    logger.info("\n✓ Optimization complete!")
    logger.info(f"Results saved to {output_dir}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
