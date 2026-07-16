"""Security unit tests for password policy and JWT session claims."""
import uuid

import pytest
import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    token_hash,
    validate_password_policy,
    verify_password,
)


def test_password_roundtrip() -> None:
    password = 'GamuCare123!'
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password('incorrecta', hashed)


def test_password_policy_accepts_strong_password() -> None:
    assert validate_password_policy('OtraClave2026!', email='owner@example.test') == []


def test_password_policy_reports_all_basic_failures() -> None:
    errors = validate_password_policy('corta', email='owner@example.test')
    assert any('12 caracteres' in item for item in errors)
    assert any('mayuscula' in item for item in errors)
    assert any('numero' in item for item in errors)
    assert any('especial' in item for item in errors)


def test_password_policy_rejects_email_local_part() -> None:
    errors = validate_password_policy('Owner2026!Clave', email='owner@example.test')
    assert any('correo electronico' in item for item in errors)


def test_access_and_refresh_tokens_are_not_interchangeable() -> None:
    user_id = uuid.uuid4()
    access = create_access_token(user_id, 'clinic', token_version=3)
    refresh, _ = create_refresh_token(user_id, 'clinic', token_version=3)
    assert decode_access_token(access)['ver'] == 3
    assert decode_refresh_token(refresh)['type'] == 'refresh'
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(refresh)
    with pytest.raises(jwt.InvalidTokenError):
        decode_refresh_token(access)


def test_refresh_tokens_are_stored_as_hashes() -> None:
    token, _ = create_refresh_token(uuid.uuid4(), 'owner')
    digest = token_hash(token)
    assert len(digest) == 64
    assert token not in digest
