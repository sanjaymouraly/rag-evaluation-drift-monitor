/**
 * Typed representations of the RAG Quality Monitor backend contract.
 * Field names mirror the JSON exactly so responses can be used without mapping.
 */

export type MetricKind =
  | 'deterministic'
  | 'heuristic'
  | 'reference_based'
  | 'embedding_based'
  | 'judge_based'
  | 'operational'
  | (string & {})

export interface MetricAggregate {
  value: number | null
  n: number
  kind: MetricKind
  std?: number | null
}

export interface GroupMetrics {
  n: number
  metrics: Record<string, MetricAggregate>
}

export interface LatencySummary {
  p50?: number | null
  p95?: number | null
  p99?: number | null
  mean?: number | null
  min?: number | null
  max?: number | null
  n?: number
}

export interface RunMetricsPayload {
  n_questions?: number
  mode?: string
  metrics?: Record<string, MetricAggregate>
  metric_kinds?: Record<string, MetricKind>
  latency_ms?: LatencySummary
  by_category?: Record<string, GroupMetrics>
  by_cohort?: Record<string, GroupMetrics>
  n_errors?: number
  n_abstained?: number
  n_with_citations?: number
}

export interface Project {
  id: number
  name: string
  description: string
  is_demo: boolean
  created_at: string
}

export interface RAGApp {
  id: number
  project_id: number
  name: string
  version_label: string
  environment: string
  description: string
  config: Record<string, unknown>
  created_at: string
}

export interface DocumentRecord {
  id: number
  doc_id: string
  title: string
  source: string
  revision: string
  fingerprint: string
  chars: number
  preview: string
  metadata: Record<string, unknown>
}

export interface Dataset {
  id: number
  project_id: number
  name: string
  version: string
  description: string
  checksum: string
  n_items: number
  is_synthetic: boolean
  reviewed: boolean
  created_at: string
}

export interface DatasetItem {
  id: number
  dataset_id: number
  question: string
  reference_answer: string
  aliases: string[]
  relevant_doc_ids: string[]
  relevance_grades: Record<string, number>
  expected_citations: Array<Record<string, unknown>>
  category: string
  difficulty: string
  answerable: boolean
  language: string
  topic: string
  cohorts: string[]
  is_synthetic: boolean
  human_reviewed: boolean
  notes: string
}

export type RunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | (string & {})

export type RunMode = 'end_to_end' | 'retrieval_only' | 'generation_only' | (string & {})

export interface Run {
  id: number
  app_id: number
  dataset_id: number
  mode: RunMode
  status: RunStatus
  progress: number
  metrics: RunMetricsPayload
  config_snapshot: Record<string, unknown>
  error: string | null
  total_input_tokens: number
  total_output_tokens: number
  estimated_cost_usd: number
  cost_is_estimate: boolean
  judge_config: Record<string, unknown>
  app_name: string
  app_version: string
  dataset_name: string
  created_at: string
  finished_at: string | null
}

export interface RetrievedChunk {
  chunk_id: string
  doc_id: string
  score: number
  text: string
  char_start?: number
  char_end?: number
}

export interface Citation {
  doc_id: string
  chunk_id: string
  quote: string
}

export interface CitationRecord {
  index: number
  doc_id: string
  chunk_id: string
  quote: string
  outcome: 'supported' | 'unsupported' | 'irrelevant' | 'structural_invalid' | (string & {})
  reason: string
}

export interface EvidenceEntry {
  kind: MetricKind
  missing_reason?: string
  evidence?: Record<string, unknown>
  unsupported_claims?: string[]
  [key: string]: unknown
}

export interface RunResult {
  id: number
  item_id: number
  question: string
  category: string
  cohorts: string[]
  answerable: boolean
  answer: string
  abstained: boolean
  retrieved: RetrievedChunk[]
  citations: Citation[]
  metrics: Record<string, number | null>
  evidence: Record<string, EvidenceEntry>
  latency_ms: number
  retrieval_latency_ms: number
  generation_latency_ms: number
  input_tokens: number
  output_tokens: number
  error: string | null
}
