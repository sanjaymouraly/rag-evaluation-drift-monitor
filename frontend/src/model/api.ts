
import type { MetricAggregate, MetricKind, Run } from './domain'

export interface CompareMetric {
  metric: string
  a: number | null
  b: number | null
  delta_b_minus_a: number | null
  kind: MetricKind
  n_a: number
  n_b: number
}

export interface PerQuestionComparison {
  item_id: number
  question: string
  category: string
  cohorts: string[]
  f1_a: number | null
  f1_b: number | null
  f1_delta: number | null
  recall_a: number | null
  recall_b: number | null
  faithfulness_a: number | null
  faithfulness_b: number | null
  citation_support_a: number | null
  citation_support_b: number | null
  answer_a: string
  answer_b: string
  top5_a: string[]
  top5_b: string[]
  top5_changed: boolean
}

export interface CompareResponse {
  run_a: Run
  run_b: Run
  metrics: CompareMetric[]
  per_question: PerQuestionComparison[]
  comparable: boolean
  warning: string | null
}

export interface CompareMultiResponse {
  runs: Run[]
  metrics_by_run: Record<string, Record<string, number>>
  comparable: boolean
  warning: string | null
}

export interface MetricHistoryPoint {
  run_id: number
  value: number | null
  app_version: string
  created_at: string
}

export interface MetricHistory {
  metric: string
  app_id: number
  series: MetricHistoryPoint[]
}

export type GateRuleType = 'min' | 'max' | 'max_drop' | 'max_increase' | 'min_delta' | (string & {})

export interface GateRuleScope {
  category?: string
  cohort?: string
}

export interface GateRule {
  metric: string
  type: GateRuleType
  threshold: number
  severity: 'hard' | 'warn' | (string & {})
  tolerance?: number | null
  label?: string
  scope?: GateRuleScope
}

export interface GatePolicy {
  id: number
  project_id: number
  name: string
  version: number
  description: string
  baseline_run_id: number | null
  rules: GateRule[]
  min_samples: number
  created_at: string
}

export interface GatePolicyDefaults {
  rules: GateRule[]
  rule_types: string[]
  note: string
}

export type GateVerdict = 'PASS' | 'FAIL' | 'INCONCLUSIVE' | (string & {})

export interface GateCheck {
  metric: string
  type: GateRuleType
  severity: string
  threshold: number
  tolerance: number | null
  scope: GateRuleScope
  label: string
  observed: number | null
  baseline_value: number | null
  observed_change: number | null
  n: number
  ci: [number, number] | null
  p_value: number | null
  effect_size: number | null
  effect_magnitude: string | null
  status: string
  evidence: string
  baseline_n?: number
}

export interface GateEvaluation {
  id: number
  policy_id: number
  candidate_run_id: number
  baseline_run_id: number | null
  verdict: GateVerdict
  checks: GateCheck[]
  summary: string
  candidate_app?: string
  baseline_app?: string
  created_at: string
}

export interface DriftKs {
  statistic: number
  p_value: number
  n_baseline: number
  n_candidate: number
}

export interface DriftSignal {
  psi: number
  psi_interpretation: string
  ks?: DriftKs
  mean_baseline?: number
  mean_candidate?: number
  n_baseline?: number
  n_candidate?: number
  [key: string]: unknown
}

export interface DriftReport {
  id: number
  baseline_run: number
  candidate_run: number
  signals: Record<string, DriftSignal>
  hypotheses: string[]
  disclaimer: string
  created_at: string
}

export interface ProviderPreset {
  key: string
  label: string
  protocol: string
  base_url: string
  default_model: string
  requires_key: boolean
  notes: string
}

export interface ProviderPresets {
  presets: ProviderPreset[]
  roles: Record<string, string>
  note: string
}

export interface Provider {
  id: number
  name: string
  kind: string
  role: string
  base_url: string
  api_key_masked: string
  has_key: boolean
  model: string
  timeout_s: number
  retries: number
  price_per_1k_input: number
  price_per_1k_output: number
  price_source: string
  is_default: boolean
  enabled: boolean
  max_concurrency: number
  created_at: string
}

export interface ProviderModel {
  id: string
  price_per_1k_input: number
  price_per_1k_output: number
  price_source: string
}

export interface ProviderTestResult {
  ok: boolean
  detail: string
  models: string[]
}

export interface MetricCatalogueEntry {
  name: string
  kind: MetricKind
  kind_description: string
  requires: string[]
  requirements: string[]
  description: string
}

export interface MetricCatalogue {
  metrics: MetricCatalogueEntry[]
  judge_dimensions: string[]
  retrievers: Record<string, string>
}

export interface Overview {
  counts: Record<string, number>
  recent_runs: Run[]
  latest_metrics: Record<string, MetricAggregate>
  history: Array<{
    run_id: number
    app_id: number
    app_version: string
    app_name: string
    recall_at_5: number | null
    token_f1: number | null
    faithfulness: number | null
    citation_support: number | null
    latency_p95_ms: number | null
    estimated_cost_usd: number | null
    created_at: string
  }>
  gate_verdicts: Array<{
    id: number
    verdict: GateVerdict
    summary: string
    candidate_run_id: number
    baseline_run_id: number | null
    created_at: string
  }>
  demo_project_ids: number[]
}

export interface SystemInfo {
  version: string
  environment: string
  database: string
  api_key_auth_enabled: boolean
  cors_origins: string[]
  trusted_hosts: string[]
  max_upload_bytes: number
  rate_limit_per_minute: number
  max_workers: number
  default_budget_usd: number
  hard_cost_limit_usd: number
  max_run_cost_usd: number
  alert_webhook_configured: boolean
  scheduler_enabled: boolean
  demo_mode: boolean
  counts: Record<string, number>
  execution_log: Array<{
    run_id: number
    status: string
    error: string
    created_at: string
    finished_at: string | null
  }>
}

export interface Alert {
  id: number
  project_id: number
  kind: string
  severity: string
  message: string
  status: string
  fingerprint: string
  created_at: string
}

export interface ScheduledJob {
  id: number
  project_id: number
  name: string
  app_id: number
  dataset_id: number
  policy_id: number | null
  interval_minutes: number
  mode: string
  enabled: boolean
  created_at?: string
}

export interface DatasetValidationIssue {
  item_id: number | null
  kind: string
  detail: string
  severity: string
}

export interface DatasetValidation {
  dataset_id: number
  n_items: number
  corpus_docs: number
  ok: boolean
  n_issues: number
  issues: DatasetValidationIssue[]
  summary: string
}

export interface ImportResult {
  imported: number
  skipped_duplicates: number
  received: number
}

export interface SyntheticResult {
  created: number
  warning: string
}

export interface JudgeRubric {
  dimension: string
  label: string
  instruction: string
  scale: string
}

export interface JudgeRubrics {
  rubrics: JudgeRubric[]
  limitation: string
}

export interface HealthInfo {
  status: string
  service: string
  version: string
}
