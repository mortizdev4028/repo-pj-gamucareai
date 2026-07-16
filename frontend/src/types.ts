export type Role = 'clinic' | 'staff' | 'owner' | 'technical'

export interface User {
  id: string
  email: string
  role: Role
  is_active: boolean
  must_change_password: boolean
  last_login_at?: string
}

export type MoneyValue = number | string

export interface DashboardFinancialSummary {
  total_committed: MoneyValue
  amount_collected: MoneyValue
  amount_outstanding: MoneyValue
  overdue_amount: MoneyValue
  overdue_installments: number
  next_due_date?: string
  next_due_amount?: MoneyValue
}

export interface DashboardTrendPoint {
  month: string
  label: string
  plans_started: number
  renewals: number
  services_completed: number
  alerts_generated: number
  amount_collected: MoneyValue
}

export interface DashboardRankedItem {
  key: string
  label: string
  count: number
}

export interface DashboardUpcomingItem {
  item_type: 'installment' | 'service' | 'plan' | 'alert'
  title: string
  detail: string
  pet_id: string
  pet_name: string
  due_date: string
  status: string
  severity?: string
  target_url: string
}

export interface DashboardOwnerPet {
  pet_id: string
  pet_name: string
  species: 'dog' | 'cat'
  breed: string
  plan_name?: string
  plan_status?: string
  plan_end_date?: string
  completion_percentage: number
  payment_status?: string
  amount_remaining: MoneyValue
  next_installment_date?: string
  next_installment_amount?: MoneyValue
  services_pending: number
  services_overdue: number
  active_alerts: number
}

export interface DashboardData {
  plans_active: number
  plans_expiring: number
  services_pending: number
  services_overdue: number
  pets_with_alerts: number
  pets_total: number
  completion_average: number
  role_scope: Role
  generated_at: string
  filters: { months: number; species?: string; plan_id?: string }
  financial: DashboardFinancialSummary
  plans_by_status: Record<string, number>
  services_by_status: Record<string, number>
  alerts_by_severity: Record<string, number>
  alerts_by_status: Record<string, number>
  species_distribution: Record<string, number>
  monthly_trends: DashboardTrendPoint[]
  top_alert_rules: DashboardRankedItem[]
  top_clinical_events: DashboardRankedItem[]
  upcoming_items: DashboardUpcomingItem[]
  owner_pets: DashboardOwnerPet[]
}

export interface OwnerSummary {
  id: string
  external_id: string
  first_name: string
  last_name: string
  email: string
  phone: string
  is_active: boolean
}

export interface OwnerListItem extends OwnerSummary {
  address: string
  pet_count: number
  user_active: boolean
}

export interface OwnerCreateResponse extends OwnerListItem {
  temporary_password: string
}

export interface PetSummary {
  id: string
  external_id: string
  name: string
  species: 'dog' | 'cat'
  breed: string
  birth_date: string
  sex: string
  weight_kg: number
  neutered: boolean
  microchip?: string
  is_active: boolean
}

export interface PetListItem extends PetSummary {
  owner: OwnerSummary
}

export interface ClinicalEvent {
  id: string
  event_date: string
  event_type: string
  title: string
  description: string
  diagnosis?: string
  treatment?: string
  weight_kg?: number
  visible_to_owner: boolean
}

export interface RiskAlert {
  id: string
  rule_code: string
  title: string
  description: string
  severity: 'info' | 'low' | 'medium' | 'high'
  status: string
  evidence: Record<string, unknown>
  llm_explanation?: string
  model_name?: string
  generated_at: string
}

export interface SubscriptionService {
  id: string
  name: string
  service_type: string
  service_mode: string
  occurrence_number: number
  scheduled_date?: string
  completed_date?: string
  status: string
  notes?: string
}

export interface PlanInstallment {
  id: string
  installment_number: number
  due_date: string
  amount: number
  status: 'pending' | 'overdue' | 'paid' | 'cancelled'
  paid_at?: string
  notes?: string
}

export interface Subscription {
  id: string
  health_plan_id: string
  plan_name: string
  lifecycle: string
  start_date: string
  end_date: string
  status: string
  renewal_status: string
  cancelled_at?: string
  cancellation_reason?: string
  completion_percentage: number
  payment_mode: 'single' | 'installments'
  payment_status: 'paid' | 'installments_pending'
  installments_total: number
  installments_paid: number
  total_amount: number
  amount_paid: number
  amount_remaining: MoneyValue
  installment_amount: number
  installments: PlanInstallment[]
  services: SubscriptionService[]
}

export interface PetDetail extends PetSummary {
  owner: OwnerSummary
  allergies?: string
  chronic_conditions?: string
  subscription?: Subscription | null
  upcoming_subscription?: Subscription | null
  clinical_events: ClinicalEvent[]
  alerts: RiskAlert[]
}

export interface PlanService {
  id: string
  name: string
  description?: string
  service_type: string
  service_mode: string
  included_quantity?: number
  frequency_months?: number
  notes?: string
}

export interface HealthPlan {
  id: string
  name: string
  species: 'dog' | 'cat'
  lifecycle: string
  description: string
  duration_months: number
  price_monthly: number
  price_single: number
  services: PlanService[]
}

export interface ChatSource {
  title: string
  source: string
  url?: string
  category?: string
  score: number
  dense_score?: number
  citation_id?: string
  content_type?: string
  document_id?: string
  country?: string
  language?: string
  trust_level?: string
  tags?: string[]
  pet_id?: string
  pet_name?: string
  breed?: string
  species?: string
  event_date?: string
  event_type?: string
}

export interface ChatResponse {
  session_id: string
  answer: string
  sources: ChatSource[]
  model_name?: string
  response_time_ms: number
  grounded: boolean
  diagnostics?: RagDiagnostics
}

export interface SubscriptionListItem {
  id: string
  pet_id: string
  pet_name: string
  owner_id: string
  owner_name: string
  health_plan_id: string
  plan_name: string
  species: 'dog' | 'cat'
  start_date: string
  end_date: string
  status: string
  renewal_status: string
  days_until_expiry: number
  payment_status: 'paid' | 'installments_pending'
  installments_total: number
  installments_paid: number
  total_amount: number
  amount_paid: number
  amount_remaining: MoneyValue
}

export interface RenewalRequestItem {
  id: string
  subscription_id: string
  pet_id: string
  pet_name: string
  owner_name: string
  current_plan_name: string
  requested_plan_id?: string
  requested_plan_name?: string
  payment_mode?: string
  installments_total?: number
  status: string
  requested_at: string
  reviewed_at?: string
  notes?: string
}

export interface AlertHistoryItem {
  id: string
  from_status?: string
  to_status: 'new' | 'reviewed' | 'resolved' | 'dismissed'
  notes?: string
  changed_by_id?: string
  changed_at: string
}

export interface RiskRuleDefinition {
  id: string
  code: string
  name: string
  description?: string
  category: string
  species?: 'dog' | 'cat'
  conditions: Record<string, unknown>
  severity: 'info' | 'low' | 'medium' | 'high'
  source: string
  source_url?: string
  source_date?: string
  reviewed_at?: string
  auto_resolve: boolean
  version: number
  is_active: boolean
}

export interface PreventiveAlert {
  id: string
  pet_id: string
  pet_name?: string
  breed?: string
  species?: 'dog' | 'cat'
  rule_code: string
  title: string
  description: string
  severity: 'info' | 'low' | 'medium' | 'high'
  status: 'new' | 'reviewed' | 'resolved' | 'dismissed'
  evidence: Record<string, unknown>
  llm_explanation?: string
  model_name?: string
  generated_at: string
  updated_at: string
  last_evaluated_at?: string
  occurrence_count: number
  reviewed_at?: string
  reviewed_by_id?: string
  review_notes?: string
  resolved_at?: string
  dismissed_at?: string
  resolution_reason?: string
  history: AlertHistoryItem[]
  rule?: RiskRuleDefinition
}

export interface AlertStats {
  total: number
  active: number
  new: number
  reviewed: number
  resolved: number
  dismissed: number
  by_severity: Record<string, number>
  by_category: Record<string, number>
  by_species: Record<string, number>
  recurrent: number
}

export interface AlertRebuildResult {
  pets_evaluated: number
  rules_evaluated: number
  created: number
  updated: number
  resolved: number
  reopened: number
  unchanged: number
  enriched: number
  without_context: number
  failed: number
}

export interface RagDiagnostics {
  confidence: 'low' | 'medium' | 'high'
  confidence_reason: string
  retrieved_count: number
  candidate_count: number
  top_score: number
  applied_filters: Record<string, unknown>
  urgent: boolean
  urgency_matches: string[]
  retrieval_decision?: 'accepted' | 'out_of_scope' | 'low_score' | 'no_evidence' | 'not_started'
  domain_in_scope?: boolean
  domain_reason?: string
  candidate_top_score?: number
}

export interface RagStatus {
  collection: string
  collection_available: boolean
  points_count: number
  documents_total: number
  documents_completed: number
  categories: Record<string, number>
  trust_levels: Record<string, number>
  latest_ingestion_at?: string
  source_manifest_total: number
  external_files_available: number
  external_download_failures: number
}

export interface RagEvaluationDetail {
  id: string
  scope: 'general' | 'clinical'
  question: string
  expected_answerable: boolean
  retrieved: number
  top_score: number
  candidate_top_score?: number
  retrieval_decision?: string
  domain_in_scope?: boolean
  domain_reason?: string
  first_relevant_rank?: number
  passed: boolean
  latency_ms: number
  sources: Array<{
    title: string
    source: string
    category?: string
    pet_name?: string
    score: number
  }>
}

export interface RagEvaluationRun {
  id: string
  mode: 'retrieval' | 'generation'
  status: 'running' | 'completed' | 'failed'
  dataset_name: string
  cases_total: number
  metrics?: Record<string, unknown>
  details?: RagEvaluationDetail[]
  model_name?: string
  error?: string
  started_at: string
  finished_at?: string
}

export interface ImportBatchItem {
  id: string
  row_number: number
  entity_type: string
  external_id?: string
  action: string
  status: string
  message?: string
  payload?: Record<string, unknown>
  created_at: string
}

export interface ImportBatchSummary {
  id: string
  source: string
  filename: string
  status: string
  requested_by_id?: string
  file_format: string
  schema_version: string
  checksum?: string
  dry_run: boolean
  records_total: number
  records_processed: number
  records_created: number
  records_updated: number
  records_skipped: number
  records_failed: number
  summary?: Record<string, unknown>
  started_at: string
  finished_at?: string
}

export interface ImportBatchDetail extends ImportBatchSummary {
  error_details?: Array<Record<string, unknown>>
  items: ImportBatchItem[]
}

export interface TemporaryCredential {
  external_id: string
  email: string
  temporary_password: string
}

export interface WakymaImportResult {
  batch: ImportBatchDetail
  temporary_credentials: TemporaryCredential[]
  affected_pets: number
}

export interface WakymaIntegrationStatus {
  connector: string
  mode: string
  supported_formats: string[]
  supported_schema_versions: string[]
  supported_entities: string[]
  max_file_size_mb: number
  real_api_configured: boolean
}


export interface SecuritySession {
  id: string
  created_at: string
  expires_at: string
  last_used_at?: string
  revoked_at?: string
  ip_address?: string
  user_agent?: string
  current: boolean
}

export interface AuditLogEntry {
  id: string
  actor_user_id?: string
  actor_email?: string
  action: string
  entity_type: string
  entity_id?: string
  outcome: string
  request_id?: string
  ip_address?: string
  user_agent?: string
  before_values?: Record<string, unknown>
  after_values?: Record<string, unknown>
  details?: Record<string, unknown>
  created_at: string
}

export interface AuditStats {
  total_events: number
  failed_events: number
  unique_actors: number
  events_last_24h: number
  by_action: Record<string, number>
  by_entity: Record<string, number>
  by_outcome: Record<string, number>
}

export interface QualityStatus {
  app_version: string
  acceptance_dataset: string
  alert_dataset: string
  latest_run_id?: string
  latest_run_status?: string
  latest_run_at?: string
  automated_criteria: number
  report_available: boolean
}

export interface SystemEvaluationRun {
  id: string
  app_version: string
  status: 'running' | 'completed' | 'failed'
  suite_name: string
  tests_total: number
  tests_passed: number
  tests_failed: number
  coverage_percent?: number
  metrics?: Record<string, number | string | boolean | null>
  details?: {
    acceptance?: EvaluationSection
    alerts?: EvaluationSection
    security?: EvaluationSection
    tests?: Record<string, any>
    vetia?: Record<string, any>
    performance?: Record<string, any>
  }
  error?: string
  started_at: string
  finished_at?: string
}

export interface EvaluationCase {
  id: string
  area?: string
  description: string
  passed: boolean
  evidence?: string | Record<string, unknown>
  expected?: boolean
  actual?: boolean
}

export interface EvaluationSection {
  dataset?: string
  total: number
  passed: number
  failed: number
  pass_rate?: number
  accuracy?: number
  precision?: number
  recall?: number
  cases: EvaluationCase[]
}


export interface DependencyStatus {
  status: 'up' | 'down'
  latency_ms: number
  error?: string
}

export interface ObservabilityStatus {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  checked_at: string
  dependencies: Record<string, DependencyStatus>
  monitoring: {
    grafana_url: string
    prometheus_url: string
    alertmanager_url: string
  }
}
