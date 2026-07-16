"""Tests for role-aware dashboard calculations introduced in v0.8.0."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    HealthPlan, Owner, Pet, PetPlanSubscription, PlanInstallment, PlanService,
    RiskAlert, SubscriptionService, User,
)
from app.services.dashboard import build_dashboard, completion_percentage, trend_months


def _database() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_dashboard(db: Session) -> tuple[User, User]:
    owner_user = User(email='owner@example.test', password_hash='x', role='owner')
    clinic_user = User(email='clinic@example.test', password_hash='x', role='clinic')
    owner = Owner(
        user=owner_user, external_id='OWNER-1', first_name='Ana', last_name='Prueba',
        phone='600000001', email='owner@example.test', address='Madrid', is_active=True,
    )
    other_owner = Owner(
        external_id='OWNER-2', first_name='Luis', last_name='Externo', phone='600000002',
        email='other@example.test', address='Madrid', is_active=True,
    )
    plan = HealthPlan(
        name='LifeCare prueba', species='dog', lifecycle='active', description='Plan de prueba',
        duration_months=12, price_monthly=Decimal('10.00'), price_single=Decimal('100.00'), is_active=True,
    )
    service_definition = PlanService(
        health_plan=plan, name='Revision', service_type='checkup', service_mode='limited',
        included_quantity=1, display_order=1,
    )
    pet = Pet(
        owner=owner, external_id='PET-1', name='Luna', species='dog', breed='Mestizo',
        birth_date=date(2020, 1, 1), sex='female', weight_kg=Decimal('15.0'),
        neutered=True, is_active=True,
    )
    other_pet = Pet(
        owner=other_owner, external_id='PET-2', name='Max', species='dog', breed='Beagle',
        birth_date=date(2021, 1, 1), sex='male', weight_kg=Decimal('12.0'),
        neutered=True, is_active=True,
    )
    subscription = PetPlanSubscription(
        pet=pet, health_plan=plan, start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=335), status='active', renewal_status='not_requested',
        payment_mode='installments', installments_total=2, installments_paid=1,
        total_amount=Decimal('120.00'),
    )
    subscription.services.append(SubscriptionService(
        plan_service=service_definition, occurrence_number=1, scheduled_date=date.today() - timedelta(days=2),
        status='overdue',
    ))
    subscription.installments.extend([
        PlanInstallment(installment_number=1, due_date=date.today() - timedelta(days=30), amount=Decimal('60.00'), status='paid', paid_at=datetime.now(timezone.utc)),
        PlanInstallment(installment_number=2, due_date=date.today() + timedelta(days=30), amount=Decimal('60.00'), status='pending'),
    ])
    pet.risk_alerts.append(RiskAlert(
        rule_code='TEST', title='Aviso de prueba', description='Seguimiento', severity='medium', status='new', evidence={},
    ))
    other_subscription = PetPlanSubscription(
        pet=other_pet, health_plan=plan, start_date=date.today(), end_date=date.today() + timedelta(days=364),
        status='active', renewal_status='not_requested', payment_mode='single', installments_total=1,
        installments_paid=1, total_amount=Decimal('100.00'),
    )
    other_subscription.installments.append(PlanInstallment(
        installment_number=1, due_date=date.today(), amount=Decimal('100.00'), status='paid', paid_at=datetime.now(timezone.utc),
    ))
    db.add_all([clinic_user, owner, other_owner, plan, service_definition, pet, other_pet])
    db.commit()
    db.refresh(owner_user)
    db.refresh(clinic_user)
    return owner_user, clinic_user


def test_trend_months_is_chronological_and_bounded() -> None:
    months = trend_months(3, today=date(2026, 7, 14))
    assert months == [date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1)]
    assert len(trend_months(99, today=date(2026, 7, 14))) == 24


def test_completion_ignores_informational_benefits() -> None:
    services = [
        SubscriptionService(status='completed'),
        SubscriptionService(status='pending'),
        SubscriptionService(status='not_applicable'),
    ]
    assert completion_percentage(services) == 50.0


def test_owner_dashboard_is_restricted_to_owned_pets() -> None:
    with _database() as db:
        owner_user, _ = _seed_dashboard(db)
        result = build_dashboard(db, owner_user, months=6)
        assert result.pets_total == 1
        assert result.plans_active == 1
        assert result.pets_with_alerts == 1
        assert len(result.owner_pets) == 1
        assert result.owner_pets[0].pet_name == 'Luna'


def test_clinic_dashboard_aggregates_financial_data() -> None:
    with _database() as db:
        _, clinic_user = _seed_dashboard(db)
        result = build_dashboard(db, clinic_user, months=6)
        assert result.pets_total == 2
        assert result.financial.total_committed == Decimal('220.00')
        assert result.financial.amount_collected == Decimal('160.00')
        assert result.financial.amount_outstanding == Decimal('60.00')


def test_dashboard_species_filter_is_applied() -> None:
    with _database() as db:
        _, clinic_user = _seed_dashboard(db)
        result = build_dashboard(db, clinic_user, months=6, species='cat')
        assert result.pets_total == 0
        assert result.plans_active == 0
