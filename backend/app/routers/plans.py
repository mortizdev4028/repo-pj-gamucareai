"""Health-plan catalogue, assignment, renewal and payment endpoints."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    ClinicalEvent,
    HealthPlan,
    Pet,
    PetPlanSubscription,
    PlanInstallment,
    RenewalRequest,
    SubscriptionService,
    User,
)
from app.schemas import (
    CompleteServiceRequest,
    HealthPlanResponse,
    InstallmentResponse,
    InstallmentUpdateRequest,
    PaymentResponse,
    PaymentUpdateRequest,
    RenewalRequestCreate,
    RenewalRequestResponse,
    RenewalReviewRequest,
    SubscriptionCancelRequest,
    SubscriptionChangeRequest,
    SubscriptionCreateRequest,
    SubscriptionListItem,
    SubscriptionRenewRequest,
)
from app.services.alert_workflow import recalculate_and_enrich_pet
from app.services.audit import record_audit, snapshot_model
from app.services.payments import payment_values
from app.services.subscriptions import (
    OPEN_STATUSES,
    add_months,
    cancel_subscription,
    create_subscription,
    generate_installments,
    find_open_subscription,
    refresh_subscription_status,
    update_installment_counters,
)

router = APIRouter(
    prefix='/plans',
    tags=['plans'],
    dependencies=[Depends(require_roles('clinic', 'staff', 'owner'))],
)


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _subscription_query():
    return select(PetPlanSubscription).options(
        selectinload(PetPlanSubscription.pet).selectinload(Pet.owner),
        selectinload(PetPlanSubscription.health_plan),
        selectinload(PetPlanSubscription.installments),
        selectinload(PetPlanSubscription.services).selectinload(SubscriptionService.plan_service),
        selectinload(PetPlanSubscription.renewal_requests),
    )


def _get_subscription(db: Session, subscription_id: uuid.UUID) -> PetPlanSubscription:
    item = db.scalar(_subscription_query().where(PetPlanSubscription.id == subscription_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Suscripcion no encontrada')
    return item


def _get_plan(db: Session, plan_id: uuid.UUID) -> HealthPlan:
    plan = db.scalar(
        select(HealthPlan)
        .options(selectinload(HealthPlan.services))
        .where(HealthPlan.id == plan_id, HealthPlan.is_active.is_(True))
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Plan no encontrado')
    return plan


def _get_pet(db: Session, pet_id: uuid.UUID) -> Pet:
    pet = db.scalar(select(Pet).options(selectinload(Pet.owner)).where(Pet.id == pet_id))
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mascota no encontrada')
    return pet


def _assert_owner_access(user: User, subscription: PetPlanSubscription) -> None:
    if user.role == 'owner' and (user.owner is None or subscription.pet.owner_id != user.owner.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No puedes consultar este plan')


def _list_item(subscription: PetPlanSubscription) -> SubscriptionListItem:
    payment = payment_values(subscription)
    return SubscriptionListItem(
        id=subscription.id,
        pet_id=subscription.pet.id,
        pet_name=subscription.pet.name,
        owner_id=subscription.pet.owner.id,
        owner_name=f'{subscription.pet.owner.first_name} {subscription.pet.owner.last_name}',
        health_plan_id=subscription.health_plan.id,
        plan_name=subscription.health_plan.name,
        species=subscription.pet.species,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        status=subscription.status,
        renewal_status=subscription.renewal_status,
        days_until_expiry=(subscription.end_date - date.today()).days,
        payment_status=payment['payment_status'],
        installments_total=payment['installments_total'],
        installments_paid=payment['installments_paid'],
        total_amount=payment['total_amount'],
        amount_paid=payment['amount_paid'],
        amount_remaining=payment['amount_remaining'],
    )


def _renewal_response(item: RenewalRequest) -> RenewalRequestResponse:
    return RenewalRequestResponse(
        id=item.id,
        subscription_id=item.subscription.id,
        pet_id=item.subscription.pet.id,
        pet_name=item.subscription.pet.name,
        owner_name=f'{item.subscription.pet.owner.first_name} {item.subscription.pet.owner.last_name}',
        current_plan_name=item.subscription.health_plan.name,
        requested_plan_id=item.requested_plan_id,
        requested_plan_name=item.requested_plan.name if item.requested_plan else None,
        payment_mode=item.payment_mode,
        installments_total=item.installments_total,
        status=item.status,
        requested_at=item.requested_at,
        reviewed_at=item.reviewed_at,
        notes=item.notes,
    )


def _renew(
    db: Session,
    *,
    subscription: PetPlanSubscription,
    plan: HealthPlan,
    start_date: date,
    payment_mode: str,
    installments_total: int,
    installments_paid: int,
) -> PetPlanSubscription:
    other = find_open_subscription(db, subscription.pet_id, excluding_id=subscription.id)
    if other is not None:
        raise ValueError('La mascota ya tiene otra suscripcion activa o programada')
    if start_date <= subscription.end_date and subscription.status != 'cancelled':
        raise ValueError('La renovacion debe comenzar despues de que termine el plan actual')
    renewed = create_subscription(
        db,
        pet=subscription.pet,
        plan=plan,
        start_date=start_date,
        payment_mode=payment_mode,
        installments_total=installments_total,
        installments_paid=installments_paid,
        renewed_from_id=subscription.id,
    )
    subscription.renewal_status = 'renewed'
    return renewed


@router.get('', response_model=list[HealthPlanResponse])
def list_plans(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[HealthPlan]:
    stmt = (
        select(HealthPlan)
        .options(selectinload(HealthPlan.services))
        .where(HealthPlan.is_active.is_(True))
        .order_by(HealthPlan.species, HealthPlan.price_monthly)
    )
    return list(db.scalars(stmt).unique().all())


@router.get('/subscriptions', response_model=list[SubscriptionListItem])
def list_subscriptions(
    lifecycle_status: str | None = Query(default=None, alias='status'),
    expiring_days: int | None = Query(default=None, ge=0, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SubscriptionListItem]:
    """List subscriptions within the scope of the authenticated profile."""
    stmt = _subscription_query().join(Pet).order_by(PetPlanSubscription.end_date)
    if user.role == 'owner':
        if user.owner is None:
            return []
        stmt = stmt.where(Pet.owner_id == user.owner.id)
    subscriptions = list(db.scalars(stmt).unique().all())
    changed = False
    for item in subscriptions:
        changed = refresh_subscription_status(item) or changed
    if changed:
        db.commit()

    if lifecycle_status:
        subscriptions = [item for item in subscriptions if item.status == lifecycle_status]
    if expiring_days is not None:
        limit = date.today() + timedelta(days=expiring_days)
        subscriptions = [
            item for item in subscriptions
            if item.status in ('active', 'expiring') and date.today() <= item.end_date <= limit
        ]
    return [_list_item(item) for item in subscriptions]


@router.post('/subscriptions', response_model=SubscriptionListItem, status_code=status.HTTP_201_CREATED)
def assign_subscription(
    payload: SubscriptionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> SubscriptionListItem:
    pet = _get_pet(db, payload.pet_id)
    plan = _get_plan(db, payload.health_plan_id)
    existing = find_open_subscription(db, pet.id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='La mascota ya tiene un plan activo o programado')
    try:
        item = create_subscription(
            db,
            pet=pet,
            plan=plan,
            start_date=payload.start_date,
            payment_mode=payload.payment_mode,
            installments_total=payload.installments_total,
            installments_paid=payload.installments_paid,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    db.flush()
    record_audit(
        db, actor=user, action='subscription.assigned', entity_type='subscription', entity_id=item.id,
        after=snapshot_model(item), details={'pet_id': str(pet.id), 'plan_id': str(plan.id)},
    )
    db.commit()
    db.refresh(item)
    return _list_item(_get_subscription(db, item.id))


@router.post('/subscriptions/{subscription_id}/change', response_model=SubscriptionListItem)
def change_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> SubscriptionListItem:
    current = _get_subscription(db, subscription_id)
    before = snapshot_model(current)
    refresh_subscription_status(current)
    if current.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Solo se puede cambiar un plan activo o programado')
    if payload.effective_date > date.today() and current.status != 'scheduled':
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='El cambio de un plan activo debe ser inmediato')
    plan = _get_plan(db, payload.health_plan_id)
    cancellation_date = current.start_date if current.status == 'scheduled' else payload.effective_date
    try:
        cancel_subscription(current, cancellation_date=cancellation_date, reason=payload.reason)
        replacement = create_subscription(
            db,
            pet=current.pet,
            plan=plan,
            start_date=payload.effective_date,
            payment_mode=payload.payment_mode,
            installments_total=payload.installments_total,
            installments_paid=payload.installments_paid,
        )
    except ValueError as exc:
        db.rollback()
        raise _bad_request(exc) from exc
    db.flush()
    record_audit(
        db, actor=user, action='subscription.changed', entity_type='subscription', entity_id=current.id,
        before=before, after=snapshot_model(current), details={'replacement_id': str(replacement.id)},
    )
    record_audit(
        db, actor=user, action='subscription.assigned', entity_type='subscription', entity_id=replacement.id,
        after=snapshot_model(replacement), details={'replaces_id': str(current.id)},
    )
    db.commit()
    db.refresh(replacement)
    return _list_item(_get_subscription(db, replacement.id))


@router.post('/subscriptions/{subscription_id}/cancel', response_model=SubscriptionListItem)
def cancel_plan(
    subscription_id: uuid.UUID,
    payload: SubscriptionCancelRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> SubscriptionListItem:
    subscription = _get_subscription(db, subscription_id)
    before = snapshot_model(subscription)
    try:
        cancel_subscription(
            subscription,
            cancellation_date=payload.cancellation_date,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    db.flush()
    record_audit(
        db, actor=user, action='subscription.cancelled', entity_type='subscription', entity_id=subscription.id,
        before=before, after=snapshot_model(subscription),
    )
    db.commit()
    return _list_item(_get_subscription(db, subscription.id))


@router.post('/subscriptions/{subscription_id}/renew', response_model=SubscriptionListItem, status_code=status.HTTP_201_CREATED)
def renew_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionRenewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> SubscriptionListItem:
    subscription = _get_subscription(db, subscription_id)
    plan = _get_plan(db, payload.health_plan_id or subscription.health_plan_id)
    start = payload.start_date or (subscription.end_date + timedelta(days=1))
    try:
        renewed = _renew(
            db,
            subscription=subscription,
            plan=plan,
            start_date=start,
            payment_mode=payload.payment_mode,
            installments_total=payload.installments_total,
            installments_paid=payload.installments_paid,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    db.flush()
    record_audit(
        db, actor=user, action='subscription.renewed', entity_type='subscription', entity_id=renewed.id,
        after=snapshot_model(renewed), details={'renewed_from_id': str(subscription.id)},
    )
    db.commit()
    db.refresh(renewed)
    return _list_item(_get_subscription(db, renewed.id))


@router.post('/subscriptions/{subscription_id}/renewal-request', response_model=RenewalRequestResponse, status_code=status.HTTP_201_CREATED)
def request_renewal(
    subscription_id: uuid.UUID,
    payload: RenewalRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RenewalRequestResponse:
    subscription = _get_subscription(db, subscription_id)
    _assert_owner_access(user, subscription)
    if user.role not in ('owner', 'clinic'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='El perfil es de solo lectura')
    if subscription.status == 'cancelled':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='No se puede renovar un plan cancelado')
    if subscription.end_date > date.today() + timedelta(days=90):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='La renovacion se puede solicitar durante los ultimos 90 dias')
    pending = db.scalar(
        select(RenewalRequest).where(
            RenewalRequest.subscription_id == subscription.id,
            RenewalRequest.status == 'pending',
        )
    )
    if pending is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Ya existe una solicitud de renovacion pendiente')
    requested_plan = _get_plan(db, payload.health_plan_id or subscription.health_plan_id)
    if requested_plan.species != subscription.pet.species:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='El plan solicitado no corresponde a la especie')
    if payload.payment_mode == 'installments' and not 2 <= payload.installments_total <= 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Selecciona entre 2 y 12 cuotas')
    item = RenewalRequest(
        subscription=subscription,
        requested_by=user.id,
        status='pending',
        requested_plan=requested_plan,
        payment_mode=payload.payment_mode,
        installments_total=1 if payload.payment_mode == 'single' else payload.installments_total,
        notes=payload.notes,
    )
    subscription.renewal_status = 'requested'
    db.add(item)
    db.flush()
    record_audit(
        db, actor=user, action='renewal.requested', entity_type='renewal_request', entity_id=item.id,
        after=snapshot_model(item), details={'subscription_id': str(subscription.id)},
    )
    db.commit()
    return _renewal_response(
        db.scalar(
            select(RenewalRequest)
            .options(
                selectinload(RenewalRequest.requested_plan),
                selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.health_plan),
                selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.pet).selectinload(Pet.owner),
            )
            .where(RenewalRequest.id == item.id)
        )
    )


@router.get('/renewal-requests', response_model=list[RenewalRequestResponse])
def list_renewal_requests(
    request_status: str | None = Query(default=None, alias='status'),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RenewalRequestResponse]:
    stmt = (
        select(RenewalRequest)
        .options(
            selectinload(RenewalRequest.requested_plan),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.health_plan),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.pet).selectinload(Pet.owner),
        )
        .order_by(RenewalRequest.requested_at.desc())
    )
    if request_status:
        stmt = stmt.where(RenewalRequest.status == request_status)
    items = list(db.scalars(stmt).unique().all())
    if user.role == 'owner':
        if user.owner is None:
            return []
        items = [item for item in items if item.subscription.pet.owner_id == user.owner.id]
    return [_renewal_response(item) for item in items]


@router.patch('/renewal-requests/{request_id}', response_model=RenewalRequestResponse)
def review_renewal_request(
    request_id: uuid.UUID,
    payload: RenewalReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> RenewalRequestResponse:
    item = db.scalar(
        select(RenewalRequest)
        .options(
            selectinload(RenewalRequest.requested_plan),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.health_plan),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.services),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.pet).selectinload(Pet.owner),
        )
        .where(RenewalRequest.id == request_id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Solicitud no encontrada')
    if item.status != 'pending':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='La solicitud ya ha sido revisada')
    before = snapshot_model(item)

    if payload.status == 'approved':
        plan = item.requested_plan or item.subscription.health_plan
        try:
            _renew(
                db,
                subscription=item.subscription,
                plan=plan,
                start_date=item.subscription.end_date + timedelta(days=1),
                payment_mode=item.payment_mode or 'single',
                installments_total=item.installments_total or 1,
                installments_paid=1 if (item.payment_mode or 'single') == 'single' else 0,
            )
        except ValueError as exc:
            raise _bad_request(exc) from exc
        item.status = 'approved'
    else:
        item.status = 'rejected'
        item.subscription.renewal_status = 'not_requested'
    item.notes = payload.notes or item.notes
    item.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    record_audit(
        db, actor=user, action='renewal.reviewed', entity_type='renewal_request', entity_id=item.id,
        before=before, after=snapshot_model(item), details={'decision': item.status},
    )
    db.commit()
    refreshed = db.scalar(
        select(RenewalRequest)
        .options(
            selectinload(RenewalRequest.requested_plan),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.health_plan),
            selectinload(RenewalRequest.subscription).selectinload(PetPlanSubscription.pet).selectinload(Pet.owner),
        )
        .where(RenewalRequest.id == request_id)
    )
    return _renewal_response(refreshed)


@router.patch('/subscriptions/{subscription_id}/installments/{installment_id}', response_model=InstallmentResponse)
def update_installment(
    subscription_id: uuid.UUID,
    installment_id: uuid.UUID,
    payload: InstallmentUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> InstallmentResponse:
    """Mark one due payment as paid or correct it back to pending."""
    subscription = _get_subscription(db, subscription_id)
    installment = next((item for item in subscription.installments if item.id == installment_id), None)
    if installment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Cuota no encontrada')
    before = snapshot_model(installment)
    if subscription.status == 'cancelled' and payload.status != 'paid':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='No se puede reabrir una cuota de un plan cancelado')

    if payload.status == 'paid':
        installment.status = 'paid'
        installment.paid_at = datetime.now(timezone.utc)
    else:
        installment.status = 'overdue' if installment.due_date < date.today() else 'pending'
        installment.paid_at = None
    installment.notes = payload.notes
    update_installment_counters(subscription)
    db.flush()
    record_audit(
        db, actor=user, action='installment.updated', entity_type='installment', entity_id=installment.id,
        before=before, after=snapshot_model(installment), details={'subscription_id': str(subscription.id)},
    )
    db.commit()
    db.refresh(installment)
    return InstallmentResponse.model_validate(installment, from_attributes=True)


@router.patch('/services/{service_id}/complete')
def complete_service(
    service_id: uuid.UUID,
    payload: CompleteServiceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> dict:
    service = db.get(SubscriptionService, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Servicio no encontrado')
    if service.status == 'cancelled':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='La prestacion pertenece a un plan cancelado')
    before = snapshot_model(service)
    service.status = 'completed'
    service.completed_date = payload.completed_date
    service.notes = payload.notes

    if service.clinical_event_id is None:
        event = ClinicalEvent(
            pet_id=service.subscription.pet_id,
            external_id=f'APP-{service.id}',
            event_date=datetime.combine(payload.completed_date, time(hour=10), tzinfo=timezone.utc),
            event_type=service.plan_service.service_type,
            title=service.plan_service.name,
            description=payload.notes or 'Prestacion marcada como realizada desde GamuCare AI.',
            visible_to_owner=True,
        )
        db.add(event)
        db.flush()
        service.clinical_event_id = event.id
    pet_id = service.subscription.pet_id
    db.flush()
    record_audit(
        db, actor=user, action='service.completed', entity_type='subscription_service', entity_id=service.id,
        before=before, after=snapshot_model(service), details={'pet_id': str(pet_id)},
    )
    db.commit()
    background_tasks.add_task(recalculate_and_enrich_pet, pet_id)
    return {'id': str(service.id), 'status': service.status}


@router.patch('/subscriptions/{subscription_id}/payment', response_model=PaymentResponse)
def update_subscription_payment(
    subscription_id: uuid.UUID,
    payload: PaymentUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> PaymentResponse:
    subscription = db.get(PetPlanSubscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Suscripcion no encontrada')
    if subscription.status == 'cancelled':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='No se puede modificar el pago de un plan cancelado')
    before = snapshot_model(subscription)

    if payload.payment_mode == 'single':
        subscription.payment_mode = 'single'
        subscription.installments_total = 1
        subscription.installments_paid = 1
        subscription.total_amount = subscription.health_plan.price_single
    else:
        if payload.installments_total < 2:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='El pago a plazos debe tener entre 2 y 12 cuotas')
        if payload.installments_paid > payload.installments_total:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Las cuotas pagadas no pueden superar las cuotas acordadas')
        subscription.payment_mode = 'installments'
        subscription.installments_total = payload.installments_total
        subscription.installments_paid = payload.installments_paid
        subscription.total_amount = subscription.health_plan.price_monthly * 12

    generate_installments(subscription)
    db.flush()
    record_audit(
        db, actor=user, action='subscription.payment_updated', entity_type='subscription', entity_id=subscription.id,
        before=before, after=snapshot_model(subscription),
    )
    db.commit()
    db.refresh(subscription)
    return PaymentResponse(subscription_id=subscription.id, **payment_values(subscription))
