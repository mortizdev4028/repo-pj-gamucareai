"""FastAPI application factory and infrastructure endpoints."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from sqlalchemy import text

from app.config import get_settings
from app.core.logging import configure_logging
from app.core.errors import register_error_handlers
from app.database import engine
from app.middleware import RequestContextMiddleware
from app.version import APP_VERSION
from app.services.observability import dependency_status
from app.routers import alerts, audit, auth, chat, dashboard, integrations, observability, owners, pets, plans, quality, rag_quality

settings = get_settings()
configure_logging(
    settings.log_level,
    settings.log_file,
    settings.log_max_bytes,
    settings.log_backup_count,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info('application_started')
    yield
    logger.info('application_stopped')


app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    description='MVP veterinario con planes de salud, VetIA, alertas preventivas, integracion Wakyma simulada, seguridad, auditoria y evaluacion formal.',
    lifespan=lifespan,
)
register_error_handlers(app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

prefix = '/api/v1'
app.include_router(auth.router, prefix=prefix)
app.include_router(audit.router, prefix=prefix)
app.include_router(dashboard.router, prefix=prefix)
app.include_router(integrations.router, prefix=prefix)
app.include_router(owners.router, prefix=prefix)
app.include_router(pets.router, prefix=prefix)
app.include_router(plans.router, prefix=prefix)
app.include_router(alerts.router, prefix=prefix)
app.include_router(chat.router, prefix=prefix)
app.include_router(rag_quality.router, prefix=prefix)
app.include_router(quality.router, prefix=prefix)
app.include_router(observability.router, prefix=prefix)
app.mount('/metrics', make_asgi_app())


@app.get('/health/live', tags=['health'])
def live() -> dict:
    return {'status': 'ok', 'service': settings.app_name, 'version': APP_VERSION}


@app.get('/health/ready', tags=['health'])
def ready() -> dict:
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))
    return {'status': 'ready'}


@app.get('/health/dependencies', tags=['health'])
def dependencies(response: Response) -> dict:
    result = dependency_status()
    if result['status'] != 'ok':
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
