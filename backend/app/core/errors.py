"""Safe and traceable HTTP error responses.

The public response keeps FastAPI's ``detail`` field for backwards compatibility,
adds a stable error code and exposes the request correlation identifier. Internal
exceptions are logged but their implementation details are never returned.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import request_id_ctx

logger = logging.getLogger(__name__)

_STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: 'bad_request',
    status.HTTP_401_UNAUTHORIZED: 'authentication_required',
    status.HTTP_403_FORBIDDEN: 'forbidden',
    status.HTTP_404_NOT_FOUND: 'not_found',
    status.HTTP_409_CONFLICT: 'conflict',
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: 'payload_too_large',
    status.HTTP_422_UNPROCESSABLE_ENTITY: 'validation_error',
    status.HTTP_423_LOCKED: 'account_locked',
    status.HTTP_429_TOO_MANY_REQUESTS: 'rate_limited',
    status.HTTP_503_SERVICE_UNAVAILABLE: 'service_unavailable',
}


def _request_id(request: Request) -> str | None:
    return request_id_ctx.get() or request.headers.get('X-Request-ID')


def _payload(*, detail: Any, code: str, request: Request, errors: list[dict[str, Any]] | None = None) -> dict:
    payload: dict[str, Any] = {
        'detail': detail,
        'error_code': code,
        'request_id': _request_id(request),
    }
    if errors:
        payload['errors'] = errors
    return payload


def register_error_handlers(app: FastAPI) -> None:
    """Register compatible, non-leaking error handlers on the application."""

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, 'http_error')
        headers = dict(exc.headers or {})
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            headers.setdefault('Retry-After', '15')
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(detail=exc.detail, code=code, request=request),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                'location': [str(value) for value in item.get('loc', ())],
                'message': item.get('msg', 'Valor no valido'),
                'type': item.get('type', 'validation_error'),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_payload(
                detail='Los datos enviados no son validos',
                code='validation_error',
                request=request,
                errors=errors,
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            'unhandled_application_error',
            extra={
                'request_id': _request_id(request),
                'method': request.method,
                'path': request.url.path,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload(
                detail='Se ha producido un error interno. Usa el identificador de solicitud para revisar la incidencia.',
                code='internal_error',
                request=request,
            ),
        )
