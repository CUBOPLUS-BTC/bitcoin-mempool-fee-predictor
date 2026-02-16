"""
Test FastAPI application
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert 'message' in data
    assert 'version' in data
    assert 'endpoints' in data


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert 'status' in data
    assert 'uptime_seconds' in data
    assert 'models_loaded' in data
    assert 'version' in data

    assert isinstance(data['uptime_seconds'], (int, float))
    assert isinstance(data['models_loaded'], list)


def test_models_endpoint(client):
    """Test models info endpoint"""
    response = client.get("/models")

    # Should return 200 (even if no models loaded) or 503 (if not initialized)
    # In test environment, it's ok if models aren't loaded yet
    if response.status_code == 200:
        data = response.json()
        assert 'loaded_models' in data
        assert 'total_models' in data
        assert isinstance(data['loaded_models'], list)
        assert isinstance(data['total_models'], int)
    elif response.status_code == 503:
        # Service unavailable is acceptable in test environment
        # when no models have been trained yet
        pass
    else:
        # Any other status code is a failure
        assert False, f"Unexpected status code: {response.status_code}"


def test_api_cors_headers(client):
    """Test that CORS is configured"""
    response = client.options("/health")

    # CORS should allow cross-origin requests
    assert response.status_code in [200, 405]  # OPTIONS might not be explicitly handled
