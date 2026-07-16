"""Password, session and JWT security helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings

settings = get_settings()
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id before storing it."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Safely verify a password without leaking mismatch details."""
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_policy(password: str, *, email: str | None = None) -> list[str]:
    """Return human-readable password policy failures."""
    errors: list[str] = []
    if len(password) < settings.password_min_length:
        errors.append(f'Debe tener al menos {settings.password_min_length} caracteres')
    if not re.search(r'[a-z]', password):
        errors.append('Debe incluir una letra minuscula')
    if not re.search(r'[A-Z]', password):
        errors.append('Debe incluir una letra mayuscula')
    if not re.search(r'\d', password):
        errors.append('Debe incluir un numero')
    if not re.search(r'[^A-Za-z0-9]', password):
        errors.append('Debe incluir un caracter especial')
    if email:
        local_part = email.split('@', 1)[0].lower()
        if len(local_part) >= 4 and local_part in password.lower():
            errors.append('No debe contener el nombre del correo electronico')
    return errors


def _token_payload(user_id: uuid.UUID, role: str, token_version: int, token_type: str, expires_delta: timedelta) -> dict:
    now = datetime.now(timezone.utc)
    return {
        'sub': str(user_id),
        'role': role,
        'ver': token_version,
        'type': token_type,
        'jti': str(uuid.uuid4()),
        'iat': now,
        'nbf': now,
        'exp': now + expires_delta,
        'iss': 'gamucare-ai',
        'aud': 'gamucare-web',
    }


def create_access_token(user_id: uuid.UUID, role: str, token_version: int = 1) -> str:
    """Create a short-lived signed access token."""
    payload = _token_payload(
        user_id,
        role,
        token_version,
        'access',
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, role: str, token_version: int = 1) -> tuple[str, datetime]:
    """Create a refresh token and return its expiry timestamp."""
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = _token_payload(
        user_id,
        role,
        token_version,
        'refresh',
        timedelta(days=settings.refresh_token_expire_days),
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), expires


def _decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience='gamucare-web',
        issuer='gamucare-ai',
    )
    if payload.get('type') != expected_type:
        raise jwt.InvalidTokenError('Tipo de token incorrecto')
    return payload


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token."""
    return _decode_token(token, 'access')


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token."""
    return _decode_token(token, 'refresh')


def token_hash(token: str) -> str:
    """Return a non-reversible identifier used to store refresh sessions."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
