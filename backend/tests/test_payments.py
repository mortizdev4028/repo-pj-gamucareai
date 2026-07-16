"""Unit tests for plan payment summaries."""
from decimal import Decimal

from app.models import PetPlanSubscription
from app.services.payments import payment_values


def test_installment_summary_is_consistent() -> None:
    subscription = PetPlanSubscription(
        payment_mode='installments',
        installments_total=12,
        installments_paid=3,
        total_amount=Decimal('600.00'),
    )
    summary = payment_values(subscription)
    assert summary['payment_status'] == 'installments_pending'
    assert summary['installment_amount'] == Decimal('50.00')
    assert summary['amount_paid'] == Decimal('150.00')
    assert summary['amount_remaining'] == Decimal('450.00')


def test_last_installment_marks_plan_as_paid() -> None:
    subscription = PetPlanSubscription(
        payment_mode='installments',
        installments_total=6,
        installments_paid=6,
        total_amount=Decimal('420.00'),
    )
    summary = payment_values(subscription)
    assert summary['payment_status'] == 'paid'
    assert summary['amount_paid'] == Decimal('420.00')
    assert summary['amount_remaining'] == Decimal('0.00')
