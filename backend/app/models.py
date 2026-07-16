"""Relational data model for the GamuCare MVP.

Strings are used for business states instead of database enums. This keeps the
first prototype easy to migrate while the allowed values remain validated in
service and schema layers.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    """Return an aware UTC timestamp suitable for database defaults."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[Owner | None] = relationship(back_populates='user', uselist=False)
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates='user')
    refresh_sessions: Mapped[list[RefreshSession]] = relationship(back_populates='user', cascade='all, delete-orphan')
    audit_entries: Mapped[list[AuditLog]] = relationship(back_populates='actor', foreign_keys='AuditLog.actor_user_id')


class RefreshSession(Base):
    __tablename__ = 'refresh_sessions'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(back_populates='refresh_sessions')


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(30), default='success', index=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    actor: Mapped[User | None] = relationship(back_populates='audit_entries', foreign_keys=[actor_user_id])


class Owner(Base):
    __tablename__ = 'owners'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), unique=True, nullable=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(180))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User | None] = relationship(back_populates='owner')
    pets: Mapped[list[Pet]] = relationship(back_populates='owner', cascade='all, delete-orphan')


class Pet(Base):
    __tablename__ = 'pets'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('owners.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    species: Mapped[str] = mapped_column(String(20), index=True)
    breed: Mapped[str] = mapped_column(String(120), index=True)
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(20))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    neutered: Mapped[bool] = mapped_column(Boolean, default=False)
    microchip: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[Owner] = relationship(back_populates='pets')
    subscriptions: Mapped[list[PetPlanSubscription]] = relationship(back_populates='pet', cascade='all, delete-orphan')
    clinical_events: Mapped[list[ClinicalEvent]] = relationship(back_populates='pet', cascade='all, delete-orphan')
    risk_alerts: Mapped[list[RiskAlert]] = relationship(back_populates='pet', cascade='all, delete-orphan')
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates='pet')


class HealthPlan(Base):
    __tablename__ = 'health_plans'
    __table_args__ = (UniqueConstraint('species', 'lifecycle', name='uq_plan_species_lifecycle'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    species: Mapped[str] = mapped_column(String(20), index=True)
    lifecycle: Mapped[str] = mapped_column(String(30), index=True)
    description: Mapped[str] = mapped_column(Text)
    duration_months: Mapped[int] = mapped_column(Integer, default=12)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    price_single: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    services: Mapped[list[PlanService]] = relationship(back_populates='health_plan', cascade='all, delete-orphan')
    subscriptions: Mapped[list[PetPlanSubscription]] = relationship(back_populates='health_plan')


class PlanService(Base):
    __tablename__ = 'plan_services'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    health_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('health_plans.id'), index=True)
    name: Mapped[str] = mapped_column(String(220))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_type: Mapped[str] = mapped_column(String(60), index=True)
    service_mode: Mapped[str] = mapped_column(String(30), default='limited')
    included_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frequency_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    health_plan: Mapped[HealthPlan] = relationship(back_populates='services')
    subscription_services: Mapped[list[SubscriptionService]] = relationship(back_populates='plan_service')


class PetPlanSubscription(Base):
    __tablename__ = 'pet_plan_subscriptions'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pets.id'), index=True)
    health_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('health_plans.id'), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), index=True)
    renewal_status: Mapped[str] = mapped_column(String(30), default='not_requested')
    payment_mode: Mapped[str] = mapped_column(String(20), default='single')
    installments_total: Mapped[int] = mapped_column(Integer, default=1)
    installments_paid: Mapped[int] = mapped_column(Integer, default=1)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal('0.00'))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    renewed_from_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('pet_plan_subscriptions.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pet: Mapped[Pet] = relationship(back_populates='subscriptions')
    health_plan: Mapped[HealthPlan] = relationship(back_populates='subscriptions')
    services: Mapped[list[SubscriptionService]] = relationship(back_populates='subscription', cascade='all, delete-orphan')
    installments: Mapped[list[PlanInstallment]] = relationship(back_populates='subscription', cascade='all, delete-orphan')
    renewal_requests: Mapped[list[RenewalRequest]] = relationship(back_populates='subscription')


class SubscriptionService(Base):
    __tablename__ = 'subscription_services'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pet_plan_subscriptions.id'), index=True)
    plan_service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('plan_services.id'), index=True)
    occurrence_number: Mapped[int] = mapped_column(Integer, default=1)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('clinical_events.id'), nullable=True)

    subscription: Mapped[PetPlanSubscription] = relationship(back_populates='services')
    plan_service: Mapped[PlanService] = relationship(back_populates='subscription_services')


class PlanInstallment(Base):
    __tablename__ = 'plan_installments'
    __table_args__ = (UniqueConstraint('subscription_id', 'installment_number', name='uq_subscription_installment'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pet_plan_subscriptions.id'), index=True)
    installment_number: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    status: Mapped[str] = mapped_column(String(30), default='pending', index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    subscription: Mapped[PetPlanSubscription] = relationship(back_populates='installments')


class ClinicalEvent(Base):
    __tablename__ = 'clinical_events'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pets.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    visible_to_owner: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pet: Mapped[Pet] = relationship(back_populates='clinical_events')


class RiskRule(Base):
    __tablename__ = 'risk_rules'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(220))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80), default='general', index=True)
    species: Mapped[str | None] = mapped_column(String(20), nullable=True)
    conditions: Mapped[dict] = mapped_column(JSON)
    severity: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_resolve: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskAlert(Base):
    __tablename__ = 'risk_alerts'
    __table_args__ = (UniqueConstraint('pet_id', 'rule_code', name='uq_pet_rule_alert'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pets.id'), index=True)
    rule_code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), default='new', index=True)
    evidence: Mapped[dict] = mapped_column(JSON)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    pet: Mapped[Pet] = relationship(back_populates='risk_alerts')
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    status_history: Mapped[list[AlertStatusHistory]] = relationship(
        back_populates='alert', cascade='all, delete-orphan', order_by='AlertStatusHistory.changed_at'
    )


class AlertStatusHistory(Base):
    __tablename__ = 'alert_status_history'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('risk_alerts.id'), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    alert: Mapped[RiskAlert] = relationship(back_populates='status_history')
    changed_by: Mapped[User | None] = relationship(foreign_keys=[changed_by_id])


class RagDocument(Base):
    __tablename__ = 'rag_documents'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    language: Mapped[str] = mapped_column(String(10), default='es')
    audience: Mapped[str] = mapped_column(String(30), default='owner')
    source_type: Mapped[str] = mapped_column(String(40), default='guideline')
    trust_level: Mapped[str] = mapped_column(String(30), default='official', index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    last_reviewed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    ingestion_status: Mapped[str] = mapped_column(String(30), default='pending')
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RagEvaluationRun(Base):
    __tablename__ = 'rag_evaluation_runs'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mode: Mapped[str] = mapped_column(String(30), default='retrieval')
    status: Mapped[str] = mapped_column(String(30), default='running', index=True)
    dataset_name: Mapped[str] = mapped_column(String(120), default='rag_cases_v1')
    cases_total: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SystemEvaluationRun(Base):
    __tablename__ = 'system_evaluation_runs'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    app_version: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), default='running', index=True)
    suite_name: Mapped[str] = mapped_column(String(120), default='mvp_quality_v1')
    tests_total: Mapped[int] = mapped_column(Integer, default=0)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    coverage_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatSession(Base):
    __tablename__ = 'chat_sessions'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    pet_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('pets.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates='chat_sessions')
    pet: Mapped[Pet | None] = relationship(back_populates='chat_sessions')
    messages: Mapped[list[ChatMessage]] = relationship(back_populates='session', cascade='all, delete-orphan')


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('chat_sessions.id'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[ChatSession] = relationship(back_populates='messages')


class ImportBatch(Base):
    __tablename__ = 'import_batches'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(80), default='wakyma_mock')
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), index=True)
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    file_format: Mapped[str] = mapped_column(String(20), default='json')
    schema_version: Mapped[str] = mapped_column(String(20), default='1.0')
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_details: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_by: Mapped[User | None] = relationship()
    items: Mapped[list[ImportBatchItem]] = relationship(
        back_populates='batch', cascade='all, delete-orphan', order_by='ImportBatchItem.row_number'
    )


class ImportBatchItem(Base):
    __tablename__ = 'import_batch_items'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('import_batches.id', ondelete='CASCADE'), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[ImportBatch] = relationship(back_populates='items')


class RenewalRequest(Base):
    __tablename__ = 'renewal_requests'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pet_plan_subscriptions.id'), index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(30), default='pending')
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('health_plans.id'), nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    installments_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subscription: Mapped[PetPlanSubscription] = relationship(back_populates='renewal_requests')
    requested_plan: Mapped[HealthPlan | None] = relationship()
