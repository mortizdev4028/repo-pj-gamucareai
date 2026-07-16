"""RAG enrichment for deterministic preventive alerts.

The rule engine remains the source of the alert. RAG and the LLM only add a
traceable explanation based on reference documents and fictitious histories.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import RiskAlert, RiskRule
from app.services.rag import RagService

logger = logging.getLogger(__name__)
settings = get_settings()


async def enrich_alerts(
    db: Session,
    *,
    only_missing: bool = False,
    alert_ids: list[str] | None = None,
    active_only: bool = True,
) -> dict[str, int]:
    """Add RAG-grounded explanations and source metadata to preventive alerts.

    The deterministic rule remains the origin of every alert. Filtering by IDs
    lets automatic workflows enrich only the patients that have changed.
    """
    stmt = select(RiskAlert).options(selectinload(RiskAlert.pet)).order_by(RiskAlert.generated_at)
    if only_missing:
        stmt = stmt.where(RiskAlert.llm_explanation.is_(None))
    if active_only:
        stmt = stmt.where(RiskAlert.status.in_(('new', 'reviewed')))
    if alert_ids:
        stmt = stmt.where(RiskAlert.id.in_([uuid.UUID(str(value)) for value in alert_ids]))
    alerts = db.scalars(stmt).all()
    rule_codes = {alert.rule_code for alert in alerts}
    rules = {
        rule.code: rule
        for rule in db.scalars(select(RiskRule).where(RiskRule.code.in_(rule_codes))).all()
    } if rule_codes else {}

    enriched = 0
    without_context = 0
    failed = 0
    rag = RagService()

    for position, alert in enumerate(alerts, start=1):
        try:
            rule = rules.get(alert.rule_code)
            explanation, chunks = await rag.explain_alert(
                pet_name=alert.pet.name,
                species=alert.pet.species,
                breed=alert.pet.breed,
                rule_title=alert.title,
                rule_description=rule.description if rule else alert.description,
                rule_source=rule.source if rule else None,
                rule_source_url=rule.source_url if rule else None,
                evidence=alert.evidence or {},
            )
            if not explanation:
                without_context += 1
                continue

            sources = [
                {
                    'title': chunk.title,
                    'source': chunk.source,
                    'category': chunk.category,
                    'score': round(chunk.score, 4),
                    'content_type': chunk.content_type,
                    'pet_id': chunk.pet_id,
                    'pet_name': chunk.pet_name,
                    'breed': chunk.breed,
                    'event_date': chunk.event_date,
                }
                for chunk in chunks
            ]
            alert.llm_explanation = explanation
            alert.model_name = settings.ollama_chat_model
            alert.evidence = {
                **(alert.evidence or {}),
                'rag_sources': sources,
                'rag_enriched_at': datetime.now(timezone.utc).isoformat(),
            }
            db.commit()
            enriched += 1
            print(f'Aviso enriquecido {position}/{len(alerts)}: {alert.pet.name} - {alert.title}')
        except Exception:
            failed += 1
            db.rollback()
            logger.exception(
                'alert_rag_enrichment_failed',
                extra={'alert_id': str(alert.id), 'pet_id': str(alert.pet_id)},
            )

    return {
        'processed': len(alerts),
        'enriched': enriched,
        'without_context': without_context,
        'failed': failed,
    }
