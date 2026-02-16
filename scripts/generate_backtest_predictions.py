"""
Generate historical predictions for backtesting
Walks through historical data and generates predictions as if in real-time
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.inference import ModelInference
from src.features import FeatureEngineer
from loguru import logger


def generate_walk_forward_predictions(
    data_df: pd.DataFrame,
    horizons: list,
    lookback_window: int = 100
) -> pd.DataFrame:
    """
    Generate predictions using walk-forward methodology

    Args:
        data_df: Full historical OHLCV data
        horizons: List of prediction horizons in minutes
        lookback_window: Minimum candles needed for features

    Returns:
        DataFrame with predictions
    """
    logger.info(f"Generating walk-forward predictions for {len(data_df)} candles")
    logger.info(f"Horizons: {horizons}")

    inference = ModelInference()
    engineer = FeatureEngineer()

    predictions = []

    # Start from lookback_window to have enough history
    for i in range(lookback_window, len(data_df)):
        # Get historical data up to this point
        historical_data = data_df.iloc[:i+1].copy()

        # Get current timestamp and price
        current_timestamp = historical_data.iloc[-1]['timestamp']
        current_price = historical_data.iloc[-1]['close']

        # Prepare features
        try:
            features = inference.prepare_features_from_raw(historical_data)

            if features is None:
                continue

            # Make predictions for all horizons
            for horizon in horizons:
                result = inference.predict_single_horizon(features, horizon)

                if result:
                    predictions.append({
                        'timestamp': current_timestamp,
                        'horizon': horizon,
                        'current_price': current_price,
                        'predicted_price': result['predicted_price'],
                        'predicted_change_pct': result['predicted_change_pct'],
                        'signal': result['signal'],
                        'confidence': result['confidence']
                    })

        except Exception as e:
            logger.warning(f"Failed to generate prediction at index {i}: {e}")
            continue

        # Progress update every 100 candles
        if i % 100 == 0:
            logger.info(f"Progress: {i}/{len(data_df)} candles processed")

    predictions_df = pd.DataFrame(predictions)
    logger.info(f"✓ Generated {len(predictions_df)} predictions")

    return predictions_df


def add_actual_outcomes(predictions_df: pd.DataFrame, data_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add actual price outcomes to predictions

    Args:
        predictions_df: Predictions DataFrame
        data_df: Historical OHLCV data

    Returns:
        Predictions DataFrame with actual outcomes
    """
    logger.info("Adding actual outcomes to predictions")

    predictions_df = predictions_df.copy()
    predictions_df['actual_price'] = np.nan
    predictions_df['actual_change_pct'] = np.nan
    predictions_df['prediction_correct'] = False

    for idx, row in predictions_df.iterrows():
        pred_timestamp = row['timestamp']
        horizon_minutes = row['horizon']

        # Find the actual price at target time
        target_timestamp = pred_timestamp + pd.Timedelta(minutes=horizon_minutes)

        # Find closest timestamp in data
        data_df['time_diff'] = abs(data_df['timestamp'] - target_timestamp)
        closest_idx = data_df['time_diff'].idxmin()

        if data_df.loc[closest_idx, 'time_diff'] < pd.Timedelta(minutes=30):  # Within 30 min tolerance
            actual_price = data_df.loc[closest_idx, 'close']
            actual_change = (actual_price - row['current_price']) / row['current_price']

            predictions_df.loc[idx, 'actual_price'] = actual_price
            predictions_df.loc[idx, 'actual_change_pct'] = actual_change * 100

            # Check if direction was correct
            predicted_direction = np.sign(row['predicted_change_pct'])
            actual_direction = np.sign(actual_change)
            predictions_df.loc[idx, 'prediction_correct'] = (predicted_direction == actual_direction)

    # Remove NaN rows
    predictions_df = predictions_df.dropna(subset=['actual_price'])

    logger.info(f"✓ Matched {len(predictions_df)} predictions with actual outcomes")

    return predictions_df


def main():
    """Generate predictions for backtesting"""
    logger.add("logs/backtest_predictions.log", rotation="1 day", retention="7 days")

    logger.info("=" * 80)
    logger.info("GENERATING BACKTEST PREDICTIONS")
    logger.info("=" * 80)

    # Load processed data with features
    engineer = FeatureEngineer()
    df = engineer.load_latest_processed_data()

    if df is None:
        logger.error("No processed data found. Run feature engineering first.")
        return 1

    # Get raw data for actual prices
    from src.ingestion import DataIngestion
    ingestion = DataIngestion()
    raw_df = ingestion.load_latest_raw_data()

    if raw_df is None:
        logger.error("No raw data found.")
        return 1

    logger.info(f"Loaded {len(df)} processed samples")
    logger.info(f"Loaded {len(raw_df)} raw OHLCV candles")

    # Generate predictions
    horizons = [30, 60, 180, 360, 720]
    predictions_df = generate_walk_forward_predictions(raw_df, horizons, lookback_window=100)

    # Add actual outcomes
    predictions_df = add_actual_outcomes(predictions_df, raw_df)

    # Calculate accuracy by horizon
    logger.info("\n" + "=" * 80)
    logger.info("PREDICTION ACCURACY BY HORIZON")
    logger.info("=" * 80)

    for horizon in horizons:
        horizon_preds = predictions_df[predictions_df['horizon'] == horizon]
        if len(horizon_preds) > 0:
            accuracy = horizon_preds['prediction_correct'].mean()
            logger.info(f"{horizon}min: {accuracy:.2%} ({len(horizon_preds)} predictions)")

    overall_accuracy = predictions_df['prediction_correct'].mean()
    logger.info(f"\nOverall Accuracy: {overall_accuracy:.2%}")

    # Save predictions
    output_dir = Path("backtest_results")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "historical_predictions.csv"
    predictions_df.to_csv(output_file, index=False)

    logger.info(f"\n✓ Predictions saved to {output_file}")
    logger.info(f"Total predictions: {len(predictions_df)}")

    # Also save price data for backtesting
    price_file = output_dir / "historical_prices.csv"
    raw_df[['timestamp', 'close']].rename(columns={'close': 'price'}).to_csv(price_file, index=False)
    logger.info(f"✓ Price data saved to {price_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
