"""Preventive alert catalogue, lifecycle and RAG enrichment endpoints."""
from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prometheus_client import Counter
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import require_roles
from app.models import AlertStatusHistory, Pet, RiskAlert, RiskRule, User
from app.schemas import (
    AlertActionRequest,
    AlertHistoryResponse,
    AlertRebuildResponse,
    AlertResponse,
    AlertStatsResponse,
    RiskRuleResponse,
)
from app.services.alert_enrichment import enrich_alerts
from app.services.audit import record_audit, snapshot_model
from app.services.risk_engine import ACTIVE_ALERT_STATUSES, rebuild_alerts, set_alert_status

router = APIRouter(prefix='/alerts', tags=['alerts'])
ALERT_REBUILDS = Counter('gamucare_alert_rebuilds_total', 'Preventive alert rebuild executions')
ALERT_TRANSITIONS = Counter(
    'gamucare_alert_transitions_total',
    'Manual preventive alert status changes',
    ['to_status'],
)


def _rule_map(db: Session, alerts: list[RiskAlert]) -> dict[str, RiskRule]:
    codes = {alert.rule_code for alert in alerts}
    if not codes:
        return {}
    return {rule.code: rule for rule in db.scalars(select(RiskRule).where(RiskRule.code.in_(codes))).all()}


def _response(alert: RiskAlert, rule: RiskRule | None = None) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        pet_id=alert.pet_id,
        pet_name=alert.pet.name if alert.pet else None,
        breed=alert.pet.breed if alert.pet else None,
        species=alert.pet.species if alert.pet else None,
        rule_code=alert.rule_code,
        title=alert.title,
        description=alert.description,
        severity=alert.severity,
        status=alert.status,
        evidence=alert.evidence or {},
        llm_explanation=alert.llm_explanation,
        model_name=alert.model_name,
        generated_at=alert.generated_at,
        updated_at=alert.updated_at,
        last_evaluated_at=alert.last_evaluated_at,
        occurrence_count=alert.occurrence_count,
        reviewed_at=alert.reviewed_at,
        reviewed_by_id=alert.reviewed_by_id,
        review_notes=alert.review_notes,
        resolved_at=alert.resolved_at,
        dismissed_at=alert.dismissed_at,
        resolution_reason=alert.resolution_reason,
        history=[AlertHistoryResponse.model_validate(item) for item in alert.status_history],
        rule=RiskRuleResponse.model_validate(rule) if rule else None,
    )


def _alert_query():
    return select(RiskAlert).options(
        selectinload(RiskAlert.pet),
        selectinload(RiskAlert.status_history),
    )


@router.get('', response_model=list[AlertResponse])
def list_alerts(
    alert_status: str | None = Query(default=None, alias='status'),
    severity: str | None = None,
    species: str | None = None,
    category: str | None = None,
    rule_code: str | None = None,
    pet_name: str | None = None,
    active_only: bool = False,
    recurrent_only: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('clinic', 'staff')),
) -> list[AlertResponse]:
    """Return filtered alerts with source, evidence and status history."""
    stmt = _alert_query().join(Pet)
    if alert_status:
        stmt = stmt.where(RiskAlert.status == alert_status)
    if severity:
        stmt = stmt.where(RiskAlert.severity == severity)
    if species:
        stmt = stmt.where(Pet.species == species)
    if rule_code:
        stmt = stmt.where(RiskAlert.rule_code == rule_code)
    if pet_name:
        stmt = stmt.where(func.lower(Pet.name).contains(pet_name.casefold()))
    if active_only:
        stmt = stmt.where(RiskAlert.status.in_(ACTIVE_ALERT_STATUSES))
    if recurrent_only:
        stmt = stmt.where(RiskAlert.occurrence_count > 1)
    if date_from:
        stmt = stmt.where(RiskAlert.generated_at >= date_from)
    if date_to:
        stmt = stmt.where(RiskAlert.generated_at <= date_to)
    if category:
        stmt = stmt.join(RiskRule, RiskRule.code == RiskAlert.rule_code).where(RiskRule.category == category)
    stmt = stmt.order_by(RiskAlert.generated_at.desc())

    alerts = list(db.scalars(stmt).unique().all())
    rules = _rule_map(db, alerts)
    return [_response(alert, rules.get(alert.rule_code)) for alert in alerts]


@router.get('/stats', response_model=AlertStatsResponse)
def alert_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('clinic', 'staff')),
) -> AlertStatsResponse:
    """Return compact statistics for the alert dashboard."""
    alerts = list(db.scalars(_alert_query()).unique().all())
    rules = _rule_map(db, alerts)
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_species: dict[str, int] = {}
    for alert in alerts:
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        category = rules.get(alert.rule_code).category if rules.get(alert.rule_code) else 'general'
        by_category[category] = by_category.get(category, 0) + 1
        species = alert.pet.species if alert.pet else 'unknown'
        by_species[species] = by_species.get(species, 0) + 1
    counts = {value: sum(1 for alert in alerts if alert.status == value) for value in ('new', 'reviewed', 'resolved', 'dismissed')}
    return AlertStatsResponse(
        total=len(alerts),
        active=counts['new'] + counts['reviewed'],
        new=counts['new'],
        reviewed=counts['reviewed'],
        resolved=counts['resolved'],
        dismissed=counts['dismissed'],
        by_severity=by_severity,
        by_category=by_category,
        by_species=by_species,
        recurrent=sum(1 for alert in alerts if alert.occurrence_count > 1),
    )


@router.get('/rules', response_model=list[RiskRuleResponse])
def list_rules(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('clinic', 'staff')),
) -> list[RiskRule]:
    """Expose the auditable rule catalogue and its documentary sources."""
    stmt = select(RiskRule).order_by(RiskRule.category, RiskRule.name)
    if active_only:
        stmt = stmt.where(RiskRule.is_active.is_(True))
    return list(db.scalars(stmt).all())


@router.get('/{alert_id}', response_model=AlertResponse)
def get_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('clinic', 'staff')),
) -> AlertResponse:
    alert = db.scalar(_alert_query().where(RiskAlert.id == alert_id))
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Aviso no encontrado')
    rule = db.scalar(select(RiskRule).where(RiskRule.code == alert.rule_code))
    return _response(alert, rule)


@router.patch('/{alert_id}/status', response_model=AlertResponse)
def update_alert_status(
    alert_id: uuid.UUID,
    payload: AlertActionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> AlertResponse:
    """Review, resolve, dismiss or reopen an alert with an audit record."""
    alert = db.scalar(_alert_query().where(RiskAlert.id == alert_id))
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Aviso no encontrado')
    before = snapshot_model(alert)
    try:
        set_alert_status(
            db,
            alert,
            payload.status,
            notes=payload.notes,
            changed_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.flush()
    record_audit(
        db, actor=user, action='alert.status_changed', entity_type='risk_alert', entity_id=alert.id,
        before=before, after=snapshot_model(alert), details={'to_status': payload.status},
    )
    db.commit()
    ALERT_TRANSITIONS.labels(to_status=payload.status).inc()
    refreshed = db.scalar(_alert_query().where(RiskAlert.id == alert_id))
    rule = db.scalar(select(RiskRule).where(RiskRule.code == refreshed.rule_code))
    return _response(refreshed, rule)


@router.post('/rebuild', response_model=AlertRebuildResponse)
async def rebuild(
    enrich: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> AlertRebuildResponse:
    """Re-evaluate all rules and optionally enrich changed active alerts with RAG."""
    summary = rebuild_alerts(db)
    ALERT_REBUILDS.inc()
    enrichment = {'enriched': 0, 'without_context': 0, 'failed': 0}
    if enrich and summary['active_alert_ids']:
        enrichment = await enrich_alerts(
            db,
            only_missing=True,
            alert_ids=summary['active_alert_ids'],
        )
    record_audit(
        db, actor=user, action='alerts.rebuilt', entity_type='risk_alert',
        details={**summary, **enrichment}, commit=True,
    )
    return AlertRebuildResponse(**summary, **enrichment)


@router.post('/enrich')
async def enrich(
    only_missing: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> dict[str, int]:
    """Ground active preventive alerts with Qdrant context and Ollama."""
    result = await enrich_alerts(db, only_missing=only_missing)
    record_audit(
        db, actor=user, action='alerts.enriched', entity_type='risk_alert', details=result, commit=True,
    )
    return result
