"""Payment calculations for annual health-plan subscriptions.

Only the selected payment mode and the number of paid instalments are stored.
Amounts returned to the UI are derived from the agreed total, avoiding drift
between counters and money fields.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.models import PetPlanSubscription

MONEY = Decimal('0.01')


def money(value: Decimal) -> Decimal:
    """Round a decimal value to cents using commercial rounding."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def payment_values(subscription: PetPlanSubscription) -> dict[str, Decimal | int | str]:
    """Return a consistent payment summary for an API response or prompt."""
    total_installments = max(1, min(12, int(subscription.installments_total or 1)))
    paid_installments = max(0, min(total_installments, int(subscription.installments_paid or 0)))
    total_amount = money(Decimal(subscription.total_amount or 0))
    installment_amount = money(total_amount / Decimal(total_installments)) if total_installments else total_amount

    if paid_installments >= total_installments:
        amount_paid = total_amount
        status = 'paid'
    else:
        amount_paid = money(total_amount * Decimal(paid_installments) / Decimal(total_installments))
        status = 'installments_pending'

    return {
        'payment_mode': subscription.payment_mode,
        'payment_status': status,
        'installments_total': total_installments,
        'installments_paid': paid_installments,
        'total_amount': total_amount,
        'amount_paid': amount_paid,
        'amount_remaining': money(total_amount - amount_paid),
        'installment_amount': installment_amount,
    }
