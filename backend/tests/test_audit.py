"""Privacy and persistence tests for the v0.10 audit trail."""
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import AuditLog, Owner, User
from app.services.audit import record_audit, sanitize_mapping, snapshot_model


def _db() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return Session(engine)


def test_sensitive_values_are_redacted() -> None:
    safe = sanitize_mapping({
        'password': 'secret',
        'token_hash': 'abc',
        'email': 'ana@example.test',
        'phone': '600000000',
        'diagnosis': 'texto clinico',
        'amount': Decimal('12.50'),
        'created': date(2026, 7, 16),
    })
    assert safe['password'] == '[REDACTED]'
    assert safe['token_hash'] == '[REDACTED]'
    assert safe['email'] == 'a***@example.test'
    assert safe['phone'] == '[REDACTED]'
    assert safe['diagnosis'] == '[CLINICAL DATA REDACTED]'
    assert safe['amount'] == '12.50'
    assert safe['created'] == '2026-07-16'


def test_audit_entry_is_stored_with_safe_snapshots() -> None:
    with _db() as db:
        actor = User(email='clinic@example.test', password_hash='hash', role='clinic')
        owner = Owner(
            external_id='OWNER-AUDIT', first_name='Ana', last_name='Demo', phone='600000000',
            email='ana@example.test', address='Direccion', is_active=True,
        )
        db.add_all([actor, owner])
        db.flush()
        record_audit(
            db,
            actor=actor,
            action='owner.created',
            entity_type='owner',
            entity_id=owner.id,
            after=snapshot_model(owner),
        )
        db.commit()
        entry = db.scalar(select(AuditLog))
        assert entry.action == 'owner.created'
        assert entry.actor_email == 'clinic@example.test'
        assert entry.after_values['phone'] == '[REDACTED]'
        assert entry.after_values['email'] == 'a***@example.test'
