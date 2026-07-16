"""Patient read and management endpoints.

Owners only see their active pets. Clinic and staff profiles can inspect the
whole catalogue, while only the clinic profile can change patient records.
"""
from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import ClinicalEvent, Owner, Pet, PetPlanSubscription, PlanInstallment, SubscriptionService, User
from app.services.alert_workflow import recalculate_and_enrich_pet
from app.services.audit import record_audit, snapshot_model
from app.services.payments import payment_values
from app.services.subscriptions import refresh_subscription_status
from app.schemas import (
    AlertResponse,
    ClinicalEventCreate,
    ClinicalEventResponse,
    InstallmentResponse,
    OwnerSummary,
    PetCreate,
    PetDetail,
    PetListItem,
    PetUpdate,
    StatusResponse,
    SubscriptionResponse,
    SubscriptionServiceResponse,
)

router = APIRouter(
    prefix='/pets',
    tags=['pets'],
    dependencies=[Depends(require_roles('clinic', 'staff', 'owner'))],
)


def authorised_pet_query(user: User, include_inactive: bool = False):
    """Build the query scope enforced for the authenticated profile."""
    stmt = select(Pet)
    if user.role == 'owner':
        if user.owner is None or not user.owner.is_active:
            return stmt.where(False)
        stmt = stmt.where(Pet.owner_id == user.owner.id, Pet.is_active.is_(True))
    elif not include_inactive:
        stmt = stmt.where(Pet.is_active.is_(True))
    return stmt


def _find_pet(db: Session, pet_id: uuid.UUID) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mascota no encontrada')
    return pet


def _find_active_owner(db: Session, owner_id: uuid.UUID) -> Owner:
    owner = db.get(Owner, owner_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='El cliente no existe o esta dado de baja')
    return owner


def _microchip_in_use(db: Session, microchip: str | None, pet_id: uuid.UUID | None = None) -> bool:
    if not microchip:
        return False
    stmt = select(Pet.id).where(Pet.microchip == microchip.strip())
    if pet_id:
        stmt = stmt.where(Pet.id != pet_id)
    return db.scalar(stmt) is not None


@router.get('', response_model=list[PetListItem])
def list_pets(
    search: str | None = Query(default=None, max_length=120),
    owner_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Pet]:
    if user.role == 'owner':
        include_inactive = False
        owner_id = None

    stmt = authorised_pet_query(user, include_inactive).options(selectinload(Pet.owner)).order_by(Pet.name)
    if owner_id and user.role in ('clinic', 'staff'):
        stmt = stmt.where(Pet.owner_id == owner_id)
    if search:
        term = f'%{search.strip()}%'
        stmt = stmt.join(Owner).where(
            or_(
                Pet.name.ilike(term),
                Pet.breed.ilike(term),
                Pet.microchip.ilike(term),
                Pet.external_id.ilike(term),
                Owner.first_name.ilike(term),
                Owner.last_name.ilike(term),
            )
        )
    return list(db.scalars(stmt.limit(250)).unique().all())


@router.post('', response_model=PetListItem, status_code=status.HTTP_201_CREATED)
def create_pet(
    payload: PetCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> Pet:
    owner = _find_active_owner(db, payload.owner_id)
    if _microchip_in_use(db, payload.microchip):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='El microchip ya esta registrado')

    pet = Pet(
        owner=owner,
        external_id=(payload.external_id or f'APP-PET-{uuid.uuid4().hex[:10].upper()}').strip(),
        name=payload.name.strip(),
        species=payload.species,
        breed=payload.breed.strip(),
        birth_date=payload.birth_date,
        sex=payload.sex.strip(),
        weight_kg=payload.weight_kg,
        neutered=payload.neutered,
        microchip=payload.microchip.strip() if payload.microchip else None,
        allergies=payload.allergies.strip() if payload.allergies else None,
        chronic_conditions=payload.chronic_conditions.strip() if payload.chronic_conditions else None,
        is_active=True,
    )
    db.add(pet)
    db.flush()
    record_audit(
        db, actor=user, action='pet.created', entity_type='pet', entity_id=pet.id,
        after=snapshot_model(pet), details={'owner_id': str(owner.id)},
    )
    db.commit()
    db.refresh(pet)
    background_tasks.add_task(recalculate_and_enrich_pet, pet.id)
    return pet


@router.patch('/{pet_id}', response_model=PetListItem)
def update_pet(
    pet_id: uuid.UUID,
    payload: PetUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> Pet:
    pet = _find_pet(db, pet_id)
    before = snapshot_model(pet)
    changes = payload.model_dump(exclude_unset=True)

    if 'owner_id' in changes and changes['owner_id'] is not None:
        pet.owner = _find_active_owner(db, changes.pop('owner_id'))
    if 'microchip' in changes:
        microchip = changes['microchip']
        if _microchip_in_use(db, microchip, pet.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='El microchip ya esta registrado')
        changes['microchip'] = microchip.strip() if microchip else None

    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(pet, field, value)

    db.flush()
    record_audit(
        db, actor=user, action='pet.updated', entity_type='pet', entity_id=pet.id,
        before=before, after=snapshot_model(pet),
    )
    db.commit()
    db.refresh(pet)
    background_tasks.add_task(recalculate_and_enrich_pet, pet.id)
    return pet


@router.post('/{pet_id}/clinical-events', response_model=ClinicalEventResponse, status_code=status.HTTP_201_CREATED)
def create_clinical_event(
    pet_id: uuid.UUID,
    payload: ClinicalEventCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> ClinicalEvent:
    """Add a clinical event and trigger patient reindexing and alert review."""
    pet = _find_pet(db, pet_id)
    event_date = payload.event_date
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    event = ClinicalEvent(
        pet=pet,
        external_id=f'APP-EVT-{uuid.uuid4().hex[:12].upper()}',
        event_date=event_date,
        event_type=payload.event_type.strip(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        diagnosis=payload.diagnosis.strip() if payload.diagnosis else None,
        treatment=payload.treatment.strip() if payload.treatment else None,
        weight_kg=payload.weight_kg,
        visible_to_owner=payload.visible_to_owner,
    )
    if payload.weight_kg is not None:
        pet.weight_kg = payload.weight_kg
    db.add(event)
    db.flush()
    record_audit(
        db, actor=user, action='clinical_event.created', entity_type='clinical_event', entity_id=event.id,
        after=snapshot_model(event), details={'pet_id': str(pet.id)},
    )
    db.commit()
    db.refresh(event)
    background_tasks.add_task(recalculate_and_enrich_pet, pet.id)
    return event


@router.delete('/{pet_id}', response_model=StatusResponse)
def deactivate_pet(
    pet_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> StatusResponse:
    pet = _find_pet(db, pet_id)
    before = snapshot_model(pet)
    pet.is_active = False
    db.flush()
    record_audit(
        db, actor=user, action='pet.deactivated', entity_type='pet', entity_id=pet.id,
        before=before, after=snapshot_model(pet),
    )
    db.commit()
    return StatusResponse(id=pet.id, is_active=False)


@router.post('/{pet_id}/activate', response_model=StatusResponse)
def activate_pet(
    pet_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> StatusResponse:
    pet = _find_pet(db, pet_id)
    before = snapshot_model(pet)
    if not pet.owner.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Activa primero al cliente propietario')
    pet.is_active = True
    db.flush()
    record_audit(
        db, actor=user, action='pet.activated', entity_type='pet', entity_id=pet.id,
        before=before, after=snapshot_model(pet),
    )
    db.commit()
    return StatusResponse(id=pet.id, is_active=True)


def build_subscription(subscription: PetPlanSubscription | None) -> SubscriptionResponse | None:
    if subscription is None:
        return None
    services = []
    counted = 0
    completed = 0
    for item in sorted(
        subscription.services,
        key=lambda service: (service.scheduled_date or subscription.end_date, service.occurrence_number),
    ):
        if item.status != 'not_applicable' and item.plan_service.service_mode not in ('discount', 'benefit'):
            counted += 1
        if item.status == 'completed':
            completed += 1
        services.append(
            SubscriptionServiceResponse(
                id=item.id,
                name=item.plan_service.name,
                service_type=item.plan_service.service_type,
                service_mode=item.plan_service.service_mode,
                occurrence_number=item.occurrence_number,
                scheduled_date=item.scheduled_date,
                completed_date=item.completed_date,
                status=item.status,
                notes=item.notes,
            )
        )
    percentage = round(completed / counted * 100, 1) if counted else 0.0
    payment = payment_values(subscription)
    installments = [
        InstallmentResponse(
            id=item.id,
            installment_number=item.installment_number,
            due_date=item.due_date,
            amount=item.amount,
            status=item.status,
            paid_at=item.paid_at,
            notes=item.notes,
        )
        for item in sorted(subscription.installments, key=lambda value: value.installment_number)
    ]
    return SubscriptionResponse(
        id=subscription.id,
        health_plan_id=subscription.health_plan.id,
        plan_name=subscription.health_plan.name,
        lifecycle=subscription.health_plan.lifecycle,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        status=subscription.status,
        renewal_status=subscription.renewal_status,
        cancelled_at=subscription.cancelled_at,
        cancellation_reason=subscription.cancellation_reason,
        completion_percentage=percentage,
        installments=installments,
        services=services,
        **payment,
    )


@router.get('/{pet_id}', response_model=PetDetail)
def get_pet(
    pet_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PetDetail:
    stmt = (
        authorised_pet_query(user, include_inactive=user.role in ('clinic', 'staff'))
        .where(Pet.id == pet_id)
        .options(
            selectinload(Pet.owner),
            selectinload(Pet.clinical_events),
            selectinload(Pet.risk_alerts),
            selectinload(Pet.subscriptions).selectinload(PetPlanSubscription.health_plan),
            selectinload(Pet.subscriptions).selectinload(PetPlanSubscription.installments),
            selectinload(Pet.subscriptions)
            .selectinload(PetPlanSubscription.services)
            .selectinload(SubscriptionService.plan_service),
        )
    )
    pet = db.scalar(stmt)
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mascota no encontrada')

    changed = False
    for subscription in pet.subscriptions:
        changed = refresh_subscription_status(subscription) or changed
    if changed:
        db.commit()

    active = next((item for item in pet.subscriptions if item.status in ('active', 'expiring')), None)
    upcoming = next((item for item in pet.subscriptions if item.status == 'scheduled'), None)
    if active is None and upcoming is not None:
        active = upcoming
        upcoming = None
    elif active is None:
        historical = [item for item in pet.subscriptions if item.status in ('expired', 'cancelled')]
        if historical:
            active = sorted(historical, key=lambda item: item.end_date, reverse=True)[0]

    events = sorted(pet.clinical_events, key=lambda item: item.event_date, reverse=True)
    if user.role == 'owner':
        events = [event for event in events if event.visible_to_owner]

    alerts: list[AlertResponse] = []
    for item in sorted(pet.risk_alerts, key=lambda value: value.generated_at, reverse=True):
        response = AlertResponse.model_validate(item)
        if user.role == 'owner':
            # Cross-patient RAG evidence is useful to the clinic but must not
            # reveal other patient references in the owner portal.
            response = response.model_copy(
                update={
                    'evidence': {key: value for key, value in response.evidence.items() if key != 'rag_sources'},
                    'llm_explanation': None,
                    'model_name': None,
                }
            )
        alerts.append(response)

    return PetDetail(
        id=pet.id,
        external_id=pet.external_id,
        name=pet.name,
        species=pet.species,
        breed=pet.breed,
        birth_date=pet.birth_date,
        sex=pet.sex,
        weight_kg=pet.weight_kg,
        neutered=pet.neutered,
        microchip=pet.microchip,
        is_active=pet.is_active,
        allergies=pet.allergies,
        chronic_conditions=pet.chronic_conditions,
        owner=OwnerSummary.model_validate(pet.owner),
        subscription=build_subscription(active),
        upcoming_subscription=build_subscription(upcoming),
        clinical_events=[ClinicalEventResponse.model_validate(item) for item in events],
        alerts=alerts,
    )
