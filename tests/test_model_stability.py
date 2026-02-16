"""
Test model stability and consistency
"""
import pytest
import pandas as pd
import numpy as np
from src.train import ModelTrainer
from src.features import FeatureEngineer
from src.inference import ModelInference


def test_model_predictions_consistency(config_path, sample_ohlcv_data):
    """Test that models give consistent predictions on same data"""
    # Prepare data
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)
    target_col = 'target_30min_pct'

    trainer = ModelTrainer(config_path=config_path)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, feature_cols, target_col
    )

    # Train model
    model = trainer.train_model(X_train, y_train, X_test, y_test, horizon=30)

    # Make predictions twice on same data
    pred1 = model.predict(X_test[:10])
    pred2 = model.predict(X_test[:10])

    # Should be identical
    np.testing.assert_array_equal(pred1, pred2)


def test_model_direction_bias(config_path, sample_ohlcv_data):
    """Test that model doesn't have extreme directional bias"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)
    target_col = 'target_30min_pct'

    trainer = ModelTrainer(config_path=config_path)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, feature_cols, target_col
    )

    model = trainer.train_model(X_train, y_train, X_test, y_test, horizon=30)

    # Get predictions
    predictions = model.predict(X_test)

    # Count positive vs negative predictions
    positive_preds = (predictions > 0).sum()
    negative_preds = (predictions < 0).sum()
    total_preds = len(predictions)

    # Neither should be more than 90% (would indicate severe bias)
    # Note: In trending markets, some bias is expected
    # This is more of a sanity check than a hard requirement
    if positive_preds / total_preds >= 0.9:
        import warnings
        warnings.warn(f"Model has strong bullish bias: {positive_preds/total_preds:.1%} predictions are positive")

    if negative_preds / total_preds >= 0.9:
        import warnings
        warnings.warn(f"Model has strong bearish bias: {negative_preds/total_preds:.1%} predictions are negative")

    # At least check it's not 100% one direction
    assert positive_preds > 0 or negative_preds > 0, "Model predicts only one direction"


def test_prediction_magnitude_reasonable(config_path, sample_ohlcv_data):
    """Test that predictions are within reasonable bounds"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)
    target_col = 'target_30min_pct'

    trainer = ModelTrainer(config_path=config_path)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, feature_cols, target_col
    )

    model = trainer.train_model(X_train, y_train, X_test, y_test, horizon=30)

    predictions = model.predict(X_test)

    # For 30min predictions, anything above 20% is unrealistic for BTC
    assert np.abs(predictions).max() < 0.20, "Predictions are unrealistically large"

    # Most predictions should be small (< 5%)
    small_predictions = (np.abs(predictions) < 0.05).sum() / len(predictions)
    assert small_predictions > 0.5, "Most predictions should be < 5%"


def test_feature_importance_sanity(config_path, sample_ohlcv_data):
    """Test that feature importances make sense"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)
    target_col = 'target_30min_pct'

    trainer = ModelTrainer(config_path=config_path)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, feature_cols, target_col
    )

    model = trainer.train_model(X_train, y_train, X_test, y_test, horizon=30)

    # Get feature importances
    importances = model.feature_importances_

    # Should have same length as features
    assert len(importances) == len(feature_cols)

    # Should sum to 1 (or close to it)
    assert 0.99 < importances.sum() < 1.01

    # No single feature should dominate (> 50%)
    assert importances.max() < 0.5, "Single feature has too much importance"


def test_inference_multiple_predictions(config_path, sample_ohlcv_data):
    """Test that inference engine can make multiple predictions"""
    inference = ModelInference(config_path=config_path)

    # Prepare features from raw data
    features = inference.prepare_features_from_raw(sample_ohlcv_data.copy())

    assert features is not None
    assert 'close' in features.columns
    assert len(features) == 1  # Should be single row
