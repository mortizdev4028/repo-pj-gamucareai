"""RAG observability and repeatable evaluation endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_roles
from app.models import RagDocument, RagEvaluationRun, User
from app.schemas import RagEvaluationRunRequest, RagEvaluationRunResponse, RagStatusResponse
from app.services.rag_evaluation import RagEvaluator

router = APIRouter(prefix='/rag', tags=['rag-quality'])
settings = get_settings()




def _external_source_status() -> tuple[int, int, int]:
    """Return manifest, downloaded-file and last-download failure counts."""
    enabled_sources: list[dict] = []
    failures = 0
    try:
        manifest = json.loads(Path(settings.rag_source_manifest).read_text(encoding='utf-8'))
        enabled_sources = [item for item in manifest.get('sources', []) if item.get('enabled', True)]
    except Exception:
        enabled_sources = []

    external_dir = Path(settings.rag_external_documents_path)
    external_files = sum(
        1 for item in enabled_sources
        if (external_dir / str(item.get('filename', ''))).is_file()
    )
    report = external_dir / 'download-report.json'
    if report.exists():
        try:
            failures = int(json.loads(report.read_text(encoding='utf-8')).get('failed', 0))
        except Exception:
            failures = 0
    return len(enabled_sources), external_files, failures

def _serialise(run: RagEvaluationRun) -> RagEvaluationRunResponse:
    return RagEvaluationRunResponse(
        id=run.id,
        mode=run.mode,
        status=run.status,
        dataset_name=run.dataset_name,
        cases_total=run.cases_total,
        metrics=run.metrics,
        details=run.details,
        model_name=run.model_name,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get('/status', response_model=RagStatusResponse)
def status_view(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> RagStatusResponse:
    """Return collection, document and metadata health indicators."""
    qdrant = QdrantClient(url=settings.qdrant_url, timeout=10)
    available = False
    points = 0
    try:
        info = qdrant.get_collection(settings.qdrant_collection)
        available = True
        points = int(info.points_count or 0)
    except Exception:
        pass

    documents = db.scalars(select(RagDocument)).all()
    categories: dict[str, int] = {}
    trust_levels: dict[str, int] = {}
    latest = None
    completed = 0
    for document in documents:
        categories[document.category] = categories.get(document.category, 0) + 1
        trust_levels[document.trust_level] = trust_levels.get(document.trust_level, 0) + 1
        completed += int(document.ingestion_status == 'completed')
        if document.ingested_at and (latest is None or document.ingested_at > latest):
            latest = document.ingested_at
    manifest_total, external_files, external_failures = _external_source_status()
    return RagStatusResponse(
        collection=settings.qdrant_collection,
        collection_available=available,
        points_count=points,
        documents_total=len(documents),
        documents_completed=completed,
        categories=categories,
        trust_levels=trust_levels,
        latest_ingestion_at=latest,
        source_manifest_total=manifest_total,
        external_files_available=external_files,
        external_download_failures=external_failures,
    )


@router.get('/evaluation/latest', response_model=RagEvaluationRunResponse | None)
def latest_evaluation(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
):
    """Return the most recent completed or failed evaluation."""
    run = db.scalar(select(RagEvaluationRun).order_by(RagEvaluationRun.started_at.desc()).limit(1))
    return _serialise(run) if run else None


@router.post('/evaluation/run', response_model=RagEvaluationRunResponse)
async def run_evaluation(
    payload: RagEvaluationRunRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles('technical')),
) -> RagEvaluationRunResponse:
    """Execute the versioned dataset and persist metrics for later comparison."""
    mode = 'generation' if payload.with_generation else 'retrieval'
    running = db.scalar(
        select(func.count(RagEvaluationRun.id)).where(RagEvaluationRun.status == 'running')
    )
    if running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Ya existe una evaluacion RAG en ejecucion',
        )

    evaluator = RagEvaluator()
    run = RagEvaluationRun(
        mode=mode,
        status='running',
        dataset_name=evaluator.dataset_path.stem,
        cases_total=len(evaluator.load_cases()),
        model_name=settings.ollama_chat_model if payload.with_generation else settings.ollama_embed_model,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        report = await evaluator.run(with_generation=payload.with_generation)
        run.status = 'completed'
        run.metrics = report['metrics']
        run.details = report['details']
        run.finished_at = datetime.now(timezone.utc)
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:2000]
        run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _serialise(run)
