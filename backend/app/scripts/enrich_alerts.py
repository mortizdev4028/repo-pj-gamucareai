"""CLI entry point to rebuild and RAG-enrich preventive alerts."""
from __future__ import annotations

import asyncio

from app.database import SessionLocal
from app.services.alert_enrichment import enrich_alerts
from app.services.risk_engine import rebuild_alerts


async def run() -> None:
    """Create deterministic alerts and add their grounded explanations."""
    db = SessionLocal()
    try:
        summary = rebuild_alerts(db)
        result = await enrich_alerts(db, only_missing=True, alert_ids=summary.get('active_alert_ids', []))
        print({**summary, **result})
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(run())
