"""Unit tests for the four-profile permission model."""

import pytest
from fastapi import HTTPException

from app.dependencies import require_roles
from app.models import User


def make_user(role: str) -> User:
    """Create an in-memory user suitable for dependency tests."""
    return User(email=f'{role}@example.test', password_hash='not-used', role=role)


def test_clinic_can_use_write_dependency() -> None:
    dependency = require_roles('clinic')
    user = make_user('clinic')
    assert dependency(user) is user


def test_staff_is_rejected_by_write_dependency() -> None:
    dependency = require_roles('clinic')
    with pytest.raises(HTTPException) as error:
        dependency(make_user('staff'))
    assert error.value.status_code == 403


def test_staff_and_clinic_can_use_business_read_dependency() -> None:
    dependency = require_roles('clinic', 'staff')
    assert dependency(make_user('clinic')).role == 'clinic'
    assert dependency(make_user('staff')).role == 'staff'


def test_technical_can_use_technical_dependency() -> None:
    dependency = require_roles('technical')
    assert dependency(make_user('technical')).role == 'technical'


def test_business_roles_cannot_use_technical_dependency() -> None:
    dependency = require_roles('technical')
    for role in ('clinic', 'staff', 'owner'):
        with pytest.raises(HTTPException) as error:
            dependency(make_user(role))
        assert error.value.status_code == 403


def test_technical_cannot_use_business_dependency() -> None:
    dependency = require_roles('clinic', 'staff', 'owner')
    with pytest.raises(HTTPException) as error:
        dependency(make_user('technical'))
    assert error.value.status_code == 403
