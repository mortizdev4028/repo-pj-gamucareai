"""Operational dependency checks used by health endpoints and the UI."""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Callable

import httpx
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.observability.metrics import DEPENDENCY_LATENCY, DEPENDENCY_UP
from app.version import APP_VERSION

settings = get_settings()


def _timed(name: str, callback: Callable[[], None]) -> dict:
    started = time.perf_counter()
    error = None
    status = 'up'
    try:
        callback()
    except Exception as exc:  # Dependency failures must be represented, not hidden.
        status = 'down'
        error = str(exc)[:300]
    latency = time.perf_counter() - started
    DEPENDENCY_UP.labels(name).set(1 if status == 'up' else 0)
    DEPENDENCY_LATENCY.labels(name).set(latency)
    result = {'status': status, 'latency_ms': round(latency * 1000, 2)}
    if error:
        result['error'] = error
    return result


def _check_postgres() -> None:
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))


def _check_http(url: str) -> None:
    with httpx.Client(timeout=5.0) as client:
        response = client.get(url)
        response.raise_for_status()


def dependency_status() -> dict:
    """Return an active, bounded check of the local Docker dependencies."""
    checks = {
        'postgres': _timed('postgres', _check_postgres),
        'qdrant': _timed('qdrant', lambda: _check_http(f'{settings.qdrant_url.rstrip("/")}/readyz')),
        'ollama': _timed('ollama', lambda: _check_http(f'{settings.ollama_url.rstrip("/")}/api/tags')),
    }
    overall = 'ok' if all(item['status'] == 'up' for item in checks.values()) else 'degraded'
    return {
        'status': overall,
        'service': settings.app_name,
        'version': APP_VERSION,
        'environment': settings.app_env,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'dependencies': checks,
        'monitoring': {
            'grafana_url': 'http://localhost:3000',
            'prometheus_url': 'http://localhost:9090',
            'alertmanager_url': 'http://localhost:9093',
        },
    }
