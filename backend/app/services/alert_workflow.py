"""Background workflows that keep patient vectors and alerts in sync."""
from __future__ import annotations

import logging
import uuid

from app.database import SessionLocal
from app.rag.ingest import upsert_pet
from app.services.alert_enrichment import enrich_alerts
from app.services.risk_engine import rebuild_alerts

logger = logging.getLogger(__name__)


async def recalculate_and_enrich_pet(pet_id: uuid.UUID, *, reindex: bool = True) -> None:
    """Reindex one patient, recalculate rules and enrich changed active alerts.

    This function is designed for FastAPI BackgroundTasks. It opens its own
    database session so it remains valid after the request session is closed.
    Failures are logged and never roll back the clinical change that triggered
    the recalculation.
    """
    db = SessionLocal()
    try:
        if reindex:
            await upsert_pet(pet_id)
        summary = rebuild_alerts(db, [pet_id])
        alert_ids = summary.get('active_alert_ids', [])
        if alert_ids:
            await enrich_alerts(db, only_missing=True, alert_ids=alert_ids)
        logger.info('pet_alert_workflow_completed', extra={'pet_id': str(pet_id), **summary})
    except Exception:
        logger.exception('pet_alert_workflow_failed', extra={'pet_id': str(pet_id)})
    finally:
        db.close()
