"""Pydantic models used by the HTTP API.

The schemas deliberately separate read models from write models. This prevents
clients from changing internal identifiers, roles or calculated fields by
accident.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    """Base schema that can be created directly from SQLAlchemy entities."""

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class UserResponse(OrmModel):
    id: uuid.UUID
    email: str
    role: Literal['clinic', 'staff', 'owner', 'technical']
    is_active: bool
    must_change_password: bool = False
    last_login_at: datetime | None = None


class SessionResponse(OrmModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    current: bool = False


class OwnerSummary(OrmModel):
    id: uuid.UUID
    external_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    is_active: bool


class OwnerListItem(OwnerSummary):
    address: str
    pet_count: int
    user_active: bool


class OwnerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=180)
    phone: str = Field(min_length=5, max_length=40)
    email: str = Field(min_length=3, max_length=255)
    address: str = Field(min_length=3, max_length=255)
    initial_password: str | None = Field(default=None, min_length=12, max_length=128)


class OwnerUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=180)
    phone: str | None = Field(default=None, min_length=5, max_length=40)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    address: str | None = Field(default=None, min_length=3, max_length=255)


class OwnerCreateResponse(OwnerListItem):
    temporary_password: str


class ClinicalEventResponse(OrmModel):
    id: uuid.UUID
    event_date: datetime
    event_type: str
    title: str
    description: str
    diagnosis: str | None
    treatment: str | None
    weight_kg: Decimal | None
    visible_to_owner: bool


class ClinicalEventCreate(BaseModel):
    event_date: datetime = Field(default_factory=datetime.now)
    event_type: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=2, max_length=220)
    description: str = Field(min_length=2, max_length=4000)
    diagnosis: str | None = Field(default=None, max_length=2000)
    treatment: str | None = Field(default=None, max_length=2000)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=250)
    visible_to_owner: bool = True


class AlertHistoryResponse(OrmModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    notes: str | None
    changed_by_id: uuid.UUID | None
    changed_at: datetime


class RiskRuleResponse(OrmModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: str
    species: str | None
    conditions: dict[str, Any]
    severity: str
    source: str
    source_url: str | None
    source_date: date | None
    reviewed_at: datetime | None
    auto_resolve: bool
    version: int
    is_active: bool


class AlertResponse(OrmModel):
    id: uuid.UUID
    pet_id: uuid.UUID
    rule_code: str
    title: str
    description: str
    severity: Literal['info', 'low', 'medium', 'high']
    status: Literal['new', 'reviewed', 'resolved', 'dismissed']
    evidence: dict[str, Any]
    llm_explanation: str | None
    model_name: str | None
    generated_at: datetime
    updated_at: datetime
    last_evaluated_at: datetime | None
    occurrence_count: int
    reviewed_at: datetime | None
    reviewed_by_id: uuid.UUID | None
    review_notes: str | None
    resolved_at: datetime | None
    dismissed_at: datetime | None
    resolution_reason: str | None
    history: list[AlertHistoryResponse] = Field(default_factory=list)
    rule: RiskRuleResponse | None = None
    pet_name: str | None = None
    breed: str | None = None
    species: str | None = None


class AlertActionRequest(BaseModel):
    status: Literal['new', 'reviewed', 'resolved', 'dismissed']
    notes: str | None = Field(default=None, max_length=1500)


class AlertRebuildResponse(BaseModel):
    pets_evaluated: int
    rules_evaluated: int
    created: int
    updated: int
    resolved: int
    reopened: int
    unchanged: int
    enriched: int = 0
    without_context: int = 0
    failed: int = 0


class AlertStatsResponse(BaseModel):
    total: int
    active: int
    new: int
    reviewed: int
    resolved: int
    dismissed: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_species: dict[str, int]
    recurrent: int


class SubscriptionServiceResponse(BaseModel):
    id: uuid.UUID
    name: str
    service_type: str
    service_mode: str
    occurrence_number: int
    scheduled_date: date | None
    completed_date: date | None
    status: str
    notes: str | None


class InstallmentResponse(BaseModel):
    id: uuid.UUID
    installment_number: int
    due_date: date
    amount: Decimal
    status: Literal['pending', 'overdue', 'paid', 'cancelled']
    paid_at: datetime | None
    notes: str | None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    health_plan_id: uuid.UUID
    plan_name: str
    lifecycle: str
    start_date: date
    end_date: date
    status: str
    renewal_status: str
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    completion_percentage: float
    payment_mode: Literal['single', 'installments']
    payment_status: Literal['paid', 'installments_pending']
    installments_total: int
    installments_paid: int
    total_amount: Decimal
    amount_paid: Decimal
    amount_remaining: Decimal
    installment_amount: Decimal
    installments: list[InstallmentResponse]
    services: list[SubscriptionServiceResponse]


class SubscriptionCreateRequest(BaseModel):
    pet_id: uuid.UUID
    health_plan_id: uuid.UUID
    start_date: date = Field(default_factory=date.today)
    payment_mode: Literal['single', 'installments'] = 'single'
    installments_total: int = Field(default=1, ge=1, le=12)
    installments_paid: int = Field(default=1, ge=0, le=12)


class SubscriptionChangeRequest(BaseModel):
    health_plan_id: uuid.UUID
    effective_date: date = Field(default_factory=date.today)
    payment_mode: Literal['single', 'installments'] = 'single'
    installments_total: int = Field(default=1, ge=1, le=12)
    installments_paid: int = Field(default=1, ge=0, le=12)
    reason: str = Field(default='Cambio de plan solicitado por la clinica.', min_length=3, max_length=500)


class SubscriptionCancelRequest(BaseModel):
    cancellation_date: date = Field(default_factory=date.today)
    reason: str = Field(min_length=3, max_length=500)


class SubscriptionRenewRequest(BaseModel):
    health_plan_id: uuid.UUID | None = None
    start_date: date | None = None
    payment_mode: Literal['single', 'installments'] = 'single'
    installments_total: int = Field(default=1, ge=1, le=12)
    installments_paid: int = Field(default=1, ge=0, le=12)


class RenewalRequestCreate(BaseModel):
    health_plan_id: uuid.UUID | None = None
    payment_mode: Literal['single', 'installments'] = 'single'
    installments_total: int = Field(default=1, ge=1, le=12)
    notes: str | None = Field(default=None, max_length=500)


class RenewalReviewRequest(BaseModel):
    status: Literal['approved', 'rejected']
    notes: str | None = Field(default=None, max_length=500)


class SubscriptionListItem(BaseModel):
    id: uuid.UUID
    pet_id: uuid.UUID
    pet_name: str
    owner_id: uuid.UUID
    owner_name: str
    health_plan_id: uuid.UUID
    plan_name: str
    species: str
    start_date: date
    end_date: date
    status: str
    renewal_status: str
    days_until_expiry: int
    payment_status: Literal['paid', 'installments_pending']
    installments_total: int
    installments_paid: int
    total_amount: Decimal
    amount_paid: Decimal
    amount_remaining: Decimal


class RenewalRequestResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    pet_id: uuid.UUID
    pet_name: str
    owner_name: str
    current_plan_name: str
    requested_plan_id: uuid.UUID | None
    requested_plan_name: str | None
    payment_mode: str | None
    installments_total: int | None
    status: str
    requested_at: datetime
    reviewed_at: datetime | None
    notes: str | None


class InstallmentUpdateRequest(BaseModel):
    status: Literal['paid', 'pending']
    notes: str | None = Field(default=None, max_length=500)


class PaymentUpdateRequest(BaseModel):
    payment_mode: Literal['single', 'installments']
    installments_total: int = Field(default=1, ge=1, le=12)
    installments_paid: int = Field(default=1, ge=0, le=12)


class PaymentResponse(BaseModel):
    subscription_id: uuid.UUID
    payment_mode: Literal['single', 'installments']
    payment_status: Literal['paid', 'installments_pending']
    installments_total: int
    installments_paid: int
    total_amount: Decimal
    amount_paid: Decimal
    amount_remaining: Decimal
    installment_amount: Decimal


class PetSummary(OrmModel):
    id: uuid.UUID
    external_id: str
    name: str
    species: Literal['dog', 'cat']
    breed: str
    birth_date: date
    sex: str
    weight_kg: Decimal
    neutered: bool
    microchip: str | None
    is_active: bool


class PetListItem(PetSummary):
    owner: OwnerSummary


class PetCreate(BaseModel):
    owner_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    species: Literal['dog', 'cat']
    breed: str = Field(min_length=1, max_length=120)
    birth_date: date
    sex: str = Field(min_length=1, max_length=20)
    weight_kg: Decimal = Field(gt=0, le=250)
    neutered: bool = False
    microchip: str | None = Field(default=None, max_length=80)
    allergies: str | None = Field(default=None, max_length=2000)
    chronic_conditions: str | None = Field(default=None, max_length=2000)
    external_id: str | None = Field(default=None, max_length=80)


class PetUpdate(BaseModel):
    owner_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    species: Literal['dog', 'cat'] | None = None
    breed: str | None = Field(default=None, min_length=1, max_length=120)
    birth_date: date | None = None
    sex: str | None = Field(default=None, min_length=1, max_length=20)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=250)
    neutered: bool | None = None
    microchip: str | None = Field(default=None, max_length=80)
    allergies: str | None = Field(default=None, max_length=2000)
    chronic_conditions: str | None = Field(default=None, max_length=2000)


class PetDetail(PetSummary):
    owner: OwnerSummary
    allergies: str | None
    chronic_conditions: str | None
    subscription: SubscriptionResponse | None
    upcoming_subscription: SubscriptionResponse | None = None
    clinical_events: list[ClinicalEventResponse]
    alerts: list[AlertResponse]


class PlanServiceResponse(OrmModel):
    id: uuid.UUID
    name: str
    description: str | None
    service_type: str
    service_mode: str
    included_quantity: int | None
    frequency_months: int | None
    notes: str | None


class HealthPlanResponse(OrmModel):
    id: uuid.UUID
    name: str
    species: str
    lifecycle: str
    description: str
    duration_months: int
    price_monthly: Decimal
    price_single: Decimal
    services: list[PlanServiceResponse]


class DashboardFinancialSummary(BaseModel):
    total_committed: Decimal = Decimal('0.00')
    amount_collected: Decimal = Decimal('0.00')
    amount_outstanding: Decimal = Decimal('0.00')
    overdue_amount: Decimal = Decimal('0.00')
    overdue_installments: int = 0
    next_due_date: date | None = None
    next_due_amount: Decimal | None = None


class DashboardTrendPoint(BaseModel):
    month: str
    label: str
    plans_started: int = 0
    renewals: int = 0
    services_completed: int = 0
    alerts_generated: int = 0
    amount_collected: Decimal = Decimal('0.00')


class DashboardRankedItem(BaseModel):
    key: str
    label: str
    count: int


class DashboardUpcomingItem(BaseModel):
    item_type: Literal['installment', 'service', 'plan', 'alert']
    title: str
    detail: str
    pet_id: uuid.UUID
    pet_name: str
    due_date: date
    status: str
    severity: str | None = None
    target_url: str


class DashboardOwnerPet(BaseModel):
    pet_id: uuid.UUID
    pet_name: str
    species: str
    breed: str
    plan_name: str | None = None
    plan_status: str | None = None
    plan_end_date: date | None = None
    completion_percentage: float = 0.0
    payment_status: str | None = None
    amount_remaining: Decimal = Decimal('0.00')
    next_installment_date: date | None = None
    next_installment_amount: Decimal | None = None
    services_pending: int = 0
    services_overdue: int = 0
    active_alerts: int = 0


class DashboardResponse(BaseModel):
    plans_active: int
    plans_expiring: int
    services_pending: int
    services_overdue: int
    pets_with_alerts: int
    pets_total: int
    completion_average: float
    role_scope: str
    generated_at: datetime
    filters: dict[str, Any] = Field(default_factory=dict)
    financial: DashboardFinancialSummary = Field(default_factory=DashboardFinancialSummary)
    plans_by_status: dict[str, int] = Field(default_factory=dict)
    services_by_status: dict[str, int] = Field(default_factory=dict)
    alerts_by_severity: dict[str, int] = Field(default_factory=dict)
    alerts_by_status: dict[str, int] = Field(default_factory=dict)
    species_distribution: dict[str, int] = Field(default_factory=dict)
    monthly_trends: list[DashboardTrendPoint] = Field(default_factory=list)
    top_alert_rules: list[DashboardRankedItem] = Field(default_factory=list)
    top_clinical_events: list[DashboardRankedItem] = Field(default_factory=list)
    upcoming_items: list[DashboardUpcomingItem] = Field(default_factory=list)
    owner_pets: list[DashboardOwnerPet] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    session_id: uuid.UUID | None = None
    pet_id: uuid.UUID | None = None
    scope: Literal['general', 'clinical', 'pet'] = 'general'


class SourceResponse(BaseModel):
    title: str
    source: str
    url: str | None
    category: str | None
    score: float
    dense_score: float | None = None
    citation_id: str | None = None
    content_type: str | None = None
    document_id: str | None = None
    country: str | None = None
    language: str | None = None
    trust_level: str | None = None
    tags: list[str] = Field(default_factory=list)
    pet_id: str | None = None
    pet_name: str | None = None
    breed: str | None = None
    species: str | None = None
    event_date: str | None = None
    event_type: str | None = None


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    answer: str
    sources: list[SourceResponse]
    model_name: str | None
    response_time_ms: int
    grounded: bool
    diagnostics: dict | None = None


class CompleteServiceRequest(BaseModel):
    completed_date: date = Field(default_factory=date.today)
    notes: str | None = Field(default=None, max_length=1000)


class StatusResponse(BaseModel):
    id: uuid.UUID
    is_active: bool

class RagDiagnosticsResponse(BaseModel):
    confidence: Literal['low', 'medium', 'high']
    confidence_reason: str
    retrieved_count: int
    candidate_count: int
    top_score: float
    applied_filters: dict
    urgent: bool
    urgency_matches: list[str]
    retrieval_decision: str = 'not_started'
    domain_in_scope: bool = True
    domain_reason: str = ''
    candidate_top_score: float = 0.0


class RagStatusResponse(BaseModel):
    collection: str
    collection_available: bool
    points_count: int
    documents_total: int
    documents_completed: int
    categories: dict[str, int]
    trust_levels: dict[str, int]
    latest_ingestion_at: datetime | None
    source_manifest_total: int = 0
    external_files_available: int = 0
    external_download_failures: int = 0


class RagEvaluationRunRequest(BaseModel):
    with_generation: bool = False


class RagEvaluationRunResponse(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    dataset_name: str
    cases_total: int
    metrics: dict | None
    details: list | None
    model_name: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class ImportBatchItemResponse(OrmModel):
    id: uuid.UUID
    row_number: int
    entity_type: str
    external_id: str | None
    action: str
    status: str
    message: str | None
    payload: dict[str, Any] | None
    created_at: datetime


class ImportBatchSummaryResponse(OrmModel):
    id: uuid.UUID
    source: str
    filename: str
    status: str
    requested_by_id: uuid.UUID | None
    file_format: str
    schema_version: str
    checksum: str | None
    dry_run: bool
    records_total: int
    records_processed: int
    records_created: int
    records_updated: int
    records_skipped: int
    records_failed: int
    summary: dict[str, Any] | None
    started_at: datetime
    finished_at: datetime | None


class ImportBatchDetailResponse(ImportBatchSummaryResponse):
    error_details: list[dict[str, Any]] | None
    items: list[ImportBatchItemResponse] = Field(default_factory=list)


class TemporaryCredential(BaseModel):
    external_id: str
    email: str
    temporary_password: str


class WakymaImportResponse(BaseModel):
    batch: ImportBatchDetailResponse
    temporary_credentials: list[TemporaryCredential] = Field(default_factory=list)
    affected_pets: int = 0


class WakymaIntegrationStatusResponse(BaseModel):
    connector: str
    mode: str
    supported_formats: list[str]
    supported_schema_versions: list[str]
    supported_entities: list[str]
    max_file_size_mb: int
    real_api_configured: bool


class AuditLogResponse(OrmModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    outcome: str
    request_id: str | None
    ip_address: str | None
    user_agent: str | None
    before_values: dict[str, Any] | None
    after_values: dict[str, Any] | None
    details: dict[str, Any] | None
    created_at: datetime


class AuditStatsResponse(BaseModel):
    total_events: int
    failed_events: int
    unique_actors: int
    events_last_24h: int
    by_action: dict[str, int]
    by_entity: dict[str, int]
    by_outcome: dict[str, int]


class SystemEvaluationRunRequest(BaseModel):
    """Options for the formal MVP evaluation."""

    include_tests: bool = True
    include_vetia: bool = True
    include_performance: bool = True


class SystemEvaluationRunResponse(BaseModel):
    id: uuid.UUID
    app_version: str
    status: str
    suite_name: str
    tests_total: int
    tests_passed: int
    tests_failed: int
    coverage_percent: Decimal | None
    metrics: dict[str, Any] | None
    details: dict[str, Any] | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class QualityStatusResponse(BaseModel):
    app_version: str
    acceptance_dataset: str
    alert_dataset: str
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None
    latest_run_at: datetime | None
    automated_criteria: int
    report_available: bool
