"""Create a machine-readable release snapshot for demonstration evidence.

The command only reads application data. It intentionally avoids owner contact
fields and clinical text so that the evidence package contains aggregate values,
not personal or sensitive-looking demonstration records.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    ClinicalEvent,
    HealthPlan,
    ImportBatch,
    Owner,
    Pet,
    PetPlanSubscription,
    RagDocument,
    RagEvaluationRun,
    RiskAlert,
    SystemEvaluationRun,
    User,
)
from app.services.observability import dependency_status
from app.version import APP_VERSION

settings = get_settings()


def _scalar_count(db: Any, model: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _group_count(db: Any, model: Any, field: Any) -> dict[str, int]:
    rows = db.execute(select(field, func.count()).select_from(model).group_by(field)).all()
    return {str(value): int(total) for value, total in rows}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def build_snapshot() -> dict[str, Any]:
    """Build a deterministic aggregate view of the current installation."""
    db = SessionLocal()
    try:
        latest_rag = db.scalar(select(RagEvaluationRun).order_by(RagEvaluationRun.started_at.desc()).limit(1))
        latest_system = db.scalar(select(SystemEvaluationRun).order_by(SystemEvaluationRun.started_at.desc()).limit(1))
        snapshot: dict[str, Any] = {
            'release': {
                'application': settings.app_name,
                'version': APP_VERSION,
                'environment': settings.app_env,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'scope': 'local_docker_mvp_without_aws',
            },
            'dataset': {
                'users': _scalar_count(db, User),
                'users_by_role': _group_count(db, User, User.role),
                'owners': _scalar_count(db, Owner),
                'pets': _scalar_count(db, Pet),
                'clinical_events': _scalar_count(db, ClinicalEvent),
                'health_plans': _scalar_count(db, HealthPlan),
                'subscriptions': _scalar_count(db, PetPlanSubscription),
                'subscriptions_by_status': _group_count(db, PetPlanSubscription, PetPlanSubscription.status),
                'preventive_alerts': _scalar_count(db, RiskAlert),
                'alerts_by_status': _group_count(db, RiskAlert, RiskAlert.status),
                'rag_documents': _scalar_count(db, RagDocument),
                'rag_documents_by_status': _group_count(db, RagDocument, RagDocument.ingestion_status),
                'wakyma_batches': _scalar_count(db, ImportBatch),
            },
            'latest_evaluations': {
                'vetia': None if latest_rag is None else {
                    'mode': latest_rag.mode,
                    'status': latest_rag.status,
                    'dataset': latest_rag.dataset_name,
                    'cases_total': latest_rag.cases_total,
                    'model': latest_rag.model_name,
                    'metrics': latest_rag.metrics,
                    'started_at': latest_rag.started_at,
                    'finished_at': latest_rag.finished_at,
                },
                'mvp': None if latest_system is None else {
                    'status': latest_system.status,
                    'suite': latest_system.suite_name,
                    'app_version': latest_system.app_version,
                    'tests_total': latest_system.tests_total,
                    'tests_passed': latest_system.tests_passed,
                    'tests_failed': latest_system.tests_failed,
                    'coverage_percent': latest_system.coverage_percent,
                    'metrics': latest_system.metrics,
                    'started_at': latest_system.started_at,
                    'finished_at': latest_system.finished_at,
                },
            },
            'dependencies': dependency_status(),
            'limitations': [
                'Datos y casos clinicos completamente ficticios.',
                'La aplicacion no sustituye el criterio de un profesional veterinario.',
                'Las fuentes externas deben revisarse antes de un uso distinto del academico.',
                'No existe despliegue AWS dentro del alcance congelado.',
            ],
        }
        return snapshot
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', help='Optional JSON path. Parent directories are created automatically.')
    args = parser.parse_args()

    snapshot = build_snapshot()
    rendered = json.dumps(snapshot, ensure_ascii=False, indent=2, default=_json_default)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + '\n', encoding='utf-8')
        print(path)
    else:
        print(rendered)


if __name__ == '__main__':
    main()
