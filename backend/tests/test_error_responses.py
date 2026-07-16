"""Regression tests for safe, traceable API errors introduced in v0.15.0."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from fastapi.testclient import TestClient

from app.main import app


def test_http_errors_keep_detail_and_add_request_id() -> None:
    client = TestClient(app)
    response = client.get('/api/v1/observability/status', headers={'X-Request-ID': 'test-request-403'})
    assert response.status_code == 401
    body = response.json()
    assert body['detail'] == 'Se requiere autenticacion'
    assert body['error_code'] == 'authentication_required'
    assert body['request_id'] == 'test-request-403'
    assert response.headers['X-Request-ID'] == 'test-request-403'


def test_validation_errors_are_bounded_and_do_not_echo_input() -> None:
    path = '/__tests__/validation-error-v015'
    if not any(getattr(route, 'path', None) == path for route in app.routes):
        router = APIRouter()

        class ValidationPayload(BaseModel):
            quantity: int = Field(ge=1, le=5)

        @router.post(path)
        def validate(payload: ValidationPayload) -> dict:
            return payload.model_dump()

        app.include_router(router)

    client = TestClient(app)
    response = client.post(
        path,
        json={'quantity': 'secret-value-that-must-not-be-echoed'},
        headers={'X-Request-ID': 'test-request-422'},
    )
    assert response.status_code == 422
    body = response.json()
    assert body['detail'] == 'Los datos enviados no son validos'
    assert body['error_code'] == 'validation_error'
    assert body['request_id'] == 'test-request-422'
    assert body['errors']
    assert 'secret-value-that-must-not-be-echoed' not in response.text


def test_unhandled_errors_return_generic_message(monkeypatch) -> None:
    # Add a test-only route once. FastAPI allows this during test collection.
    path = '/__tests__/unexpected-error-v015'
    if not any(getattr(route, 'path', None) == path for route in app.routes):
        router = APIRouter()

        @router.get(path)
        def fail() -> None:
            raise RuntimeError('database password must never be returned')

        app.include_router(router)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(path, headers={'X-Request-ID': 'test-request-500'})
    assert response.status_code == 500
    body = response.json()
    assert body['error_code'] == 'internal_error'
    assert body['request_id'] == 'test-request-500'
    assert 'database password' not in response.text
