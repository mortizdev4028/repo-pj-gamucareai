"""Role-aware dashboard aggregation for GamuCare AI.

The dashboard deliberately reuses the same relational data that powers the
operational screens. No figures are stored separately, so cards, charts and
exports cannot drift from subscriptions, instalments, services or alerts.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Pet, PetPlanSubscription, RiskAlert, SubscriptionService, User
from app.schemas import (
    DashboardFinancialSummary,
    DashboardOwnerPet,
    DashboardRankedItem,
    DashboardResponse,
    DashboardTrendPoint,
    DashboardUpcomingItem,
)
from app.services.payments import money
from app.services.subscriptions import refresh_subscription_status

MONTH_LABELS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')
OPEN_PLAN_STATUSES = {'active', 'expiring', 'scheduled'}
ACTIVE_ALERT_STATUSES = {'new', 'reviewed'}


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, offset: int) -> date:
    """Move to the first day of another month without external dependencies."""
    index = value.year * 12 + value.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def trend_months(month_count: int, *, today: date | None = None) -> list[date]:
    """Return chronological month starts ending in the current month."""
    current = _month_start(today or date.today())
    safe_count = max(1, min(24, month_count))
    return [_shift_month(current, offset) for offset in range(-(safe_count - 1), 1)]


def completion_percentage(services: list[SubscriptionService]) -> float:
    """Calculate completion while excluding informational plan benefits."""
    counted = [item for item in services if item.status not in {'not_applicable', 'cancelled'}]
    completed = sum(1 for item in counted if item.status == 'completed')
    return round(completed / len(counted) * 100, 1) if counted else 0.0


def _load_pets(db: Session, user: User, species: str | None) -> list[Pet]:
    stmt = (
        select(Pet)
        .options(
            selectinload(Pet.owner),
            selectinload(Pet.subscriptions).selectinload(PetPlanSubscription.health_plan),
            selectinload(Pet.subscriptions).selectinload(PetPlanSubscription.installments),
            selectinload(Pet.subscriptions)
            .selectinload(PetPlanSubscription.services)
            .selectinload(SubscriptionService.plan_service),
            selectinload(Pet.risk_alerts),
            selectinload(Pet.clinical_events),
        )
        .where(Pet.is_active.is_(True))
        .order_by(Pet.name)
    )
    if user.role == 'owner':
        if user.owner is None or not user.owner.is_active:
            return []
        stmt = stmt.where(Pet.owner_id == user.owner.id)
    if species:
        stmt = stmt.where(Pet.species == species)
    return list(db.scalars(stmt).unique().all())


def _ranked(counter: Counter[str], labels: dict[str, str] | None = None, limit: int = 6) -> list[DashboardRankedItem]:
    label_map = labels or {}
    return [
        DashboardRankedItem(key=key, label=label_map.get(key, key.replace('_', ' ').title()), count=count)
        for key, count in counter.most_common(limit)
    ]


def build_dashboard(
    db: Session,
    user: User,
    *,
    months: int = 6,
    species: str | None = None,
    plan_id: uuid.UUID | None = None,
) -> DashboardResponse:
    """Build one consistent dashboard response scoped to the current user."""
    today = date.today()
    now = datetime.now(timezone.utc)
    month_starts = trend_months(months, today=today)
    trend_start = month_starts[0]
    month_keys = [item.strftime('%Y-%m') for item in month_starts]

    pets = _load_pets(db, user, species)
    changed = False
    for pet in pets:
        for subscription in pet.subscriptions:
            changed = refresh_subscription_status(subscription, today=today) or changed
    if changed:
        db.commit()

    subscriptions: list[PetPlanSubscription] = []
    scoped_pets: list[Pet] = []
    for pet in pets:
        selected = [item for item in pet.subscriptions if plan_id is None or item.health_plan_id == plan_id]
        if plan_id is None or selected:
            scoped_pets.append(pet)
        subscriptions.extend(selected)

    services = [service for subscription in subscriptions for service in subscription.services]
    installments = [item for subscription in subscriptions for item in subscription.installments]
    alerts = [alert for pet in scoped_pets for alert in pet.risk_alerts]
    clinical_events = [event for pet in scoped_pets for event in pet.clinical_events]

    plan_statuses = Counter(item.status for item in subscriptions)
    service_statuses = Counter(item.status for item in services)
    alert_statuses = Counter(item.status for item in alerts)
    active_alerts = [item for item in alerts if item.status in ACTIVE_ALERT_STATUSES]
    alert_severities = Counter(item.severity for item in active_alerts)
    species_distribution = Counter(item.species for item in scoped_pets)

    active_pet_ids = {item.pet_id for item in active_alerts}
    plans_active = plan_statuses['active'] + plan_statuses['expiring']
    plans_expiring = sum(
        1
        for item in subscriptions
        if item.status in OPEN_PLAN_STATUSES and today <= item.end_date <= today + timedelta(days=45)
    )

    total_committed = money(sum((Decimal(item.total_amount or 0) for item in subscriptions if item.status != 'cancelled'), Decimal('0')))
    paid_installments = [item for item in installments if item.status == 'paid']
    unpaid_installments = [item for item in installments if item.status not in {'paid', 'cancelled'}]
    amount_collected = money(sum((Decimal(item.amount) for item in paid_installments), Decimal('0')))
    amount_outstanding = money(sum((Decimal(item.amount) for item in unpaid_installments), Decimal('0')))
    overdue_installments = [item for item in unpaid_installments if item.due_date < today]
    overdue_amount = money(sum((Decimal(item.amount) for item in overdue_installments), Decimal('0')))
    next_installment = min(unpaid_installments, key=lambda item: item.due_date, default=None)

    trends: dict[str, dict[str, int | Decimal]] = {
        key: {
            'plans_started': 0,
            'renewals': 0,
            'services_completed': 0,
            'alerts_generated': 0,
            'amount_collected': Decimal('0'),
        }
        for key in month_keys
    }
    for item in subscriptions:
        key = item.start_date.strftime('%Y-%m')
        if key in trends:
            trends[key]['plans_started'] += 1
            if item.renewed_from_id:
                trends[key]['renewals'] += 1
    for item in services:
        if item.completed_date:
            key = item.completed_date.strftime('%Y-%m')
            if key in trends:
                trends[key]['services_completed'] += 1
    for item in alerts:
        key = item.generated_at.date().strftime('%Y-%m')
        if key in trends:
            trends[key]['alerts_generated'] += 1
    for item in paid_installments:
        if item.paid_at:
            key = item.paid_at.date().strftime('%Y-%m')
            if key in trends:
                trends[key]['amount_collected'] += Decimal(item.amount)

    monthly_trends = [
        DashboardTrendPoint(
            month=key,
            label=f'{MONTH_LABELS[start.month - 1]} {str(start.year)[-2:]}',
            plans_started=int(trends[key]['plans_started']),
            renewals=int(trends[key]['renewals']),
            services_completed=int(trends[key]['services_completed']),
            alerts_generated=int(trends[key]['alerts_generated']),
            amount_collected=money(Decimal(trends[key]['amount_collected'])),
        )
        for start, key in zip(month_starts, month_keys, strict=True)
    ]

    rule_labels = {item.rule_code: item.title for item in active_alerts}
    top_alert_rules = _ranked(Counter(item.rule_code for item in active_alerts), rule_labels)
    recent_events = [item for item in clinical_events if item.event_date.date() >= trend_start]
    event_labels = {item.event_type: item.event_type.replace('_', ' ').title() for item in recent_events}
    top_clinical_events = _ranked(Counter(item.event_type for item in recent_events), event_labels)

    upcoming: list[DashboardUpcomingItem] = []
    for subscription in subscriptions:
        pet = subscription.pet
        if subscription.status in {'active', 'expiring'} and today <= subscription.end_date <= today + timedelta(days=45):
            upcoming.append(DashboardUpcomingItem(
                item_type='plan', title='Plan proximo a vencer', detail=subscription.health_plan.name,
                pet_id=pet.id, pet_name=pet.name, due_date=subscription.end_date,
                status=subscription.status, target_url=f'/pets/{pet.id}',
            ))
        for item in subscription.installments:
            if item.status not in {'paid', 'cancelled'} and item.due_date <= today + timedelta(days=45):
                upcoming.append(DashboardUpcomingItem(
                    item_type='installment', title=f'Cuota {item.installment_number}',
                    detail=f'{money(Decimal(item.amount)):.2f} EUR', pet_id=pet.id, pet_name=pet.name,
                    due_date=item.due_date, status='overdue' if item.due_date < today else 'pending',
                    target_url=f'/pets/{pet.id}',
                ))
        for item in subscription.services:
            if item.status in {'overdue', 'upcoming'} and item.scheduled_date and item.scheduled_date <= today + timedelta(days=45):
                upcoming.append(DashboardUpcomingItem(
                    item_type='service', title=item.plan_service.name, detail=subscription.health_plan.name,
                    pet_id=pet.id, pet_name=pet.name, due_date=item.scheduled_date, status=item.status,
                    target_url=f'/pets/{pet.id}',
                ))
    for alert in active_alerts:
        if alert.severity in {'high', 'medium'}:
            upcoming.append(DashboardUpcomingItem(
                item_type='alert', title=alert.title, detail='Aviso preventivo pendiente de seguimiento',
                pet_id=alert.pet_id, pet_name=alert.pet.name, due_date=alert.generated_at.date(),
                status=alert.status, severity=alert.severity,
                target_url=(f'/pets/{alert.pet_id}' if user.role == 'owner' else f'/alerts?pet_id={alert.pet_id}'),
            ))
    priority = {'overdue': 0, 'new': 0, 'reviewed': 1, 'upcoming': 2, 'pending': 3, 'expiring': 4, 'active': 5}
    upcoming.sort(key=lambda item: (priority.get(item.status, 9), item.due_date, item.pet_name))

    owner_pets: list[DashboardOwnerPet] = []
    if user.role == 'owner':
        for pet in scoped_pets:
            pet_subscriptions = [item for item in pet.subscriptions if plan_id is None or item.health_plan_id == plan_id]
            current = next((item for item in pet_subscriptions if item.status in OPEN_PLAN_STATUSES), None)
            if current is None:
                current = max(pet_subscriptions, key=lambda item: item.end_date, default=None)
            pet_services = current.services if current else []
            pet_unpaid = [item for item in (current.installments if current else []) if item.status not in {'paid', 'cancelled'}]
            next_due = min(pet_unpaid, key=lambda item: item.due_date, default=None)
            pet_alerts = [item for item in pet.risk_alerts if item.status in ACTIVE_ALERT_STATUSES]
            owner_pets.append(DashboardOwnerPet(
                pet_id=pet.id,
                pet_name=pet.name,
                species=pet.species,
                breed=pet.breed,
                plan_name=current.health_plan.name if current else None,
                plan_status=current.status if current else None,
                plan_end_date=current.end_date if current else None,
                completion_percentage=completion_percentage(pet_services),
                payment_status=('paid' if current and not pet_unpaid else 'installments_pending') if current else None,
                amount_remaining=money(sum((Decimal(item.amount) for item in pet_unpaid), Decimal('0'))),
                next_installment_date=next_due.due_date if next_due else None,
                next_installment_amount=money(Decimal(next_due.amount)) if next_due else None,
                services_pending=sum(1 for item in pet_services if item.status in {'pending', 'upcoming'}),
                services_overdue=sum(1 for item in pet_services if item.status == 'overdue'),
                active_alerts=len(pet_alerts),
            ))

    return DashboardResponse(
        plans_active=plans_active,
        plans_expiring=plans_expiring,
        services_pending=service_statuses['pending'] + service_statuses['upcoming'],
        services_overdue=service_statuses['overdue'],
        pets_with_alerts=len(active_pet_ids),
        pets_total=len(scoped_pets),
        completion_average=completion_percentage(services),
        role_scope=user.role,
        generated_at=now,
        filters={'months': len(month_starts), 'species': species, 'plan_id': str(plan_id) if plan_id else None},
        financial=DashboardFinancialSummary(
            total_committed=total_committed,
            amount_collected=amount_collected,
            amount_outstanding=amount_outstanding,
            overdue_amount=overdue_amount,
            overdue_installments=len(overdue_installments),
            next_due_date=next_installment.due_date if next_installment else None,
            next_due_amount=money(Decimal(next_installment.amount)) if next_installment else None,
        ),
        plans_by_status=dict(plan_statuses),
        services_by_status=dict(service_statuses),
        alerts_by_severity=dict(alert_severities),
        alerts_by_status=dict(alert_statuses),
        species_distribution=dict(species_distribution),
        monthly_trends=monthly_trends,
        top_alert_rules=top_alert_rules,
        top_clinical_events=top_clinical_events,
        upcoming_items=upcoming[:15],
        owner_pets=owner_pets,
    )
