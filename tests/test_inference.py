"""
Test inference module
"""
import pytest
from src.inference import ModelInference


def test_inference_initialization(config_path):
    """Test ModelInference can be initialized"""
    inference = ModelInference(config_path=config_path)

    assert inference is not None
    assert inference.config is not None
    assert inference.models_dir is not None
    assert isinstance(inference.models, dict)
    assert isinstance(inference.model_timestamps, dict)


def test_get_loaded_models_info(config_path):
    """Test getting loaded models info"""
    inference = ModelInference(config_path=config_path)

    info = inference.get_loaded_models_info()

    assert 'loaded_models' in info
    assert 'total_models' in info
    assert 'load_timestamps' in info
    assert isinstance(info['loaded_models'], list)
    assert isinstance(info['total_models'], int)


def test_prepare_features_from_raw(config_path, sample_ohlcv_data):
    """Test feature preparation from raw data"""
    inference = ModelInference(config_path=config_path)

    features = inference.prepare_features_from_raw(sample_ohlcv_data.copy())

    # Should return features (last row only)
    assert features is not None
    assert len(features) == 1  # Only last row
    assert len(features.columns) > 10  # Should have many features
