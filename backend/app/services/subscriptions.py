"""Business rules for assigning and maintaining health-plan subscriptions.

The module keeps plan lifecycle rules out of the HTTP routers. It is used by
manual assignments, plan changes, renewals and the demonstration data loader.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HealthPlan, Pet, PetPlanSubscription, PlanInstallment, PlanService, SubscriptionService
from app.services.payments import money

OPEN_STATUSES = ('active', 'expiring', 'scheduled')


def add_months(value: date, months: int) -> date:
    """Add whole months without producing invalid dates."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def status_for_dates(start_date: date, end_date: date, *, today: date | None = None) -> str:
    """Calculate the visible lifecycle state of a non-cancelled subscription."""
    current = today or date.today()
    if start_date > current:
        return 'scheduled'
    if end_date < current:
        return 'expired'
    if end_date <= current + timedelta(days=45):
        return 'expiring'
    return 'active'


def refresh_subscription_status(subscription: PetPlanSubscription, *, today: date | None = None) -> bool:
    """Refresh lifecycle and pending service states, returning whether data changed."""
    if subscription.status == 'cancelled':
        return False

    changed = False
    calculated = status_for_dates(subscription.start_date, subscription.end_date, today=today)
    if subscription.status != calculated:
        subscription.status = calculated
        changed = True

    current = today or date.today()
    for service in subscription.services:
        if service.status in ('completed', 'not_applicable', 'cancelled') or service.scheduled_date is None:
            continue
        if subscription.status == 'scheduled':
            expected = 'pending'
        elif service.scheduled_date < current:
            expected = 'overdue'
        elif service.scheduled_date <= current + timedelta(days=30):
            expected = 'upcoming'
        else:
            expected = 'pending'
        if service.status != expected:
            service.status = expected
            changed = True

    for installment in subscription.installments:
        if installment.status in ('paid', 'cancelled'):
            continue
        expected = 'overdue' if installment.due_date < current else 'pending'
        if installment.status != expected:
            installment.status = expected
            changed = True
    return changed


def _service_date(plan_service: PlanService, start_date: date, duration_months: int, occurrence: int, quantity: int) -> date:
    """Place a plan benefit within the subscription period using simple rules.

    Periodic services follow their configured interval. Multi-use benefits with
    no explicit frequency are spread across the year. One-off preventive tests
    are placed after the first month so the clinic can reschedule them later.
    """
    if plan_service.frequency_months:
        months = plan_service.frequency_months * (occurrence - 1)
    elif quantity > 1:
        months = round((duration_months - 1) * (occurrence - 1) / max(1, quantity - 1))
    elif plan_service.service_type in ('administrative', 'vaccination', 'deworming'):
        months = 0
    else:
        months = min(1, max(0, duration_months - 1))
    return add_months(start_date, months)


def generate_subscription_services(subscription: PetPlanSubscription, *, today: date | None = None) -> None:
    """Create concrete service occurrences from the selected plan catalogue."""
    current = today or date.today()
    duration = subscription.health_plan.duration_months
    for definition in sorted(subscription.health_plan.services, key=lambda item: item.display_order):
        if definition.service_mode in ('unlimited', 'discount', 'benefit'):
            subscription.services.append(
                SubscriptionService(
                    plan_service=definition,
                    occurrence_number=1,
                    scheduled_date=None,
                    status='not_applicable',
                    notes=(
                        'Prestacion disponible durante toda la vigencia del plan.'
                        if definition.service_mode == 'unlimited'
                        else definition.notes
                    ),
                )
            )
            continue

        quantity = max(1, int(definition.included_quantity or 1))
        for occurrence in range(1, quantity + 1):
            scheduled = _service_date(definition, subscription.start_date, duration, occurrence, quantity)
            if subscription.start_date > current:
                service_status = 'pending'
            elif scheduled < current:
                service_status = 'overdue'
            elif scheduled <= current + timedelta(days=30):
                service_status = 'upcoming'
            else:
                service_status = 'pending'
            subscription.services.append(
                SubscriptionService(
                    plan_service=definition,
                    occurrence_number=occurrence,
                    scheduled_date=scheduled,
                    status=service_status,
                )
            )


def generate_installments(subscription: PetPlanSubscription, *, today: date | None = None) -> None:
    """Create the detailed payment schedule for a subscription.

    The stored counters remain a compact summary, while this schedule allows the
    clinic and owner to see each due date and correct individual payments.
    """
    current = today or date.today()
    total = max(1, min(12, int(subscription.installments_total or 1)))
    paid = max(0, min(total, int(subscription.installments_paid or 0)))
    total_amount = Decimal(subscription.total_amount or 0)
    regular_amount = money(total_amount / Decimal(total))
    existing = {item.installment_number: item for item in list(subscription.installments)}

    for number in range(1, total + 1):
        months = 0 if total == 1 else ((number - 1) * subscription.health_plan.duration_months) // total
        due_date = add_months(subscription.start_date, months)
        amount = regular_amount if number < total else money(total_amount - regular_amount * Decimal(total - 1))
        is_paid = number <= paid
        installment = existing.pop(number, None)
        if installment is None:
            installment = PlanInstallment(installment_number=number, due_date=due_date, amount=amount)
            subscription.installments.append(installment)
        installment.due_date = due_date
        installment.amount = amount
        installment.status = 'paid' if is_paid else ('overdue' if due_date < current else 'pending')
        if is_paid:
            installment.paid_at = installment.paid_at or datetime.combine(
                min(due_date, current), datetime.min.time(), tzinfo=timezone.utc
            )
        else:
            installment.paid_at = None

    for obsolete in existing.values():
        subscription.installments.remove(obsolete)


def update_installment_counters(subscription: PetPlanSubscription) -> None:
    """Synchronise the compact payment counter with the detailed schedule."""
    subscription.installments_paid = sum(1 for item in subscription.installments if item.status == 'paid')


def payment_terms(plan: HealthPlan, payment_mode: str, installments_total: int, installments_paid: int) -> dict:
    """Validate payment choices and return fields stored in the subscription."""
    if payment_mode == 'single':
        return {
            'payment_mode': 'single',
            'installments_total': 1,
            'installments_paid': 1,
            'total_amount': Decimal(plan.price_single),
        }
    if not 2 <= installments_total <= 12:
        raise ValueError('El pago a plazos debe tener entre 2 y 12 cuotas')
    if not 0 <= installments_paid <= installments_total:
        raise ValueError('Las cuotas pagadas deben estar entre cero y el total acordado')
    return {
        'payment_mode': 'installments',
        'installments_total': installments_total,
        'installments_paid': installments_paid,
        'total_amount': Decimal(plan.price_monthly) * Decimal('12'),
    }


def find_open_subscription(db: Session, pet_id, *, excluding_id=None) -> PetPlanSubscription | None:
    """Return the current or scheduled subscription for a patient, if any."""
    stmt = select(PetPlanSubscription).where(
        PetPlanSubscription.pet_id == pet_id,
        PetPlanSubscription.status.in_(OPEN_STATUSES),
    )
    if excluding_id is not None:
        stmt = stmt.where(PetPlanSubscription.id != excluding_id)
    subscriptions = list(db.scalars(stmt).all())
    for item in subscriptions:
        refresh_subscription_status(item)
    return next((item for item in subscriptions if item.status in OPEN_STATUSES), None)


def create_subscription(
    db: Session,
    *,
    pet: Pet,
    plan: HealthPlan,
    start_date: date,
    payment_mode: str,
    installments_total: int,
    installments_paid: int,
    renewed_from_id=None,
) -> PetPlanSubscription:
    """Create a subscription and all service occurrences, without committing."""
    if not pet.is_active:
        raise ValueError('No se puede asignar un plan a una mascota dada de baja')
    if plan.species != pet.species:
        raise ValueError('El plan seleccionado no corresponde a la especie de la mascota')
    if not plan.is_active:
        raise ValueError('El plan seleccionado no esta disponible')

    end_date = add_months(start_date, plan.duration_months) - timedelta(days=1)
    subscription = PetPlanSubscription(
        pet=pet,
        health_plan=plan,
        start_date=start_date,
        end_date=end_date,
        status=status_for_dates(start_date, end_date),
        renewal_status='not_requested',
        renewed_from_id=renewed_from_id,
        **payment_terms(plan, payment_mode, installments_total, installments_paid),
    )
    generate_subscription_services(subscription)
    generate_installments(subscription)
    db.add(subscription)
    return subscription


def cancel_subscription(
    subscription: PetPlanSubscription,
    *,
    cancellation_date: date,
    reason: str,
) -> None:
    """Cancel a subscription and invalidate only its unfinished services."""
    if subscription.status == 'cancelled':
        raise ValueError('La suscripcion ya esta cancelada')
    if cancellation_date < subscription.start_date:
        raise ValueError('La fecha de baja no puede ser anterior al inicio del plan')

    subscription.status = 'cancelled'
    subscription.cancelled_at = datetime.combine(cancellation_date, datetime.min.time(), tzinfo=timezone.utc)
    subscription.cancellation_reason = reason.strip()
    if cancellation_date < subscription.end_date:
        subscription.end_date = cancellation_date
    for service in subscription.services:
        if service.status not in ('completed', 'not_applicable'):
            service.status = 'cancelled'
            service.notes = reason.strip()
    for installment in subscription.installments:
        if installment.status != 'paid':
            installment.status = 'cancelled'
            installment.notes = reason.strip()
