"""Unit tests for the v0.6 preventive alert engine."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid

import pytest

from app.models import (
    ClinicalEvent,
    HealthPlan,
    Pet,
    PetPlanSubscription,
    PlanService,
    RiskAlert,
    SubscriptionService,
)
from app.services.risk_catalog import RISK_RULE_CATALOG
from app.services.risk_engine import matches, set_alert_status


class FakeSession:
    """Minimal SQLAlchemy session substitute for transition unit tests."""

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def make_pet() -> Pet:
    return Pet(
        id=uuid.uuid4(),
        external_id=f'TEST-{uuid.uuid4()}',
        owner_id=uuid.uuid4(),
        name='Paciente',
        species='dog',
        breed='Mestizo',
        birth_date=date(2018, 1, 1),
        sex='female',
        weight_kg=Decimal('20.0'),
        neutered=True,
    )


def add_event(pet: Pet, days_ago: int, text: str, weight: str | None = None) -> None:
    pet.clinical_events.append(
        ClinicalEvent(
            id=uuid.uuid4(),
            external_id=f'EVT-{uuid.uuid4()}',
            event_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
            event_type='consultation',
            title=text,
            description=text,
            weight_kg=Decimal(weight) if weight else None,
            visible_to_owner=True,
        )
    )


def test_recurrence_rule_requires_two_recent_events() -> None:
    pet = make_pet()
    add_event(pet, 100, 'Otitis externa')
    matched, evidence = matches(
        pet,
        {'history_contains': ['otitis'], 'history_min_occurrences': 2, 'history_lookback_months': 24},
    )
    assert matched is False
    add_event(pet, 20, 'Nuevo episodio de otitis')
    matched, evidence = matches(
        pet,
        {'history_contains': ['otitis'], 'history_min_occurrences': 2, 'history_lookback_months': 24},
    )
    assert matched is True
    assert evidence['matched_event_count'] == 2


def test_recurrence_rule_ignores_events_outside_lookback() -> None:
    pet = make_pet()
    add_event(pet, 900, 'Otitis antigua')
    add_event(pet, 10, 'Otitis reciente')
    matched, evidence = matches(
        pet,
        {'history_contains': ['otitis'], 'history_min_occurrences': 2, 'history_lookback_months': 12},
    )
    assert matched is False
    assert evidence['matched_event_count'] == 1


def test_weight_change_rule_detects_ten_percent_gain() -> None:
    pet = make_pet()
    add_event(pet, 120, 'Control de peso', weight='18.0')
    pet.weight_kg = Decimal('20.0')
    matched, evidence = matches(
        pet,
        {'weight_change_pct_gte': 10, 'weight_lookback_months': 6, 'minimum_weight_records': 2},
    )
    assert matched is True
    assert evidence['weight_change_pct'] > 11


def test_overdue_service_rule_uses_active_plan() -> None:
    pet = make_pet()
    plan = HealthPlan(
        id=uuid.uuid4(), name='Plan', species='dog', lifecycle='active', description='Test',
        duration_months=12, price_monthly=Decimal('10'), price_single=Decimal('100'),
    )
    service_definition = PlanService(
        id=uuid.uuid4(), health_plan=plan, name='Vacuna anual', service_type='vaccination',
        service_mode='limited', included_quantity=1, mandatory=True, display_order=1,
    )
    subscription = PetPlanSubscription(
        id=uuid.uuid4(), pet=pet, health_plan=plan, start_date=date.today() - timedelta(days=100),
        end_date=date.today() + timedelta(days=200), status='active', total_amount=Decimal('100'),
    )
    subscription.services.append(
        SubscriptionService(
            id=uuid.uuid4(), plan_service=service_definition, occurrence_number=1,
            scheduled_date=date.today() - timedelta(days=15), status='overdue',
        )
    )
    matched, evidence = matches(pet, {'overdue_service_types': ['vaccination'], 'overdue_days_min': 1})
    assert matched is True
    assert evidence['overdue_count'] == 1


def test_resolve_or_dismiss_requires_a_reason() -> None:
    alert = RiskAlert(
        id=uuid.uuid4(), pet_id=uuid.uuid4(), rule_code='TEST', title='Test', description='Test',
        severity='low', status='new', evidence={},
    )
    with pytest.raises(ValueError):
        set_alert_status(FakeSession(), alert, 'resolved', notes=None, changed_by_id=uuid.uuid4())


def test_review_records_transition() -> None:
    alert = RiskAlert(
        id=uuid.uuid4(), pet_id=uuid.uuid4(), rule_code='TEST', title='Test', description='Test',
        severity='low', status='new', evidence={},
    )
    session = FakeSession()
    set_alert_status(session, alert, 'reviewed', notes='Revisado por la clínica.', changed_by_id=uuid.uuid4())
    assert alert.status == 'reviewed'
    assert alert.review_notes == 'Revisado por la clínica.'
    assert len(session.added) == 1


def test_rule_catalog_codes_are_unique_and_sources_are_traceable() -> None:
    codes = [str(rule['code']) for rule in RISK_RULE_CATALOG]
    assert len(codes) == len(set(codes))
    sourced = [rule for rule in RISK_RULE_CATALOG if rule.get('source_url')]
    assert sourced
    assert all(str(rule['source_url']).startswith('https://') for rule in sourced)
