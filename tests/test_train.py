"""
Test model training module
"""
import pytest
import pandas as pd
import numpy as np
from src.train import ModelTrainer
from src.features import FeatureEngineer


def test_model_trainer_initialization(config_path):
    """Test ModelTrainer can be initialized"""
    trainer = ModelTrainer(config_path=config_path)

    assert trainer is not None
    assert trainer.config is not None
    assert trainer.models_dir is not None


def test_prepare_data(config_path, sample_ohlcv_data):
    """Test data preparation for training"""
    # Create features and targets
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)
    target_col = 'target_30min_pct'

    # Prepare data
    trainer = ModelTrainer(config_path=config_path)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, feature_cols, target_col
    )

    # Check shapes
    assert len(X_train) > 0
    assert len(X_test) > 0
    assert X_train.shape[1] == len(feature_cols)
    assert X_test.shape[1] == len(feature_cols)
    assert len(y_train) == len(X_train)
    assert len(y_test) == len(X_test)

    # Check time-series split (test should be after train)
    total_samples = len(X_train) + len(X_test)
    assert total_samples == len(df)


def test_data_split_ratio(config_path, sample_ohlcv_data):
    """Test that data split respects configured test_size"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)
    target_col = 'target_30min_pct'

    trainer = ModelTrainer(config_path=config_path)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, feature_cols, target_col
    )

    test_size = trainer.config['model']['test_size']
    actual_test_ratio = len(X_test) / (len(X_train) + len(X_test))

    # Allow small tolerance for rounding
    assert abs(actual_test_ratio - test_size) < 0.05


def test_train_model_basic(config_path, sample_ohlcv_data):
    """Test basic model training (smoke test)"""
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

    assert model is not None
    assert hasattr(model, 'predict')


def test_evaluate_model(config_path, sample_ohlcv_data):
    """Test model evaluation"""
    # Prepare and train
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

    # Evaluate
    metrics = trainer.evaluate_model(model, X_test, y_test, horizon=30)

    # Check metrics exist
    assert 'mse' in metrics
    assert 'rmse' in metrics
    assert 'mae' in metrics
    assert 'r2' in metrics
    assert 'mape' in metrics
    assert 'directional_accuracy' in metrics

    # Check metrics are reasonable
    assert metrics['mse'] >= 0
    assert metrics['rmse'] >= 0
    assert metrics['mae'] >= 0
    assert 0 <= metrics['directional_accuracy'] <= 1
