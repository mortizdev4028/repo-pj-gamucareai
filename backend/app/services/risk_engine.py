"""Deterministic and auditable preventive-risk engine.

The engine never diagnoses. It evaluates transparent conditions against the
current patient record, records the evidence that triggered each rule and
maintains the alert lifecycle without creating duplicates. RAG and the LLM are
applied later only to explain an alert that already exists.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any, Iterable
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AlertStatusHistory,
    Pet,
    PetPlanSubscription,
    RiskAlert,
    RiskRule,
    SubscriptionService,
)

ACTIVE_ALERT_STATUSES = {'new', 'reviewed'}
CLOSED_ALERT_STATUSES = {'resolved', 'dismissed'}


def age_years(birth_date: date, today: date | None = None) -> int:
    """Calculate completed years without relying on approximate day counts."""
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _normalise(value: str | None) -> str:
    """Normalise case and accents so fictitious free text is searched reliably."""
    if not value:
        return ''
    decomposed = unicodedata.normalize('NFKD', value.casefold())
    return ''.join(char for char in decomposed if not unicodedata.combining(char))


def _months_ago(months: int, today: date) -> date:
    """Return an approximate calendar boundary adequate for recurrence filters."""
    return today - timedelta(days=months * 30)


def _event_text(event: Any) -> str:
    return _normalise(' '.join(filter(None, [event.title, event.description, event.diagnosis, event.treatment])))


def _history_evidence(pet: Pet, conditions: dict[str, Any], today: date) -> tuple[bool, dict[str, Any]]:
    terms = [_normalise(item) for item in conditions.get('history_contains', [])]
    if not terms:
        return True, {}

    lookback_months = conditions.get('history_lookback_months')
    boundary = _months_ago(int(lookback_months), today) if lookback_months else None
    matched_events: list[dict[str, Any]] = []
    matched_terms: set[str] = set()

    for event in pet.clinical_events:
        event_day = event.event_date.date()
        if boundary and event_day < boundary:
            continue
        text = _event_text(event)
        event_matches = [term for term in terms if term and term in text]
        if event_matches:
            matched_terms.update(event_matches)
            matched_events.append(
                {
                    'event_id': str(event.id),
                    'date': event_day.isoformat(),
                    'title': event.title,
                    'terms': event_matches,
                }
            )

    # Chronic conditions and allergies are valid evidence for non-recurrent
    # rules, but they count as a single profile observation rather than as
    # repeated clinical episodes.
    profile_text = _normalise(' '.join(filter(None, [pet.allergies, pet.chronic_conditions])))
    profile_matches = [term for term in terms if term and term in profile_text]
    if profile_matches:
        matched_terms.update(profile_matches)

    minimum = int(conditions.get('history_min_occurrences', 1))
    occurrences = len(matched_events)
    if profile_matches and minimum <= 1:
        occurrences += 1

    evidence = {
        'matched_terms': sorted(matched_terms),
        'matched_history': sorted(matched_terms),
        'matched_event_count': len(matched_events),
        'matched_events': matched_events[:10],
        'profile_match': bool(profile_matches),
    }
    return occurrences >= minimum, evidence


def _weight_evidence(pet: Pet, conditions: dict[str, Any], today: date) -> tuple[bool, dict[str, Any]]:
    if 'weight_change_pct_gte' not in conditions and 'weight_change_pct_lte' not in conditions:
        return True, {}

    lookback_months = int(conditions.get('weight_lookback_months', 6))
    boundary = _months_ago(lookback_months, today)
    records: list[tuple[date, float, str]] = []
    for event in pet.clinical_events:
        if event.weight_kg is not None and event.event_date.date() >= boundary:
            records.append((event.event_date.date(), float(event.weight_kg), str(event.id)))
    records.append((today, float(Decimal(pet.weight_kg)), 'current'))
    records.sort(key=lambda item: item[0])

    minimum = int(conditions.get('minimum_weight_records', 2))
    if len(records) < minimum:
        return False, {'weight_records': len(records), 'lookback_months': lookback_months}

    first_date, first_weight, _ = records[0]
    last_date, last_weight, _ = records[-1]
    if first_weight <= 0:
        return False, {'weight_records': len(records), 'lookback_months': lookback_months}
    change_pct = round(((last_weight - first_weight) / first_weight) * 100, 2)
    matched = True
    if conditions.get('weight_change_pct_gte') is not None:
        matched = matched and change_pct >= float(conditions['weight_change_pct_gte'])
    if conditions.get('weight_change_pct_lte') is not None:
        matched = matched and change_pct <= float(conditions['weight_change_pct_lte'])

    return matched, {
        'weight_change_pct': change_pct,
        'weight_from_kg': round(first_weight, 2),
        'weight_to_kg': round(last_weight, 2),
        'weight_from_date': first_date.isoformat(),
        'weight_to_date': last_date.isoformat(),
        'weight_records': len(records),
        'lookback_months': lookback_months,
    }


def _overdue_evidence(pet: Pet, conditions: dict[str, Any], today: date) -> tuple[bool, dict[str, Any]]:
    service_types = set(conditions.get('overdue_service_types', []))
    if not service_types:
        return True, {}
    minimum_days = int(conditions.get('overdue_days_min', 1))
    overdue: list[dict[str, Any]] = []

    for subscription in pet.subscriptions:
        if subscription.status not in ('active', 'expiring'):
            continue
        for item in subscription.services:
            if item.plan_service.service_type not in service_types:
                continue
            if item.status in ('completed', 'cancelled', 'not_applicable') or item.scheduled_date is None:
                continue
            days = (today - item.scheduled_date).days
            if days >= minimum_days:
                overdue.append(
                    {
                        'service_id': str(item.id),
                        'name': item.plan_service.name,
                        'service_type': item.plan_service.service_type,
                        'scheduled_date': item.scheduled_date.isoformat(),
                        'days_overdue': days,
                        'subscription_id': str(subscription.id),
                    }
                )

    return bool(overdue), {'overdue_services': overdue[:12], 'overdue_count': len(overdue)}


def matches(pet: Pet, conditions: dict[str, Any], today: date | None = None) -> tuple[bool, dict[str, Any]]:
    """Evaluate all supported operators and return the observed evidence."""
    today = today or date.today()
    evidence: dict[str, Any] = {
        'species': pet.species,
        'breed': pet.breed,
        'age_years': age_years(pet.birth_date, today),
        'weight_kg': float(Decimal(pet.weight_kg)),
        'evaluated_on': today.isoformat(),
    }

    if conditions.get('species') and pet.species != conditions['species']:
        return False, evidence
    if conditions.get('min_age_years') is not None and evidence['age_years'] < conditions['min_age_years']:
        return False, evidence
    if conditions.get('max_age_years') is not None and evidence['age_years'] > conditions['max_age_years']:
        return False, evidence
    if conditions.get('min_weight_kg') is not None and evidence['weight_kg'] < conditions['min_weight_kg']:
        return False, evidence
    if conditions.get('max_weight_kg') is not None and evidence['weight_kg'] > conditions['max_weight_kg']:
        return False, evidence

    breeds = [_normalise(item) for item in conditions.get('breeds', [])]
    if breeds and _normalise(pet.breed) not in breeds:
        return False, evidence

    history_match, history_data = _history_evidence(pet, conditions, today)
    evidence.update(history_data)
    if not history_match:
        return False, evidence

    weight_match, weight_data = _weight_evidence(pet, conditions, today)
    evidence.update(weight_data)
    if not weight_match:
        return False, evidence

    overdue_match, overdue_data = _overdue_evidence(pet, conditions, today)
    evidence.update(overdue_data)
    if not overdue_match:
        return False, evidence

    return True, evidence


def _semantic_evidence(evidence: dict[str, Any]) -> str:
    """Ignore RAG metadata when deciding whether deterministic evidence changed."""
    clean = {key: value for key, value in evidence.items() if key not in {'rag_sources', 'rag_enriched_at'}}
    return json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str)


def _record_transition(
    db: Session,
    alert: RiskAlert,
    to_status: str,
    *,
    notes: str | None,
    changed_by_id: uuid.UUID | None = None,
) -> None:
    """Persist one status transition and update lifecycle timestamps."""
    from_status = alert.status
    if from_status == to_status:
        return
    alert.status = to_status
    now = datetime.now(timezone.utc)
    alert.updated_at = now
    if to_status == 'reviewed':
        alert.reviewed_at = now
        alert.reviewed_by_id = changed_by_id
    elif to_status == 'resolved':
        alert.resolved_at = now
        alert.resolution_reason = notes
    elif to_status == 'dismissed':
        alert.dismissed_at = now
        alert.resolution_reason = notes
    elif to_status == 'new':
        alert.resolved_at = None
        alert.dismissed_at = None
        alert.resolution_reason = None
    db.add(
        AlertStatusHistory(
            alert=alert,
            from_status=from_status,
            to_status=to_status,
            notes=notes,
            changed_by_id=changed_by_id,
        )
    )


def set_alert_status(
    db: Session,
    alert: RiskAlert,
    status: str,
    *,
    notes: str | None,
    changed_by_id: uuid.UUID | None,
) -> RiskAlert:
    """Apply a clinician action while keeping an immutable status history."""
    allowed = {'new', 'reviewed', 'resolved', 'dismissed'}
    if status not in allowed:
        raise ValueError(f'Estado de alerta no permitido: {status}')
    if status in {'resolved', 'dismissed'} and not notes:
        raise ValueError('Indica el motivo para cerrar o descartar el aviso')
    if status == 'reviewed':
        alert.review_notes = notes
    _record_transition(db, alert, status, notes=notes, changed_by_id=changed_by_id)
    alert.review_notes = notes or alert.review_notes
    return alert


def _pet_query() -> Any:
    return select(Pet).options(
        selectinload(Pet.clinical_events),
        selectinload(Pet.subscriptions)
        .selectinload(PetPlanSubscription.services)
        .selectinload(SubscriptionService.plan_service),
    )


def rebuild_alerts(
    db: Session,
    pet_ids: Iterable[uuid.UUID] | None = None,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Synchronise alerts with current evidence and return an audit summary."""
    today = today or date.today()
    now = datetime.now(timezone.utc)
    pet_stmt = _pet_query()
    pet_ids_list = list(pet_ids or [])
    if pet_ids_list:
        pet_stmt = pet_stmt.where(Pet.id.in_(pet_ids_list))
    pets = list(db.scalars(pet_stmt).unique().all())
    rules = list(db.scalars(select(RiskRule).where(RiskRule.is_active.is_(True))).all())

    summary: dict[str, Any] = {
        'pets_evaluated': len(pets),
        'rules_evaluated': len(rules),
        'created': 0,
        'updated': 0,
        'resolved': 0,
        'reopened': 0,
        'unchanged': 0,
        'active_alert_ids': [],
    }

    existing_alerts = list(
        db.scalars(
            select(RiskAlert).where(RiskAlert.pet_id.in_([pet.id for pet in pets]))
        ).all()
    ) if pets else []
    existing_by_key = {(alert.pet_id, alert.rule_code): alert for alert in existing_alerts}

    for pet in pets:
        for rule in rules:
            if rule.species and rule.species != pet.species:
                continue
            matched, evidence = matches(pet, rule.conditions, today)
            key = (pet.id, rule.code)
            existing = existing_by_key.get(key)

            if matched:
                if existing is None:
                    existing = RiskAlert(
                        pet_id=pet.id,
                        rule_code=rule.code,
                        title=rule.name,
                        description=rule.description or (
                            'Se ha detectado un factor preventivo que conviene revisar. '
                            'Este aviso no constituye un diagnóstico.'
                        ),
                        severity=rule.severity,
                        status='new',
                        evidence=evidence,
                        last_evaluated_at=now,
                        occurrence_count=1,
                    )
                    db.add(existing)
                    db.flush()
                    db.add(
                        AlertStatusHistory(
                            alert=existing,
                            from_status=None,
                            to_status='new',
                            notes='Aviso creado por el motor preventivo.',
                        )
                    )
                    existing_by_key[key] = existing
                    summary['created'] += 1
                else:
                    old_evidence = _semantic_evidence(existing.evidence or {})
                    new_evidence = _semantic_evidence(evidence)
                    changed = old_evidence != new_evidence or existing.severity != rule.severity or existing.title != rule.name
                    existing.title = rule.name
                    existing.description = rule.description or existing.description
                    existing.severity = rule.severity
                    existing.last_evaluated_at = now
                    if changed:
                        existing.evidence = evidence
                        existing.llm_explanation = None
                        existing.model_name = None
                        existing.updated_at = now
                        summary['updated'] += 1
                    else:
                        summary['unchanged'] += 1

                    if existing.status == 'resolved':
                        existing.occurrence_count += 1
                        _record_transition(
                            db,
                            existing,
                            'new',
                            notes='La condición preventiva vuelve a cumplirse.',
                        )
                        summary['reopened'] += 1
                    # A dismissed alert remains dismissed because it represents
                    # an explicit clinical decision. It can be reopened manually.

                if existing.status in ACTIVE_ALERT_STATUSES:
                    summary['active_alert_ids'].append(str(existing.id))
                continue

            if existing is not None:
                existing.last_evaluated_at = now
                if existing.status in ACTIVE_ALERT_STATUSES and rule.auto_resolve:
                    _record_transition(
                        db,
                        existing,
                        'resolved',
                        notes='La condición dejó de cumplirse en la última evaluación automática.',
                    )
                    summary['resolved'] += 1

    db.commit()
    return summary
