"""Audit helpers with privacy-aware snapshots.

Audit records deliberately avoid storing passwords, tokens and full clinical
notes. They provide enough evidence to reconstruct who changed a record and
which business fields changed without turning the audit table into a second
clinical database.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
import uuid

from prometheus_client import Counter
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.request_context import ip_address_ctx, request_id_ctx, user_agent_ctx
from app.models import AuditLog, User


AUDIT_EVENTS = Counter(
    'gamucare_audit_events_total',
    'Audit events recorded by outcome and entity type.',
    ['outcome', 'entity_type'],
)

SECRET_KEYS = ('password', 'token', 'secret', 'authorization', 'cookie', 'hash')
CLINICAL_TEXT_KEYS = ('diagnosis', 'treatment', 'description', 'allergies', 'chronic_conditions', 'notes')
CONTACT_KEYS = ('address', 'phone')


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return sanitize_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _mask_email(value: str) -> str:
    local, separator, domain = value.partition('@')
    if not separator:
        return '[REDACTED]'
    visible = local[:1] if local else ''
    return f'{visible}***@{domain}'


def sanitize_mapping(values: dict[str, Any] | None) -> dict[str, Any] | None:
    """Redact sensitive values before writing them to the audit table."""
    if values is None:
        return None
    safe: dict[str, Any] = {}
    for key, value in values.items():
        lowered = key.lower()
        if any(token in lowered for token in SECRET_KEYS):
            safe[key] = '[REDACTED]'
        elif lowered == 'email' and isinstance(value, str):
            safe[key] = _mask_email(value)
        elif lowered in CONTACT_KEYS and value:
            safe[key] = '[REDACTED]'
        elif lowered in CLINICAL_TEXT_KEYS and value:
            safe[key] = '[CLINICAL DATA REDACTED]'
        else:
            safe[key] = _json_value(value)
    return safe


def snapshot_model(model: Any, *, include: set[str] | None = None) -> dict[str, Any] | None:
    """Return a privacy-aware snapshot of SQLAlchemy column attributes."""
    if model is None:
        return None
    mapper = inspect(model.__class__)
    values = {
        column.key: getattr(model, column.key)
        for column in mapper.columns
        if include is None or column.key in include
    }
    return sanitize_mapping(values)


def record_audit(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    outcome: str = 'success',
    commit: bool = False,
) -> AuditLog:
    """Append an immutable audit entry to the current transaction."""
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=outcome,
        request_id=request_id_ctx.get(),
        ip_address=ip_address_ctx.get(),
        user_agent=(user_agent_ctx.get() or '')[:255] or None,
        before_values=sanitize_mapping(before),
        after_values=sanitize_mapping(after),
        details=sanitize_mapping(details),
    )
    db.add(entry)
    AUDIT_EVENTS.labels(outcome=outcome, entity_type=entity_type).inc()
    if commit:
        db.commit()
    return entry
