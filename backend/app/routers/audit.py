"""Read-only audit trail for clinic governance and incident review."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import AuditLog, User
from app.schemas import AuditLogResponse, AuditStatsResponse

router = APIRouter(prefix='/audit', tags=['audit'])


def _filtered_query(
    *,
    actor: str | None,
    action: str | None,
    entity_type: str | None,
    outcome: str | None,
    search: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    stmt = select(AuditLog)
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f'%{actor.strip()}%'))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if search:
        term = f'%{search.strip()}%'
        stmt = stmt.where(
            or_(
                AuditLog.action.ilike(term),
                AuditLog.entity_type.ilike(term),
                AuditLog.entity_id.ilike(term),
                AuditLog.request_id.ilike(term),
            )
        )
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    return stmt


@router.get('', response_model=list[AuditLogResponse])
def list_audit(
    actor: str | None = Query(default=None, max_length=255),
    action: str | None = Query(default=None, max_length=80),
    entity_type: str | None = Query(default=None, max_length=80),
    outcome: str | None = Query(default=None, max_length=30),
    search: str | None = Query(default=None, max_length=120),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> list[AuditLog]:
    stmt = _filtered_query(
        actor=actor,
        action=action,
        entity_type=entity_type,
        outcome=outcome,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )
    return list(db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit)).all())


@router.get('/stats', response_model=AuditStatsResponse)
def audit_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> AuditStatsResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    total = db.scalar(select(func.count(AuditLog.id))) or 0
    failed = db.scalar(select(func.count(AuditLog.id)).where(AuditLog.outcome != 'success')) or 0
    actors = db.scalar(select(func.count(func.distinct(AuditLog.actor_user_id))).where(AuditLog.actor_user_id.is_not(None))) or 0
    recent = db.scalar(select(func.count(AuditLog.id)).where(AuditLog.created_at >= cutoff)) or 0

    def grouped(column) -> dict[str, int]:
        rows = db.execute(select(column, func.count(AuditLog.id)).group_by(column).order_by(func.count(AuditLog.id).desc())).all()
        return {str(key or 'unknown'): int(count) for key, count in rows[:20]}

    return AuditStatsResponse(
        total_events=int(total),
        failed_events=int(failed),
        unique_actors=int(actors),
        events_last_24h=int(recent),
        by_action=grouped(AuditLog.action),
        by_entity=grouped(AuditLog.entity_type),
        by_outcome=grouped(AuditLog.outcome),
    )


@router.get('/export.csv')
def export_audit(
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    outcome: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> Response:
    """Export a bounded audit data set; clinical text remains redacted."""
    stmt = _filtered_query(
        actor=actor,
        action=action,
        entity_type=entity_type,
        outcome=outcome,
        search=None,
        date_from=date_from,
        date_to=date_to,
    )
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(5000)).all()
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow([
        'created_at', 'actor_email', 'action', 'entity_type', 'entity_id', 'outcome',
        'request_id', 'ip_address', 'before_values', 'after_values', 'details',
    ])
    for item in rows:
        writer.writerow([
            item.created_at.isoformat(), item.actor_email or '', item.action, item.entity_type,
            item.entity_id or '', item.outcome, item.request_id or '', item.ip_address or '',
            item.before_values or '', item.after_values or '', item.details or '',
        ])
    return Response(
        content=output.getvalue(),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="gamucare_audit.csv"'},
    )
