"""Customer management endpoints.

Clinic users may create, edit, deactivate and reactivate customers. Staff users
can inspect the same information but all write operations are blocked by the
backend, not only hidden in the frontend.
"""
from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, validate_password_policy
from app.database import get_db
from app.dependencies import require_roles
from app.models import Owner, Pet, User
from app.schemas import OwnerCreate, OwnerCreateResponse, OwnerListItem, OwnerUpdate, StatusResponse
from app.services.audit import record_audit, snapshot_model

router = APIRouter(prefix='/owners', tags=['owners'])


def _owner_item(owner: Owner, pet_count: int) -> OwnerListItem:
    """Convert an owner plus calculated values into the public read model."""
    return OwnerListItem(
        id=owner.id,
        external_id=owner.external_id,
        first_name=owner.first_name,
        last_name=owner.last_name,
        email=owner.email,
        phone=owner.phone,
        address=owner.address,
        is_active=owner.is_active,
        pet_count=pet_count,
        user_active=bool(owner.user and owner.user.is_active),
    )


def _find_owner(db: Session, owner_id: uuid.UUID) -> Owner:
    owner = db.get(Owner, owner_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Cliente no encontrado')
    return owner


def _email_in_use(db: Session, email: str, owner_id: uuid.UUID | None = None) -> bool:
    """Check both authentication and customer records for duplicate email."""
    normalized = email.lower().strip()
    user_exists = db.scalar(select(User.id).where(User.email == normalized))
    owner_stmt = select(Owner.id).where(Owner.email == normalized)
    if owner_id is not None:
        owner_stmt = owner_stmt.where(Owner.id != owner_id)
    owner_exists = db.scalar(owner_stmt)
    if owner_id is not None:
        owner = db.get(Owner, owner_id)
        if owner and owner.user_id == user_exists:
            user_exists = None
    return bool(user_exists or owner_exists)


@router.get('', response_model=list[OwnerListItem])
def list_owners(
    search: str | None = Query(default=None, max_length=120),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('clinic', 'staff')),
) -> list[OwnerListItem]:
    stmt = (
        select(Owner, func.count(Pet.id))
        .outerjoin(Pet, Pet.owner_id == Owner.id)
        .group_by(Owner.id)
        .order_by(Owner.last_name, Owner.first_name)
    )
    if not include_inactive:
        stmt = stmt.where(Owner.is_active.is_(True))
    if search:
        term = f'%{search.strip()}%'
        stmt = stmt.where(
            or_(
                Owner.first_name.ilike(term),
                Owner.last_name.ilike(term),
                Owner.email.ilike(term),
                Owner.phone.ilike(term),
                Owner.external_id.ilike(term),
            )
        )
    rows = db.execute(stmt.limit(200)).all()
    return [_owner_item(owner, int(pet_count)) for owner, pet_count in rows]


@router.get('/{owner_id}', response_model=OwnerListItem)
def get_owner(
    owner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('clinic', 'staff')),
) -> OwnerListItem:
    owner = _find_owner(db, owner_id)
    pet_count = db.scalar(select(func.count(Pet.id)).where(Pet.owner_id == owner.id)) or 0
    return _owner_item(owner, pet_count)


@router.post('', response_model=OwnerCreateResponse, status_code=status.HTTP_201_CREATED)
def create_owner(
    payload: OwnerCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles('clinic')),
) -> OwnerCreateResponse:
    email = str(payload.email).lower().strip()
    if _email_in_use(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Ya existe un usuario con ese correo')

    temporary_password = payload.initial_password or f'{secrets.token_urlsafe(10)}A1!'
    policy_errors = validate_password_policy(temporary_password, email=email)
    if policy_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=policy_errors)
    owner_user = User(email=email, password_hash=hash_password(temporary_password), role='owner', must_change_password=True)
    owner = Owner(
        user=owner_user,
        external_id=f'APP-OWN-{uuid.uuid4().hex[:10].upper()}',
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=payload.phone.strip(),
        email=email,
        address=payload.address.strip(),
        is_active=True,
    )
    db.add(owner)
    db.flush()
    record_audit(
        db, actor=actor, action='owner.created', entity_type='owner', entity_id=owner.id,
        after=snapshot_model(owner), details={'created_user_id': str(owner_user.id)},
    )
    db.commit()
    db.refresh(owner)
    item = _owner_item(owner, 0)
    return OwnerCreateResponse(**item.model_dump(), temporary_password=temporary_password)


@router.patch('/{owner_id}', response_model=OwnerListItem)
def update_owner(
    owner_id: uuid.UUID,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> OwnerListItem:
    owner = _find_owner(db, owner_id)
    before = snapshot_model(owner)
    changes = payload.model_dump(exclude_unset=True)

    if 'email' in changes and changes['email'] is not None:
        email = str(changes['email']).lower().strip()
        if email != owner.email and _email_in_use(db, email, owner.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Ya existe un usuario con ese correo')
        owner.email = email
        if owner.user:
            owner.user.email = email
        changes.pop('email')

    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(owner, field, value)

    db.flush()
    record_audit(
        db, actor=user, action='owner.updated', entity_type='owner', entity_id=owner.id,
        before=before, after=snapshot_model(owner),
    )
    db.commit()
    db.refresh(owner)
    pet_count = db.scalar(select(func.count(Pet.id)).where(Pet.owner_id == owner.id)) or 0
    return _owner_item(owner, pet_count)


@router.delete('/{owner_id}', response_model=StatusResponse)
def deactivate_owner(
    owner_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> StatusResponse:
    owner = _find_owner(db, owner_id)
    before = snapshot_model(owner)
    owner.is_active = False
    if owner.user:
        owner.user.is_active = False
    for pet in owner.pets:
        pet.is_active = False
    db.flush()
    record_audit(
        db, actor=user, action='owner.deactivated', entity_type='owner', entity_id=owner.id,
        before=before, after=snapshot_model(owner),
    )
    db.commit()
    return StatusResponse(id=owner.id, is_active=False)


@router.post('/{owner_id}/activate', response_model=StatusResponse)
def activate_owner(
    owner_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('clinic')),
) -> StatusResponse:
    owner = _find_owner(db, owner_id)
    before = snapshot_model(owner)
    owner.is_active = True
    if owner.user:
        owner.user.is_active = True
    db.flush()
    record_audit(
        db, actor=user, action='owner.activated', entity_type='owner', entity_id=owner.id,
        before=before, after=snapshot_model(owner),
    )
    db.commit()
    return StatusResponse(id=owner.id, is_active=True)
