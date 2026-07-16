"""Endpoints for the auditable Wakyma mock integration."""
from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from prometheus_client import Counter, Histogram
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import require_roles
from app.integrations.wakyma.service import (
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_ENTITY_TYPES,
    SUPPORTED_SCHEMA_VERSIONS,
    WakymaImportError,
    execute_import,
)
from app.models import ImportBatch, User
from app.schemas import (
    ImportBatchDetailResponse,
    ImportBatchSummaryResponse,
    WakymaImportResponse,
    WakymaIntegrationStatusResponse,
)
from app.services.alert_workflow import recalculate_and_enrich_pet
from app.services.audit import record_audit, snapshot_model

router = APIRouter(prefix='/integrations/wakyma', tags=['integrations'])

IMPORTS_TOTAL = Counter(
    'gamucare_wakyma_imports_total',
    'Mock Wakyma imports by result and mode.',
    ['status', 'mode', 'format'],
)
IMPORT_DURATION = Histogram(
    'gamucare_wakyma_import_duration_seconds',
    'Duration of Wakyma mock imports.',
    ['mode', 'format'],
)
IMPORT_RECORDS = Counter(
    'gamucare_wakyma_records_total',
    'Records handled by the Wakyma mock connector.',
    ['entity', 'status'],
)


@router.get('/status', response_model=WakymaIntegrationStatusResponse)
def integration_status(
    _: User = Depends(require_roles('technical')),
) -> WakymaIntegrationStatusResponse:
    return WakymaIntegrationStatusResponse(
        connector='wakyma_mock',
        mode='file_import',
        supported_formats=['json', 'csv'],
        supported_schema_versions=sorted(SUPPORTED_SCHEMA_VERSIONS),
        supported_entities=sorted(SUPPORTED_ENTITY_TYPES),
        max_file_size_mb=MAX_FILE_SIZE_BYTES // (1024 * 1024),
        real_api_configured=False,
    )


@router.post('/imports', response_model=WakymaImportResponse)
def import_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles('technical')),
) -> WakymaImportResponse:
    """Validate or execute a JSON/CSV import.

    The technical profile may validate and execute controlled mock imports.
    """
    if not dry_run and user.role != 'technical':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Solo el perfil tecnico puede ejecutar importaciones')
    filename = file.filename or 'wakyma_import.json'
    content = file.file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='El fichero supera 5 MB')

    extension = filename.lower().rsplit('.', 1)[-1] if '.' in filename else 'unknown'
    mode = 'validate' if dry_run else 'execute'
    try:
        with IMPORT_DURATION.labels(mode=mode, format=extension).time():
            execution = execute_import(
                db,
                filename=filename,
                content=content,
                requested_by_id=user.id,
                dry_run=dry_run,
            )
    except WakymaImportError as exc:
        IMPORTS_TOTAL.labels(status='rejected', mode=mode, format=extension).inc()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    batch = _load_batch(db, execution.batch.id)
    IMPORTS_TOTAL.labels(status=batch.status, mode=mode, format=batch.file_format).inc()
    for item in batch.items:
        IMPORT_RECORDS.labels(entity=item.entity_type, status=item.status).inc()

    if not dry_run:
        for pet_id in sorted(execution.affected_pet_ids, key=str):
            background_tasks.add_task(recalculate_and_enrich_pet, pet_id)

    record_audit(
        db,
        actor=user,
        action='wakyma.validated' if dry_run else 'wakyma.imported',
        entity_type='import_batch',
        entity_id=batch.id,
        after=snapshot_model(batch),
        details={
            'filename': filename,
            'affected_pets': len(execution.affected_pet_ids),
            'temporary_credentials_count': len(execution.temporary_credentials),
        },
        commit=True,
    )

    return WakymaImportResponse(
        batch=ImportBatchDetailResponse.model_validate(batch),
        temporary_credentials=execution.temporary_credentials,
        affected_pets=len(execution.affected_pet_ids),
    )


@router.get('/imports', response_model=list[ImportBatchSummaryResponse])
def list_imports(
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> list[ImportBatchSummaryResponse]:
    batches = db.scalars(
        select(ImportBatch).order_by(ImportBatch.started_at.desc()).limit(limit)
    ).all()
    return [ImportBatchSummaryResponse.model_validate(batch) for batch in batches]


@router.get('/imports/{batch_id}', response_model=ImportBatchDetailResponse)
def get_import(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> ImportBatchDetailResponse:
    return ImportBatchDetailResponse.model_validate(_load_batch(db, batch_id))


@router.get('/templates/{file_format}')
def download_template(
    file_format: str,
    _: User = Depends(require_roles('technical')),
) -> Response:
    """Return a documented example file without relying on external storage."""
    if file_format == 'json':
        content = _json_template()
        return Response(
            content=content,
            media_type='application/json',
            headers={'Content-Disposition': 'attachment; filename="wakyma_import_template.json"'},
        )
    if file_format == 'csv':
        content = _csv_template()
        return Response(
            content=content,
            media_type='text/csv; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename="wakyma_import_template.csv"'},
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Plantilla no disponible')


def _load_batch(db: Session, batch_id: uuid.UUID) -> ImportBatch:
    batch = db.scalar(
        select(ImportBatch)
        .options(selectinload(ImportBatch.items))
        .where(ImportBatch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Importacion no encontrada')
    return batch


def _json_template() -> str:
    return '''{
  "source": "wakyma_mock",
  "schema_version": "2.0",
  "owners": [
    {
      "external_id": "WK-OWN-DEMO",
      "first_name": "Nombre",
      "last_name": "Apellidos",
      "phone": "600000000",
      "email": "demo@example.test",
      "address": "Direccion ficticia"
    }
  ],
  "pets": [
    {
      "external_id": "WK-PET-DEMO",
      "owner_external_id": "WK-OWN-DEMO",
      "name": "Demo",
      "species": "dog",
      "breed": "Mestizo",
      "birth_date": "2021-01-15",
      "sex": "female",
      "weight_kg": 18.5,
      "neutered": true,
      "microchip": "724000000000000"
    }
  ],
  "clinical_events": [
    {
      "external_id": "WK-EVT-DEMO",
      "pet_external_id": "WK-PET-DEMO",
      "event_date": "2026-01-20T10:30:00+00:00",
      "event_type": "consultation",
      "title": "Revision general",
      "description": "Evento clinico ficticio",
      "visible_to_owner": true
    }
  ]
}\n'''


def _csv_template() -> str:
    fields = [
        'entity_type', 'external_id', 'owner_external_id', 'pet_external_id',
        'first_name', 'last_name', 'phone', 'email', 'address', 'name', 'species',
        'breed', 'birth_date', 'sex', 'weight_kg', 'neutered', 'microchip',
        'allergies', 'chronic_conditions', 'event_date', 'event_type', 'title',
        'description', 'diagnosis', 'treatment', 'visible_to_owner', 'is_active',
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerow({
        'entity_type': 'owner', 'external_id': 'WK-OWN-DEMO', 'first_name': 'Nombre',
        'last_name': 'Apellidos', 'phone': '600000000', 'email': 'demo@example.test',
        'address': 'Direccion ficticia', 'is_active': 'true',
    })
    writer.writerow({
        'entity_type': 'pet', 'external_id': 'WK-PET-DEMO', 'owner_external_id': 'WK-OWN-DEMO',
        'name': 'Demo', 'species': 'dog', 'breed': 'Mestizo', 'birth_date': '2021-01-15',
        'sex': 'female', 'weight_kg': '18.5', 'neutered': 'true',
        'microchip': '724000000000000', 'is_active': 'true',
    })
    writer.writerow({
        'entity_type': 'clinical_event', 'external_id': 'WK-EVT-DEMO',
        'pet_external_id': 'WK-PET-DEMO', 'event_date': '2026-01-20T10:30:00+00:00',
        'event_type': 'consultation', 'title': 'Revision general',
        'description': 'Evento clinico ficticio', 'visible_to_owner': 'true',
    })
    return output.getvalue()
