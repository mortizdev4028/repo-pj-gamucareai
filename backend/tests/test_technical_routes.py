"""API-level access tests for the isolated technical profile."""
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from app.models import User
from app.routers import observability


def user(role: str) -> User:
    """Build a lightweight authenticated user for dependency overrides."""
    return User(email=f'{role}@example.test', password_hash='unused', role=role, is_active=True)


def request_as(role: str, path: str):
    app.dependency_overrides[get_current_user] = lambda: user(role)
    try:
        return TestClient(app).get(path)
    finally:
        app.dependency_overrides.clear()


def test_technical_profile_can_open_operational_status(monkeypatch) -> None:
    monkeypatch.setattr(
        observability,
        'dependency_status',
        lambda: {'status': 'ok', 'dependencies': {}},
    )
    response = request_as('technical', '/api/v1/observability/status')
    assert response.status_code == 200


def test_clinic_profile_cannot_open_operational_status() -> None:
    response = request_as('clinic', '/api/v1/observability/status')
    assert response.status_code == 403


def test_technical_profile_cannot_open_business_dashboard() -> None:
    response = request_as('technical', '/api/v1/dashboard')
    assert response.status_code == 403
