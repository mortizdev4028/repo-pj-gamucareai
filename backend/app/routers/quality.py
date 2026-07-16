"""Formal quality evaluation endpoints for the MVP."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_roles
from app.models import SystemEvaluationRun, User
from app.schemas import QualityStatusResponse, SystemEvaluationRunRequest, SystemEvaluationRunResponse
from app.services.system_evaluation import SystemEvaluator
from app.version import APP_VERSION

router = APIRouter(prefix='/quality', tags=['quality'])
settings = get_settings()
EVALUATIONS = Counter('gamucare_quality_evaluations_total', 'Formal quality evaluations', ['status'])
EVALUATION_DURATION = Histogram('gamucare_quality_evaluation_duration_seconds', 'Formal evaluation duration')


def _serialise(run: SystemEvaluationRun) -> SystemEvaluationRunResponse:
    return SystemEvaluationRunResponse(
        id=run.id,
        app_version=run.app_version,
        status=run.status,
        suite_name=run.suite_name,
        tests_total=run.tests_total,
        tests_passed=run.tests_passed,
        tests_failed=run.tests_failed,
        coverage_percent=run.coverage_percent,
        metrics=run.metrics,
        details=run.details,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get('/status', response_model=QualityStatusResponse)
def quality_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> QualityStatusResponse:
    evaluator = SystemEvaluator()
    latest = db.scalar(select(SystemEvaluationRun).order_by(SystemEvaluationRun.started_at.desc()).limit(1))
    return QualityStatusResponse(
        app_version=APP_VERSION,
        acceptance_dataset=evaluator.acceptance_path.stem,
        alert_dataset=evaluator.alert_path.stem,
        latest_run_id=latest.id if latest else None,
        latest_run_status=latest.status if latest else None,
        latest_run_at=latest.started_at if latest else None,
        automated_criteria=len(evaluator.load_acceptance_criteria()),
        report_available=bool(latest and latest.report_markdown),
    )


@router.get('/evaluation/latest', response_model=SystemEvaluationRunResponse | None)
def latest_evaluation(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
):
    run = db.scalar(select(SystemEvaluationRun).order_by(SystemEvaluationRun.started_at.desc()).limit(1))
    return _serialise(run) if run else None


@router.post('/evaluation/run', response_model=SystemEvaluationRunResponse)
async def run_evaluation(
    payload: SystemEvaluationRunRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> SystemEvaluationRunResponse:
    if db.scalar(select(func.count(SystemEvaluationRun.id)).where(SystemEvaluationRun.status == 'running')):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Ya existe una evaluacion formal en ejecucion')

    evaluator = SystemEvaluator()
    run = SystemEvaluationRun(app_version=APP_VERSION, status='running', suite_name='mvp_quality_v1')
    db.add(run)
    db.commit()
    db.refresh(run)
    started = datetime.now(timezone.utc)
    try:
        result = await evaluator.run(
            db,
            include_tests=payload.include_tests,
            include_vetia=payload.include_vetia,
            include_performance=payload.include_performance,
        )
        run.status = 'completed'
        run.tests_total = result['tests_total']
        run.tests_passed = result['tests_passed']
        run.tests_failed = result['tests_failed']
        coverage = result['coverage_percent']
        run.coverage_percent = Decimal(str(coverage)) if coverage is not None else None
        run.metrics = result['metrics']
        run.details = result['details']
        run.report_markdown = result['report_markdown']
        EVALUATIONS.labels(status='completed').inc()
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:3000]
        EVALUATIONS.labels(status='failed').inc()
    finally:
        run.finished_at = datetime.now(timezone.utc)
        EVALUATION_DURATION.observe((run.finished_at - started).total_seconds())
        db.commit()
        db.refresh(run)
    return _serialise(run)


@router.get('/evaluation/{run_id}/report', response_class=PlainTextResponse)
def download_report(
    run_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> PlainTextResponse:
    try:
        evaluation_id = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='Identificador de evaluacion no valido') from exc
    run = db.get(SystemEvaluationRun, evaluation_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Evaluacion no encontrada')
    if not run.report_markdown:
        raise HTTPException(status_code=409, detail='La evaluacion no dispone de informe')
    filename = f'gamucare-evaluation-{run.app_version}-{run.id}.md'
    return PlainTextResponse(
        run.report_markdown,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        media_type='text/markdown; charset=utf-8',
    )
