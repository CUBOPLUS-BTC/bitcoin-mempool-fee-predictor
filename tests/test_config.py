"""
Test configuration loading
"""
import pytest
import yaml
from pathlib import Path


def test_config_file_exists():
    """Test that config file exists"""
    config_path = Path("config/config.yaml")
    assert config_path.exists(), "Config file not found"


def test_config_is_valid_yaml():
    """Test that config is valid YAML"""
    config_path = Path("config/config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    assert config is not None, "Config is empty"
    assert isinstance(config, dict), "Config should be a dictionary"


def test_config_has_required_sections():
    """Test that config has all required sections"""
    config_path = Path("config/config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    required_sections = ['data', 'features', 'model', 'api']

    for section in required_sections:
        assert section in config, f"Config missing {section} section"


def test_config_data_section():
    """Test data section has required fields"""
    config_path = Path("config/config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    data_config = config['data']

    assert 'exchange' in data_config
    assert 'symbol' in data_config
    assert 'base_timeframe' in data_config
    assert 'lookback_days' in data_config
    assert 'raw_dir' in data_config
    assert 'processed_dir' in data_config


def test_config_model_horizons():
    """Test that model horizons are defined"""
    config_path = Path("config/config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    horizons = config['model']['horizons']

    assert isinstance(horizons, list), "Horizons should be a list"
    assert len(horizons) > 0, "At least one horizon should be defined"
    assert all(isinstance(h, int) for h in horizons), "All horizons should be integers"
