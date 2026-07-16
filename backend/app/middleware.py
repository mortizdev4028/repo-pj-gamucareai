"""Request tracing, access logs and Prometheus metrics."""
import logging
import time
import uuid

import jwt
from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_context import ip_address_ctx, request_id_ctx, user_agent_ctx
from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models import AuditLog, User

logger = logging.getLogger('gamucare.access')

REQUESTS = Counter(
    'gamucare_http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status_code'],
)
DURATION = Histogram(
    'gamucare_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'path'],
)


def _audit_rejected_request(request: Request, status_code: int, request_id: str, client_ip: str | None, user_agent: str | None) -> None:
    """Persist denied access and failed write attempts without reading the body."""
    if status_code not in {401, 403, 423} and not (status_code >= 400 and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}):
        return
    db = SessionLocal()
    try:
        actor = None
        authorization = request.headers.get('Authorization', '')
        if authorization.lower().startswith('bearer '):
            try:
                payload = decode_access_token(authorization.split(' ', 1)[1])
                actor = db.get(User, uuid.UUID(payload['sub']))
            except (jwt.PyJWTError, KeyError, TypeError, ValueError):
                actor = None
        db.add(AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action='security.access_denied' if status_code in {401, 403, 423} else 'request.write_failed',
            entity_type='http_request',
            entity_id=request.url.path[:120],
            outcome='blocked' if status_code in {403, 423} else 'failed',
            request_id=request_id,
            ip_address=client_ip,
            user_agent=user_agent,
            details={'method': request.method, 'path': request.url.path, 'status_code': status_code},
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception('audit_write_failed')
    finally:
        db.close()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID and request metadata without logging payloads."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))[:80]
        forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        client_ip = forwarded_for or (request.client.host if request.client else None)
        user_agent = request.headers.get('User-Agent', '')[:255] or None

        request_token = request_id_ctx.set(request_id)
        ip_token = ip_address_ctx.set(client_ip)
        agent_token = user_agent_ctx.set(user_agent)
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            _audit_rejected_request(request, response.status_code, request_id, client_ip, user_agent)
            return response
        except Exception:
            _audit_rejected_request(request, 500, request_id, client_ip, user_agent)
            logger.exception(
                'request_failed',
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.url.path,
                },
            )
            raise
        finally:
            duration = time.perf_counter() - start
            route = request.scope.get('route')
            path_template = getattr(route, 'path', request.url.path)
            status_code = response.status_code if response is not None else 500
            if response is not None:
                response.headers['X-Request-ID'] = request_id
            REQUESTS.labels(request.method, path_template, status_code).inc()
            DURATION.labels(request.method, path_template).observe(duration)
            logger.info(
                'request_completed',
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': path_template,
                    'status_code': status_code,
                    'duration_ms': round(duration * 1000, 2),
                },
            )
            request_id_ctx.reset(request_token)
            ip_address_ctx.reset(ip_token)
            user_agent_ctx.reset(agent_token)
