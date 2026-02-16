"""
Test feature engineering module
"""
import pytest
import pandas as pd
import numpy as np
from src.features import FeatureEngineer


def test_feature_engineer_initialization(config_path):
    """Test FeatureEngineer can be initialized"""
    engineer = FeatureEngineer(config_path=config_path)

    assert engineer is not None
    assert engineer.config is not None


def test_create_price_features(config_path, sample_ohlcv_data):
    """Test basic price features are created"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer._add_price_features(sample_ohlcv_data.copy())

    assert 'returns' in df.columns
    assert 'high_low_pct' in df.columns
    assert 'close_open_pct' in df.columns
    assert 'price_position' in df.columns


def test_create_technical_indicators(config_path, sample_ohlcv_data):
    """Test technical indicators are created"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer._add_technical_indicators(sample_ohlcv_data.copy())

    # Check RSI
    assert 'rsi' in df.columns
    assert 'rsi_norm' in df.columns

    # Check MACD
    assert 'macd' in df.columns
    assert 'macd_signal' in df.columns
    assert 'macd_hist' in df.columns

    # Check Bollinger Bands
    assert 'bb_upper' in df.columns
    assert 'bb_middle' in df.columns
    assert 'bb_lower' in df.columns
    assert 'bb_position' in df.columns


def test_create_volume_features(config_path, sample_ohlcv_data):
    """Test volume features are created"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer._add_volume_features(sample_ohlcv_data.copy())

    assert 'volume_ma_5' in df.columns
    assert 'volume_ratio_5' in df.columns
    assert 'vwap' in df.columns


def test_create_volatility_features(config_path, sample_ohlcv_data):
    """Test volatility features are created"""
    engineer = FeatureEngineer(config_path=config_path)
    df = sample_ohlcv_data.copy()

    # Add returns first (required for volatility)
    df = engineer._add_price_features(df)
    df = engineer._add_volatility_features(df)

    assert 'volatility_10' in df.columns
    assert 'volatility_20' in df.columns
    assert 'parkinson_vol_10' in df.columns


def test_create_time_features(config_path, sample_ohlcv_data):
    """Test time-based features are created"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer._add_time_features(sample_ohlcv_data.copy())

    assert 'hour_sin' in df.columns
    assert 'hour_cos' in df.columns
    assert 'day_sin' in df.columns
    assert 'day_cos' in df.columns
    assert 'is_weekend' in df.columns


def test_create_lag_features(config_path, sample_ohlcv_data):
    """Test lag features are created"""
    engineer = FeatureEngineer(config_path=config_path)
    df = sample_ohlcv_data.copy()

    # Add returns first (required)
    df = engineer._add_price_features(df)
    df = engineer._add_technical_indicators(df)
    df = engineer._add_lag_features(df, n_lags=3)

    assert 'close_lag_1' in df.columns
    assert 'close_lag_2' in df.columns
    assert 'close_lag_3' in df.columns
    assert 'returns_lag_1' in df.columns


def test_create_all_features(config_path, sample_ohlcv_data):
    """Test that all features are created together"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())

    # Check that we have many features
    assert len(df.columns) > 20, "Should have many features"

    # Check no NaN after cleaning
    assert df.isnull().sum().sum() == 0, "Should have no NaN values after cleaning"

    # Check we still have data
    assert len(df) > 0, "Should have data after cleaning"


def test_create_multi_horizon_targets(config_path, sample_ohlcv_data):
    """Test multi-horizon target creation"""
    engineer = FeatureEngineer(config_path=config_path)
    df = sample_ohlcv_data.copy()

    # Create features first
    df = engineer.create_all_features(df)

    # Create targets for specific horizons
    df = engineer.create_multi_horizon_targets(df, horizons=[30, 60])

    assert 'target_30min' in df.columns
    assert 'target_30min_pct' in df.columns
    assert 'target_60min' in df.columns
    assert 'target_60min_pct' in df.columns


def test_get_feature_columns(config_path, sample_ohlcv_data):
    """Test getting feature column names"""
    engineer = FeatureEngineer(config_path=config_path)
    df = engineer.create_all_features(sample_ohlcv_data.copy())
    df = engineer.create_multi_horizon_targets(df, horizons=[30])

    feature_cols = engineer.get_feature_columns(df)

    # Should exclude OHLCV, timestamp, and targets
    assert 'timestamp' not in feature_cols
    assert 'open' not in feature_cols
    assert 'close' not in feature_cols
    assert 'target_30min' not in feature_cols
    assert 'target_30min_pct' not in feature_cols

    # Should include actual features
    assert 'returns' in feature_cols
    assert len(feature_cols) > 10
