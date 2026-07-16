"""Tests for the auditable Wakyma mock import pipeline."""
from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.integrations.wakyma.service import WakymaImportError, execute_import, parse_export
from app.models import ClinicalEvent, Owner, Pet, User


def make_db() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return Session(engine)


def clinic_user(db: Session) -> User:
    user = User(email='clinic@test.local', password_hash='unused', role='clinic')
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def valid_payload() -> bytes:
    return json.dumps({
        'source': 'wakyma_mock',
        'schema_version': '2.0',
        'owners': [{
            'external_id': 'WK-O-1', 'first_name': 'Ana', 'last_name': 'Demo',
            'phone': '600000001', 'email': 'ana@example.test', 'address': 'Madrid',
        }],
        'pets': [{
            'external_id': 'WK-P-1', 'owner_external_id': 'WK-O-1', 'name': 'Luna',
            'species': 'dog', 'breed': 'Mestizo', 'birth_date': '2021-01-01',
            'sex': 'female', 'weight_kg': 18.2, 'neutered': True,
        }],
        'clinical_events': [{
            'external_id': 'WK-E-1', 'pet_external_id': 'WK-P-1',
            'event_date': '2026-01-15T10:00:00+00:00', 'event_type': 'consultation',
            'title': 'Revision', 'description': 'Revision general ficticia',
            'visible_to_owner': True,
        }],
    }).encode()


def test_dry_run_does_not_modify_business_data() -> None:
    db = make_db()
    user = clinic_user(db)
    execution = execute_import(
        db, filename='demo.json', content=valid_payload(), requested_by_id=user.id, dry_run=True
    )
    assert execution.batch.status == 'validated'
    assert execution.batch.records_processed == 3
    assert db.scalar(select(Owner)) is None
    assert db.scalar(select(Pet)) is None
    assert db.scalar(select(ClinicalEvent)) is None


def test_execute_creates_and_then_updates_records() -> None:
    db = make_db()
    user = clinic_user(db)
    first = execute_import(
        db, filename='demo.json', content=valid_payload(), requested_by_id=user.id, dry_run=False
    )
    assert first.batch.status == 'completed'
    assert first.batch.records_created == 3
    assert len(first.temporary_credentials) == 1
    assert db.scalar(select(Owner).where(Owner.external_id == 'WK-O-1')) is not None
    assert db.scalar(select(Pet).where(Pet.external_id == 'WK-P-1')).name == 'Luna'
    assert db.scalar(select(ClinicalEvent).where(ClinicalEvent.external_id == 'WK-E-1')) is not None

    payload = json.loads(valid_payload())
    payload['pets'][0]['weight_kg'] = 19.4
    second = execute_import(
        db, filename='demo.json', content=json.dumps(payload).encode(), requested_by_id=user.id, dry_run=False
    )
    assert second.batch.records_updated == 3
    assert float(db.scalar(select(Pet).where(Pet.external_id == 'WK-P-1')).weight_kg) == 19.4


def test_invalid_reference_is_recorded_without_aborting_file() -> None:
    db = make_db()
    user = clinic_user(db)
    payload = json.loads(valid_payload())
    payload['pets'][0]['owner_external_id'] = 'MISSING'
    result = execute_import(
        db, filename='bad.json', content=json.dumps(payload).encode(), requested_by_id=user.id, dry_run=True
    )
    assert result.batch.records_failed == 2
    assert result.batch.status == 'validated_with_errors'
    error = next(item for item in result.batch.items if item.status == 'error')
    assert 'Propietario no encontrado' in (error.message or '')


def test_csv_mixed_entities_are_supported() -> None:
    content = (
        'entity_type,external_id,owner_external_id,pet_external_id,first_name,last_name,phone,email,address,name,species,breed,birth_date,sex,weight_kg,neutered,event_date,event_type,title,description,visible_to_owner\n'
        'owner,WK-O-2,,,Luis,Demo,600000002,luis@example.test,Madrid,,,,,,,,,,,,\n'
        'pet,WK-P-2,WK-O-2,,,,,,,Nala,cat,Comun Europeo,2022-01-01,female,4.1,true,,,,,\n'
        'clinical_event,WK-E-2,,WK-P-2,,,,,,,,,,,,,2026-02-01T09:00:00+00:00,vaccination,Vacuna,Evento ficticio,true\n'
    ).encode()
    parsed = parse_export('demo.csv', content)
    assert [record.entity_type for record in parsed.records] == ['owner', 'pet', 'clinical_event']


def test_rejects_unknown_file_format() -> None:
    try:
        parse_export('demo.txt', b'hello')
    except WakymaImportError as exc:
        assert 'JSON o CSV' in str(exc)
    else:
        raise AssertionError('Expected WakymaImportError')
