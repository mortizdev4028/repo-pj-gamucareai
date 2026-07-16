"""Auditable mock integration for Wakyma JSON and CSV exports.

The module deliberately separates parsing, validation and persistence. The
current connector consumes fictitious files, but the normalized records are
independent from the transport so a future API client can reuse the same import
pipeline.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
import hashlib
import io
import json
import secrets
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.services.audit import sanitize_mapping
from app.models import ClinicalEvent, ImportBatch, ImportBatchItem, Owner, Pet, User, utcnow

SUPPORTED_SCHEMA_VERSIONS = {'1.0', '2.0'}
SUPPORTED_ENTITY_TYPES = {'owner', 'pet', 'clinical_event'}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


@dataclass(slots=True)
class NormalizedRecord:
    row_number: int
    entity_type: str
    external_id: str | None
    data: dict[str, Any]


@dataclass(slots=True)
class ParsedExport:
    file_format: str
    schema_version: str
    records: list[NormalizedRecord]


@dataclass(slots=True)
class ImportExecution:
    batch: ImportBatch
    affected_pet_ids: set[uuid.UUID] = field(default_factory=set)
    temporary_credentials: list[dict[str, str]] = field(default_factory=list)


class WakymaImportError(ValueError):
    """Raised when an import file cannot be parsed at all."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _parse_bool(value: Any, *, default: bool | None = None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = (_clean(value) or '').lower()
    if not normalized and default is not None:
        return default
    if normalized in {'true', '1', 'yes', 'si', 's'}:
        return True
    if normalized in {'false', '0', 'no', 'n'}:
        return False
    raise ValueError('Debe ser un valor booleano')


def _parse_date(value: Any, field_name: str) -> date:
    normalized = _clean(value)
    if not normalized:
        raise ValueError(f'Falta {field_name}')
    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f'{field_name} debe usar formato YYYY-MM-DD') from exc


def _parse_datetime(value: Any, field_name: str) -> datetime:
    normalized = _clean(value)
    if not normalized:
        raise ValueError(f'Falta {field_name}')
    try:
        parsed = datetime.fromisoformat(normalized.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{field_name} debe usar formato ISO 8601') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_decimal(value: Any, field_name: str, *, optional: bool = False) -> Decimal | None:
    normalized = _clean(value)
    if normalized is None and optional:
        return None
    if normalized is None:
        raise ValueError(f'Falta {field_name}')
    try:
        result = Decimal(normalized.replace(',', '.'))
    except InvalidOperation as exc:
        raise ValueError(f'{field_name} no es numerico') from exc
    if result <= 0:
        raise ValueError(f'{field_name} debe ser mayor que cero')
    return result


def _require(data: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if _clean(data.get(field)) is None]
    if missing:
        raise ValueError(f"Faltan campos obligatorios: {', '.join(missing)}")


def _valid_email(value: str) -> bool:
    _, address = parseaddr(value)
    return bool(address and '@' in address and '.' in address.rsplit('@', 1)[-1])


def parse_export(filename: str, content: bytes) -> ParsedExport:
    """Parse a JSON or mixed-entity CSV export into normalized records."""
    if not content:
        raise WakymaImportError('El fichero esta vacio')
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise WakymaImportError('El fichero supera el limite de 5 MB')

    extension = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    if extension == 'json':
        return _parse_json(content)
    if extension == 'csv':
        return _parse_csv(content)
    raise WakymaImportError('Solo se admiten ficheros JSON o CSV')


def _parse_json(content: bytes) -> ParsedExport:
    try:
        payload = json.loads(content.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WakymaImportError('El JSON no es valido o no esta codificado en UTF-8') from exc
    if not isinstance(payload, dict):
        raise WakymaImportError('La raiz del JSON debe ser un objeto')
    if payload.get('source') != 'wakyma_mock':
        raise WakymaImportError('El fichero no identifica el origen wakyma_mock')
    schema_version = str(payload.get('schema_version', '1.0'))
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise WakymaImportError(f'Version de esquema no soportada: {schema_version}')

    records: list[NormalizedRecord] = []
    row = 1
    for entity_type, key in (
        ('owner', 'owners'), ('pet', 'pets'), ('clinical_event', 'clinical_events')
    ):
        values = payload.get(key, [])
        if not isinstance(values, list):
            raise WakymaImportError(f'El campo {key} debe ser una lista')
        for item in values:
            row += 1
            if not isinstance(item, dict):
                item = {'_invalid_value': item}
            records.append(
                NormalizedRecord(
                    row_number=row,
                    entity_type=entity_type,
                    external_id=_clean(item.get('external_id')),
                    data=dict(item),
                )
            )
    return ParsedExport(file_format='json', schema_version=schema_version, records=records)


def _parse_csv(content: bytes) -> ParsedExport:
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise WakymaImportError('El CSV debe estar codificado en UTF-8') from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or 'entity_type' not in reader.fieldnames:
        raise WakymaImportError('El CSV debe incluir la columna entity_type')
    records: list[NormalizedRecord] = []
    for row_number, row in enumerate(reader, start=2):
        entity_type = (_clean(row.get('entity_type')) or '').lower()
        records.append(
            NormalizedRecord(
                row_number=row_number,
                entity_type=entity_type,
                external_id=_clean(row.get('external_id')),
                data={key: value for key, value in row.items() if value not in (None, '')},
            )
        )
    return ParsedExport(file_format='csv', schema_version='2.0', records=records)


def _validate_owner(data: dict[str, Any]) -> dict[str, Any]:
    _require(data, 'external_id', 'first_name', 'last_name', 'phone', 'email', 'address')
    email = _clean(data['email']).lower()  # type: ignore[union-attr]
    if not _valid_email(email):
        raise ValueError('El correo electronico no es valido')
    return {
        'external_id': _clean(data['external_id']),
        'first_name': _clean(data['first_name']),
        'last_name': _clean(data['last_name']),
        'phone': _clean(data['phone']),
        'email': email,
        'address': _clean(data['address']),
        'is_active': _parse_bool(data.get('is_active'), default=True),
    }


def _validate_pet(data: dict[str, Any]) -> dict[str, Any]:
    _require(
        data, 'external_id', 'owner_external_id', 'name', 'species', 'breed',
        'birth_date', 'sex', 'weight_kg',
    )
    species = (_clean(data['species']) or '').lower()
    if species not in {'dog', 'cat'}:
        raise ValueError('species debe ser dog o cat')
    sex = (_clean(data['sex']) or '').lower()
    if sex not in {'male', 'female'}:
        raise ValueError('sex debe ser male o female')
    return {
        'external_id': _clean(data['external_id']),
        'owner_external_id': _clean(data['owner_external_id']),
        'name': _clean(data['name']),
        'species': species,
        'breed': _clean(data['breed']),
        'birth_date': _parse_date(data['birth_date'], 'birth_date'),
        'sex': sex,
        'weight_kg': _parse_decimal(data['weight_kg'], 'weight_kg'),
        'neutered': _parse_bool(data.get('neutered'), default=False),
        'microchip': _clean(data.get('microchip')),
        'allergies': _clean(data.get('allergies')),
        'chronic_conditions': _clean(data.get('chronic_conditions')),
        'is_active': _parse_bool(data.get('is_active'), default=True),
    }


def _validate_event(data: dict[str, Any]) -> dict[str, Any]:
    _require(
        data, 'external_id', 'pet_external_id', 'event_date', 'event_type',
        'title', 'description',
    )
    return {
        'external_id': _clean(data['external_id']),
        'pet_external_id': _clean(data['pet_external_id']),
        'event_date': _parse_datetime(data['event_date'], 'event_date'),
        'event_type': _clean(data['event_type']),
        'title': _clean(data['title']),
        'description': _clean(data['description']),
        'diagnosis': _clean(data.get('diagnosis')),
        'treatment': _clean(data.get('treatment')),
        'weight_kg': _parse_decimal(data.get('weight_kg'), 'weight_kg', optional=True),
        'visible_to_owner': _parse_bool(data.get('visible_to_owner'), default=True),
    }


def _normalize_record(record: NormalizedRecord) -> dict[str, Any]:
    if record.entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError('entity_type debe ser owner, pet o clinical_event')
    if record.entity_type == 'owner':
        return _validate_owner(record.data)
    if record.entity_type == 'pet':
        return _validate_pet(record.data)
    return _validate_event(record.data)


def _existing_action(db: Session, entity_type: str, external_id: str) -> str:
    model = {'owner': Owner, 'pet': Pet, 'clinical_event': ClinicalEvent}[entity_type]
    return 'update' if db.scalar(select(model.id).where(model.external_id == external_id)) else 'create'


def _email_conflict(db: Session, email: str, external_id: str) -> bool:
    owner = db.scalar(select(Owner).where(Owner.email == email))
    if owner and owner.external_id != external_id:
        return True
    user = db.scalar(select(User).where(User.email == email))
    return bool(user and (not user.owner or user.owner.external_id != external_id))


def execute_import(
    db: Session,
    *,
    filename: str,
    content: bytes,
    requested_by_id: uuid.UUID,
    dry_run: bool,
) -> ImportExecution:
    """Validate and optionally upsert a fictitious Wakyma export.

    Dry runs are persisted as audit batches but never modify business entities.
    Invalid rows do not abort valid rows; every result is recorded individually.
    """
    checksum = hashlib.sha256(content).hexdigest()
    parsed = parse_export(filename, content)
    batch = ImportBatch(
        source='wakyma_mock',
        filename=filename,
        status='validating' if dry_run else 'processing',
        requested_by_id=requested_by_id,
        file_format=parsed.file_format,
        schema_version=parsed.schema_version,
        checksum=checksum,
        dry_run=dry_run,
        records_total=len(parsed.records),
    )
    db.add(batch)
    db.flush()

    execution = ImportExecution(batch=batch)
    normalized: list[tuple[NormalizedRecord, dict[str, Any], str]] = []
    seen: set[tuple[str, str]] = set()

    # First pass: field-level validation and duplicate detection.
    for record in parsed.records:
        try:
            values = _normalize_record(record)
            external_id = str(values['external_id'])
            key = (record.entity_type, external_id)
            if key in seen:
                raise ValueError('Identificador externo duplicado dentro del fichero')
            seen.add(key)
            if record.entity_type == 'owner':
                if _email_conflict(db, str(values['email']), external_id):
                    raise ValueError('El correo ya pertenece a otro cliente o usuario')
            action = _existing_action(db, record.entity_type, external_id)
            normalized.append((record, values, action))
        except ValueError as exc:
            batch.records_failed += 1
            db.add(ImportBatchItem(
                batch=batch,
                row_number=record.row_number,
                entity_type=record.entity_type or 'unknown',
                external_id=record.external_id,
                action='none',
                status='error',
                message=str(exc),
                payload=_safe_payload(record.data),
            ))

    # Second pass: relational references and write operations in dependency order.
    order = {'owner': 0, 'pet': 1, 'clinical_event': 2}
    normalized.sort(key=lambda entry: (order[entry[0].entity_type], entry[0].row_number))
    owner_cache: dict[str, Owner] = {}
    pet_cache: dict[str, Pet] = {}
    available_owner_ids: set[str] = set()
    available_pet_ids: set[str] = set()

    for record, values, action in normalized:
        try:
            if record.entity_type == 'owner':
                owner = _upsert_owner(db, values, dry_run, execution)
                available_owner_ids.add(str(values['external_id']))
                if owner is not None:
                    owner_cache[str(values['external_id'])] = owner
            elif record.entity_type == 'pet':
                owner_external_id = str(values['owner_external_id'])
                owner = owner_cache.get(owner_external_id) or db.scalar(
                    select(Owner).where(Owner.external_id == owner_external_id)
                )
                if owner is None and owner_external_id not in available_owner_ids:
                    raise ValueError(f'Propietario no encontrado o rechazado: {owner_external_id}')
                if dry_run:
                    pet = db.scalar(select(Pet).where(Pet.external_id == values['external_id']))
                    available_pet_ids.add(str(values['external_id']))
                    if pet is not None:
                        pet_cache[str(values['external_id'])] = pet
                else:
                    if owner is None:
                        raise ValueError(f'El propietario {owner_external_id} no se pudo importar')
                    pet = _upsert_pet(db, values, owner, False)
                    if pet is not None:
                        available_pet_ids.add(str(values['external_id']))
                        pet_cache[str(values['external_id'])] = pet
                        execution.affected_pet_ids.add(pet.id)
            else:
                pet_external_id = str(values['pet_external_id'])
                pet = pet_cache.get(pet_external_id) or db.scalar(
                    select(Pet).where(Pet.external_id == pet_external_id)
                )
                if pet is None and pet_external_id not in available_pet_ids:
                    raise ValueError(f'Mascota no encontrada o rechazada: {pet_external_id}')
                if not dry_run:
                    if pet is None:
                        raise ValueError(f'La mascota {pet_external_id} no se pudo importar')
                    _upsert_event(db, values, pet, False)
                    execution.affected_pet_ids.add(pet.id)

            batch.records_processed += 1
            if action == 'create':
                batch.records_created += 1
            else:
                batch.records_updated += 1
            db.add(ImportBatchItem(
                batch=batch,
                row_number=record.row_number,
                entity_type=record.entity_type,
                external_id=str(values['external_id']),
                action=action,
                status='validated' if dry_run else 'success',
                message='Validacion correcta' if dry_run else f'Registro {action}d correctamente',
                payload=_safe_payload(values),
            ))
        except ValueError as exc:
            batch.records_failed += 1
            db.add(ImportBatchItem(
                batch=batch,
                row_number=record.row_number,
                entity_type=record.entity_type,
                external_id=record.external_id,
                action=action,
                status='error',
                message=str(exc),
                payload=_safe_payload(record.data),
            ))

    batch.error_details = [
        {'row': item.row_number, 'entity_type': item.entity_type, 'external_id': item.external_id, 'message': item.message}
        for item in batch.items if item.status == 'error'
    ]
    batch.summary = {
        'owners': _count_items(batch.items, 'owner'),
        'pets': _count_items(batch.items, 'pet'),
        'clinical_events': _count_items(batch.items, 'clinical_event'),
        'rag_reindex_scheduled': bool(execution.affected_pet_ids and not dry_run),
        'alerts_recalculation_scheduled': bool(execution.affected_pet_ids and not dry_run),
    }
    batch.status = _final_status(batch, dry_run)
    batch.finished_at = utcnow()
    db.commit()
    db.refresh(batch)
    return execution


def _upsert_owner(
    db: Session,
    values: dict[str, Any],
    dry_run: bool,
    execution: ImportExecution,
) -> Owner | None:
    owner = db.scalar(select(Owner).where(Owner.external_id == values['external_id']))
    if dry_run:
        return owner
    if owner is None:
        temporary_password = f'{secrets.token_urlsafe(10)}A1!'
        user = User(
            email=values['email'],
            password_hash=hash_password(temporary_password),
            role='owner',
            is_active=values['is_active'],
            must_change_password=True,
        )
        owner = Owner(user=user, **values)
        db.add(owner)
        db.flush()
        execution.temporary_credentials.append({
            'external_id': str(values['external_id']),
            'email': str(values['email']),
            'temporary_password': temporary_password,
        })
        return owner
    for field_name in ('first_name', 'last_name', 'phone', 'email', 'address', 'is_active'):
        setattr(owner, field_name, values[field_name])
    if owner.user:
        owner.user.email = values['email']
        owner.user.is_active = values['is_active']
    return owner


def _upsert_pet(db: Session, values: dict[str, Any], owner: Owner, dry_run: bool) -> Pet | None:
    pet = db.scalar(select(Pet).where(Pet.external_id == values['external_id']))
    if dry_run:
        return pet
    fields = {key: value for key, value in values.items() if key not in {'external_id', 'owner_external_id'}}
    if pet is None:
        pet = Pet(external_id=values['external_id'], owner=owner, **fields)
        db.add(pet)
        db.flush()
        return pet
    pet.owner = owner
    for field_name, value in fields.items():
        setattr(pet, field_name, value)
    return pet


def _upsert_event(db: Session, values: dict[str, Any], pet: Pet, dry_run: bool) -> ClinicalEvent | None:
    event = db.scalar(select(ClinicalEvent).where(ClinicalEvent.external_id == values['external_id']))
    if dry_run:
        return event
    fields = {key: value for key, value in values.items() if key not in {'external_id', 'pet_external_id'}}
    if event is None:
        event = ClinicalEvent(external_id=values['external_id'], pet=pet, **fields)
        db.add(event)
        db.flush()
        return event
    event.pet = pet
    for field_name, value in fields.items():
        setattr(event, field_name, value)
    return event


def _safe_payload(values: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, (date, datetime)):
            payload[key] = value.isoformat()
        elif isinstance(value, Decimal):
            payload[key] = str(value)
        else:
            payload[key] = value
    return sanitize_mapping(payload) or {}


def _count_items(items: list[ImportBatchItem], entity_type: str) -> dict[str, int]:
    selected = [item for item in items if item.entity_type == entity_type]
    return {
        'total': len(selected),
        'success': sum(item.status in {'success', 'validated'} for item in selected),
        'errors': sum(item.status == 'error' for item in selected),
    }


def _final_status(batch: ImportBatch, dry_run: bool) -> str:
    if batch.records_total == 0:
        return 'empty'
    if batch.records_failed == batch.records_total:
        return 'validation_failed' if dry_run else 'failed'
    if batch.records_failed:
        return 'validated_with_errors' if dry_run else 'completed_with_errors'
    return 'validated' if dry_run else 'completed'
