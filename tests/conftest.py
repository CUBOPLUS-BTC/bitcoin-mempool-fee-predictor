"""
Pytest configuration and fixtures
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start='2024-01-01', periods=1000, freq='30T')

    # Generate realistic-looking price data
    np.random.seed(42)
    base_price = 50000
    returns = np.random.normal(0, 0.01, len(dates))
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.uniform(-0.002, 0.002, len(dates))),
        'high': prices * (1 + np.random.uniform(0.001, 0.005, len(dates))),
        'low': prices * (1 + np.random.uniform(-0.005, -0.001, len(dates))),
        'close': prices,
        'volume': np.random.uniform(100, 1000, len(dates))
    })

    return df


@pytest.fixture
def config_path():
    """Return path to config file"""
    return "config/config.yaml"


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directories"""
    raw_dir = tmp_path / "data" / "raw"
    processed_dir = tmp_path / "data" / "processed"
    raw_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)
    return tmp_path
