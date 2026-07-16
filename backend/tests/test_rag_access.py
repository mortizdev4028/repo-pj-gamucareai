"""Tests for clinical RAG authorisation and history-aware rules."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import ClinicalEvent, Pet, User
from app.routers.chat import pet_context, verify_scope_access
from app.services.rag import RagService
from app.services.risk_engine import matches


def make_user(role: str) -> User:
    return User(email=f'{role}@example.test', password_hash='unused', role=role)


def test_owner_cannot_request_clinical_scope() -> None:
    with pytest.raises(HTTPException) as error:
        verify_scope_access(make_user('owner'), 'clinical')
    assert error.value.status_code == 403


def test_staff_can_request_clinical_scope() -> None:
    verify_scope_access(make_user('staff'), 'clinical')


def test_owner_can_request_own_pet_scope() -> None:
    verify_scope_access(make_user('owner'), 'pet')


def test_history_rule_reads_clinical_events() -> None:
    pet = Pet(
        external_id='TEST-PET',
        name='Prueba',
        species='dog',
        breed='Mestizo',
        birth_date=date(2020, 1, 1),
        sex='female',
        weight_kg=Decimal('18.0'),
        neutered=True,
    )
    pet.clinical_events.append(
        ClinicalEvent(
            external_id='TEST-EVENT',
            event_date=datetime.now(timezone.utc),
            event_type='consultation',
            title='Revision auricular',
            description='Nuevo episodio de otitis externa.',
            visible_to_owner=True,
        )
    )

    matched, evidence = matches(pet, {'history_contains': ['otitis']})
    assert matched is True
    assert evidence['matched_history'] == ['otitis']


def test_owner_pet_context_excludes_internal_events() -> None:
    pet = Pet(
        external_id='TEST-OWNER-PET',
        name='Luna',
        species='dog',
        breed='Mestizo',
        birth_date=date(2020, 1, 1),
        sex='female',
        weight_kg=Decimal('18.0'),
        neutered=True,
    )
    pet.clinical_events.extend(
        [
            ClinicalEvent(
                external_id='VISIBLE-EVENT',
                event_date=datetime.now(timezone.utc),
                event_type='vaccination',
                title='Vacuna visible',
                description='Registro visible para el propietario.',
                visible_to_owner=True,
            ),
            ClinicalEvent(
                external_id='INTERNAL-EVENT',
                event_date=datetime.now(timezone.utc),
                event_type='internal_note',
                title='Nota interna',
                description='Contenido reservado al personal.',
                visible_to_owner=False,
            ),
        ]
    )

    context = pet_context(pet, owner_view=True)
    assert 'Vacuna visible' in context
    assert 'Nota interna' not in context


def test_owner_vector_filter_includes_pet_and_visibility() -> None:
    vector_filter = RagService._build_filter(
        ['clinical_profile', 'clinical_event'],
        pet_id='pet-123',
        owner_visible_only=True,
    )
    assert vector_filter is not None
    keys = {condition.key for condition in vector_filter.must}
    assert keys == {'content_type', 'pet_id', 'visible_to_owner'}
