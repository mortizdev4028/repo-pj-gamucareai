"""Reusable FastAPI dependencies for authentication and role checks."""
from collections.abc import Callable
import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)
PASSWORD_CHANGE_ALLOWED_PATHS = {
    '/api/v1/auth/me',
    '/api/v1/auth/change-password',
    '/api/v1/auth/logout',
    '/api/v1/auth/refresh',
    '/api/v1/auth/sessions',
}


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user and enforce token/session versioning."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Se requiere autenticacion')
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload['sub'])
        token_version = int(payload.get('ver', 1))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token no valido') from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuario no disponible')
    if token_version != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='La sesion ha sido revocada')
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Debes cambiar la contrasena temporal antes de continuar',
        )
    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Build a dependency that permits only the supplied roles."""
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No tienes permisos para esta operacion')
        return user
    return dependency
