import pytest

@pytest.fixture(scope='session')
def test_client():
    from fastapi.testclient import TestClient
    from src.ntheemba_auth.main import app

    client = TestClient(app)
    yield client
    # Cleanup can be done here if needed