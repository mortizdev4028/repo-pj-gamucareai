"""Create or update the versioned preventive-rule catalogue."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import RiskAlert, RiskRule
from app.services.risk_catalog import RISK_RULE_CATALOG
from app.services.risk_engine import ACTIVE_ALERT_STATUSES, set_alert_status


def sync() -> dict[str, int]:
    """Synchronise catalogue metadata without deleting historical alerts."""
    db = SessionLocal()
    created = 0
    updated = 0
    deactivated = 0
    closed_alerts = 0
    try:
        for definition in RISK_RULE_CATALOG:
            rule = db.scalar(select(RiskRule).where(RiskRule.code == definition['code']))
            values = {
                'name': definition['name'],
                'description': definition.get('description'),
                'category': definition.get('category', 'general'),
                'species': definition.get('species'),
                'conditions': definition['conditions'],
                'severity': definition['severity'],
                'source': definition['source'],
                'source_url': definition.get('source_url'),
                'source_date': definition.get('source_date'),
                'reviewed_at': datetime.now(timezone.utc),
                'auto_resolve': definition.get('auto_resolve', True),
                'version': definition.get('version', 1),
                'is_active': True,
            }
            if rule is None:
                rule = RiskRule(code=definition['code'], **values)
                db.add(rule)
                created += 1
            else:
                for key, value in values.items():
                    setattr(rule, key, value)
                updated += 1
        catalogue_codes = {definition['code'] for definition in RISK_RULE_CATALOG}
        legacy_rules = list(db.scalars(select(RiskRule).where(RiskRule.code.not_in(catalogue_codes))).all())
        for legacy in legacy_rules:
            if legacy.is_active:
                legacy.is_active = False
                deactivated += 1
            alerts = list(
                db.scalars(
                    select(RiskAlert).where(
                        RiskAlert.rule_code == legacy.code,
                        RiskAlert.status.in_(ACTIVE_ALERT_STATUSES),
                    )
                ).all()
            )
            for alert in alerts:
                set_alert_status(
                    db,
                    alert,
                    'resolved',
                    notes='Regla desactivada al actualizar el catalogo preventivo a la version 0.6.0.',
                    changed_by_id=None,
                )
                closed_alerts += 1
        db.commit()
        return {
            'created': created,
            'updated': updated,
            'deactivated': deactivated,
            'closed_alerts': closed_alerts,
        }
    finally:
        db.close()


if __name__ == '__main__':
    print(sync())
