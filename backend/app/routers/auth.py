"""Authentication, password and session-management endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    token_hash,
    validate_password_policy,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import RefreshSession, User
from app.schemas import ChangePasswordRequest, LoginRequest, SessionResponse, TokenResponse, UserResponse
from app.services.audit import record_audit

router = APIRouter(prefix='/auth', tags=['auth'])
settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path='/api/v1/auth',
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path='/api/v1/auth',
    )


def _create_session(db: Session, user: User, request: Request) -> tuple[str, str, RefreshSession]:
    access_token = create_access_token(user.id, user.role, user.token_version)
    refresh_token, expires_at = create_refresh_token(user.id, user.role, user.token_version)
    session = RefreshSession(
        user_id=user.id,
        token_hash=token_hash(refresh_token),
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get('User-Agent') or '')[:255] or None,
    )
    db.add(session)
    db.flush()
    return access_token, refresh_token, session


def _response(user: User, access_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        must_change_password=user.must_change_password,
    )


@router.post('/login', response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate, apply lockout controls and create a rotatable session."""
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    now = _now()

    if user and user.locked_until and user.locked_until <= now:
        user.locked_until = None
        user.failed_login_attempts = 0

    if user and user.locked_until and user.locked_until > now:
        record_audit(
            db,
            actor=user,
            action='auth.login_blocked',
            entity_type='session',
            entity_id=user.id,
            outcome='blocked',
            details={'reason': 'temporary_lock'},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail='Cuenta bloqueada temporalmente. Intentalo mas tarde.',
        )

    valid = bool(user and user.is_active and verify_password(payload.password, user.password_hash))
    if not valid:
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.max_failed_login_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
            record_audit(
                db,
                actor=user,
                action='auth.login_failed',
                entity_type='session',
                entity_id=user.id,
                outcome='failed',
                details={'attempts': user.failed_login_attempts},
            )
        else:
            record_audit(
                db,
                actor=None,
                action='auth.login_failed',
                entity_type='session',
                outcome='failed',
                details={'email': email, 'reason': 'unknown_or_invalid'},
            )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Correo o contrasena incorrectos')

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    access_token, refresh_token, session = _create_session(db, user, request)
    record_audit(
        db,
        actor=user,
        action='auth.login_success',
        entity_type='session',
        entity_id=session.id,
        details={'role': user.role},
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return _response(user, access_token)


@router.post('/refresh', response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    """Rotate a valid refresh token and issue a new short-lived access token."""
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sesion no disponible')
    try:
        payload = decode_refresh_token(raw_token)
        user_id = uuid.UUID(payload['sub'])
        token_version = int(payload.get('ver', 1))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sesion no valida') from None

    stored = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(raw_token)))
    user = db.get(User, user_id)
    now = _now()
    if (
        stored is None
        or stored.user_id != user_id
        or stored.revoked_at is not None
        or stored.expires_at <= now
        or user is None
        or not user.is_active
        or user.token_version != token_version
    ):
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sesion caducada o revocada')

    stored.revoked_at = now
    stored.last_used_at = now
    access_token, refresh_token, new_session = _create_session(db, user, request)
    record_audit(
        db,
        actor=user,
        action='auth.session_refreshed',
        entity_type='session',
        entity_id=new_session.id,
        details={'rotated_session_id': str(stored.id)},
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return _response(user, access_token)


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(raw_token)))
        if session and session.user_id == user.id and session.revoked_at is None:
            session.revoked_at = _now()
            record_audit(
                db,
                actor=user,
                action='auth.logout',
                entity_type='session',
                entity_id=session.id,
            )
            db.commit()
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post('/change-password', response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TokenResponse:
    if not verify_password(payload.current_password, user.password_hash):
        record_audit(
            db,
            actor=user,
            action='auth.password_change_failed',
            entity_type='user',
            entity_id=user.id,
            outcome='failed',
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='La contrasena actual no es correcta')
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='La nueva contrasena debe ser distinta')
    errors = validate_password_policy(payload.new_password, email=user.email)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    now = _now()
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = now
    user.token_version += 1
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    access_token, refresh_token, new_session = _create_session(db, user, request)
    record_audit(
        db,
        actor=user,
        action='auth.password_changed',
        entity_type='user',
        entity_id=user.id,
        after={'must_change_password': False, 'token_version': user.token_version},
        details={'new_session_id': str(new_session.id)},
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return _response(user, access_token)


@router.get('/sessions', response_model=list[SessionResponse])
def sessions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SessionResponse]:
    current_hash = token_hash(request.cookies[settings.refresh_cookie_name]) if request.cookies.get(settings.refresh_cookie_name) else None
    rows = db.scalars(
        select(RefreshSession)
        .where(RefreshSession.user_id == user.id)
        .order_by(RefreshSession.created_at.desc())
        .limit(30)
    ).all()
    return [
        SessionResponse(
            id=item.id,
            created_at=item.created_at,
            expires_at=item.expires_at,
            last_used_at=item.last_used_at,
            revoked_at=item.revoked_at,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            current=bool(current_hash and item.token_hash == current_hash),
        )
        for item in rows
    ]


@router.delete('/sessions/{session_id}', status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    session = db.get(RefreshSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sesion no encontrada')
    if session.revoked_at is None:
        session.revoked_at = _now()
        record_audit(
            db,
            actor=user,
            action='auth.session_revoked',
            entity_type='session',
            entity_id=session.id,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/me', response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
