"""Formal evaluation tests introduced in v0.11.0."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    ClinicalEvent,
    HealthPlan,
    Owner,
    Pet,
    PetPlanSubscription,
    RagDocument,
    RiskRule,
    SystemEvaluationRun,
    User,
)
from app.services.system_evaluation import SystemEvaluator
from app.version import APP_VERSION


ROOT = Path('/app') if Path('/app/data').exists() else Path(__file__).resolve().parents[2]


def evaluator() -> SystemEvaluator:
    value = SystemEvaluator()
    value.acceptance_path = ROOT / 'data/evaluation/acceptance_criteria_v1.json'
    value.alert_path = ROOT / 'data/evaluation/alert_cases_v1.json'
    value.reports_path = ROOT / 'data/reports'
    return value


def database() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return Session(engine)


def seed_minimum_mvp(db: Session) -> None:
    clinic = User(email='clinic@eval.test', password_hash='x', role='clinic')
    staff = User(email='staff@eval.test', password_hash='x', role='staff')
    owner_user = User(email='owner@eval.test', password_hash='x', role='owner')
    technical = User(email='technical@eval.test', password_hash='x', role='technical')
    owner = Owner(
        user=owner_user,
        external_id='OWNER-EVAL',
        first_name='Ana',
        last_name='Evaluacion',
        phone='600000000',
        email='owner@eval.test',
        address='Madrid',
        is_active=True,
    )
    dog_plan = HealthPlan(
        name='LifeCare Dog Eval', species='dog', lifecycle='active', description='Plan de prueba',
        duration_months=12, price_monthly=Decimal('10'), price_single=Decimal('100'), is_active=True,
    )
    cat_plan = HealthPlan(
        name='LifeCare Cat Eval', species='cat', lifecycle='active', description='Plan de prueba',
        duration_months=12, price_monthly=Decimal('10'), price_single=Decimal('100'), is_active=True,
    )
    pet = Pet(
        owner=owner,
        external_id='PET-EVAL',
        name='Luna',
        species='dog',
        breed='Mestizo',
        birth_date=date(2020, 1, 1),
        sex='female',
        weight_kg=Decimal('18.0'),
        neutered=True,
        is_active=True,
    )
    pet.clinical_events.append(
        ClinicalEvent(
            external_id='EVENT-EVAL',
            event_date=datetime.now(timezone.utc),
            event_type='checkup',
            title='Revision',
            description='Evento de evaluacion',
            visible_to_owner=True,
        )
    )
    pet.subscriptions.append(
        PetPlanSubscription(
            health_plan=dog_plan,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=355),
            status='active',
            renewal_status='not_requested',
            payment_mode='single',
            installments_total=1,
            installments_paid=1,
            total_amount=Decimal('100'),
        )
    )
    db.add_all([
        clinic,
        staff,
        technical,
        owner,
        dog_plan,
        cat_plan,
        pet,
        RiskRule(
            code='EVAL-RULE', name='Regla evaluacion', description='Prueba', category='general',
            conditions={'min_age_years': 1}, severity='low', source='Fuente',
            source_url='https://example.test/source', is_active=True,
        ),
        RagDocument(
            title='Documento', source_name='Fuente', category='general', file_hash='a' * 64,
            ingestion_status='completed', trust_level='official', tags=[],
        ),
    ])
    db.commit()


def test_alert_dataset_has_perfect_expected_accuracy() -> None:
    result = evaluator().evaluate_alerts()
    assert result['total'] == 8
    assert result['accuracy'] == 1.0
    assert result['precision'] == 1.0
    assert result['recall'] == 1.0


def test_acceptance_dataset_is_versioned_and_fully_automated() -> None:
    criteria = evaluator().load_acceptance_criteria()
    assert len(criteria) == 16
    assert len({item['id'] for item in criteria}) == len(criteria)
    assert all(item['check'] for item in criteria)


def test_minimum_seed_passes_acceptance_criteria(monkeypatch) -> None:
    from app.services import system_evaluation
    monkeypatch.setattr(system_evaluation.settings, 'jwt_secret', 'a' * 48)
    with database() as db:
        seed_minimum_mvp(db)
        result = evaluator().evaluate_acceptance(db)
        assert result['total'] == 16
        assert result['passed'] == 16
        assert result['failed'] == 0


def test_security_evaluation_checks_redaction_and_policy(monkeypatch) -> None:
    from app.services import system_evaluation
    monkeypatch.setattr(system_evaluation.settings, 'jwt_secret', 'b' * 48)
    result = evaluator().evaluate_security()
    assert result['total'] >= 5
    assert result['failed'] == 0


def test_markdown_report_contains_version_and_interpretation() -> None:
    value = evaluator()
    sections = {
        'acceptance': {'passed': 16, 'total': 16, 'failed': 0, 'pass_rate': 1.0, 'cases': []},
        'alerts': {'passed': 8, 'total': 8, 'failed': 0, 'accuracy': 1.0, 'precision': 1.0, 'recall': 1.0, 'cases': []},
        'security': {'passed': 5, 'total': 5, 'failed': 0, 'pass_rate': 1.0, 'cases': []},
        'tests': {'status': 'passed', 'passed': 53, 'total': 53, 'coverage_percent': 60.0},
        'vetia': {'status': 'completed', 'metrics': {'retrieval_hit_rate': 0.9}},
        'performance': {'status': 'completed', 'success_rate': 1.0, 'latency_p95_ms': 10.0},
    }
    report = value.build_report(sections, 99.0, True)
    assert APP_VERSION in report
    assert 'APTO' in report
    assert 'validacion veterinaria humana' in report


def test_system_evaluation_run_can_be_persisted() -> None:
    with database() as db:
        run = SystemEvaluationRun(app_version=APP_VERSION, status='completed', tests_total=1, tests_passed=1)
        db.add(run)
        db.commit()
        db.refresh(run)
        assert run.id is not None
        assert run.app_version == APP_VERSION
