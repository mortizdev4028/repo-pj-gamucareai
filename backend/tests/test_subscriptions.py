"""Unit tests for the health-plan lifecycle rules."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import HealthPlan, PetPlanSubscription, PlanService
from app.services.subscriptions import (
    cancel_subscription,
    generate_installments,
    generate_subscription_services,
    payment_terms,
    status_for_dates,
    update_installment_counters,
)


def _plan() -> HealthPlan:
    plan = HealthPlan(
        name='Plan de prueba',
        species='dog',
        lifecycle='active',
        description='Plan utilizado por las pruebas unitarias.',
        duration_months=12,
        price_monthly=Decimal('45.00'),
        price_single=Decimal('495.00'),
        is_active=True,
    )
    plan.services = [
        PlanService(
            name='Desparasitacion trimestral',
            service_type='deworming',
            service_mode='periodic',
            included_quantity=4,
            frequency_months=3,
            display_order=1,
        ),
        PlanService(
            name='Consultas ilimitadas',
            service_type='consultation',
            service_mode='unlimited',
            included_quantity=None,
            display_order=2,
        ),
    ]
    return plan


def test_status_distinguishes_scheduled_expiring_and_expired() -> None:
    today = date(2026, 7, 14)
    assert status_for_dates(today + timedelta(days=5), today + timedelta(days=365), today=today) == 'scheduled'
    assert status_for_dates(today - timedelta(days=300), today + timedelta(days=30), today=today) == 'expiring'
    assert status_for_dates(today - timedelta(days=400), today - timedelta(days=1), today=today) == 'expired'


def test_service_occurrences_are_created_from_catalogue() -> None:
    plan = _plan()
    subscription = PetPlanSubscription(
        health_plan=plan,
        start_date=date(2026, 7, 1),
        end_date=date(2027, 6, 30),
        status='active',
        renewal_status='not_requested',
        payment_mode='single',
        installments_total=1,
        installments_paid=1,
        total_amount=Decimal('495.00'),
    )
    generate_subscription_services(subscription, today=date(2026, 7, 14))
    periodic = [item for item in subscription.services if item.plan_service.service_mode == 'periodic']
    unlimited = [item for item in subscription.services if item.plan_service.service_mode == 'unlimited']
    assert len(periodic) == 4
    assert [item.scheduled_date.month for item in periodic] == [7, 10, 1, 4]
    assert len(unlimited) == 1
    assert unlimited[0].status == 'not_applicable'


def test_cancellation_preserves_completed_services() -> None:
    plan = _plan()
    subscription = PetPlanSubscription(
        health_plan=plan,
        start_date=date(2026, 7, 1),
        end_date=date(2027, 6, 30),
        status='active',
        renewal_status='not_requested',
        payment_mode='single',
        installments_total=1,
        installments_paid=1,
        total_amount=Decimal('495.00'),
    )
    generate_subscription_services(subscription, today=date(2026, 7, 14))
    subscription.services[0].status = 'completed'
    cancel_subscription(subscription, cancellation_date=date(2026, 7, 14), reason='Prueba de baja')
    assert subscription.status == 'cancelled'
    assert subscription.services[0].status == 'completed'
    assert all(item.status in ('completed', 'not_applicable', 'cancelled') for item in subscription.services)


def test_installment_terms_reject_more_than_twelve_payments() -> None:
    with pytest.raises(ValueError):
        payment_terms(_plan(), 'installments', 13, 0)


def test_detailed_installments_match_payment_summary() -> None:
    plan = _plan()
    subscription = PetPlanSubscription(
        health_plan=plan,
        start_date=date(2026, 7, 1),
        end_date=date(2027, 6, 30),
        status='active',
        renewal_status='not_requested',
        payment_mode='installments',
        installments_total=6,
        installments_paid=2,
        total_amount=Decimal('540.00'),
    )
    generate_installments(subscription, today=date(2026, 7, 14))
    assert len(subscription.installments) == 6
    assert sum(item.amount for item in subscription.installments) == Decimal('540.00')
    assert [item.status for item in subscription.installments[:2]] == ['paid', 'paid']
    subscription.installments[2].status = 'paid'
    update_installment_counters(subscription)
    assert subscription.installments_paid == 3
