"""Compatibility wrapper for command-line imports.

HTTP imports use :mod:`app.integrations.wakyma.service`. This adapter remains so
existing scripts and documentation keep working while sharing the new parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from app.integrations.wakyma.service import execute_import


@dataclass(slots=True)
class ImportResult:
    owners_created: int = 0
    owners_updated: int = 0
    pets_created: int = 0
    pets_updated: int = 0
    events_created: int = 0
    events_updated: int = 0
    records_failed: int = 0


class MockWakymaAdapter:
    """Import a documented JSON or CSV file using the auditable pipeline."""

    def import_data(self, db: Session, path: str | Path, requested_by_id: uuid.UUID) -> ImportResult:
        import_path = Path(path)
        execution = execute_import(
            db,
            filename=import_path.name,
            content=import_path.read_bytes(),
            requested_by_id=requested_by_id,
            dry_run=False,
        )
        items = execution.batch.items
        return ImportResult(
            owners_created=sum(i.entity_type == 'owner' and i.action == 'create' and i.status == 'success' for i in items),
            owners_updated=sum(i.entity_type == 'owner' and i.action == 'update' and i.status == 'success' for i in items),
            pets_created=sum(i.entity_type == 'pet' and i.action == 'create' and i.status == 'success' for i in items),
            pets_updated=sum(i.entity_type == 'pet' and i.action == 'update' and i.status == 'success' for i in items),
            events_created=sum(i.entity_type == 'clinical_event' and i.action == 'create' and i.status == 'success' for i in items),
            events_updated=sum(i.entity_type == 'clinical_event' and i.action == 'update' and i.status == 'success' for i in items),
            records_failed=execution.batch.records_failed,
        )
