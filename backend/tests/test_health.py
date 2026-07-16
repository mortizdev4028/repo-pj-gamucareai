from fastapi.testclient import TestClient

from app.main import app
from app.version import APP_VERSION


def test_live_endpoint() -> None:
    client = TestClient(app)
    response = client.get('/health/live')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['version'] == APP_VERSION
