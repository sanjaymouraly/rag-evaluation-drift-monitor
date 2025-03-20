/**
 * Badge tones and status mapping shared across the dashboard.
 */
import type { GateVerdict, RunStatus } from '../types'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'muted'

export interface BadgeSpec {
  label: string
  tone: Tone
}

const RUN_STATUS_MAP: Record<string, BadgeSpec> = {
  queued: { label: 'Queued', tone: 'info' },
  pending: { label: 'Queued', tone: 'info' },
  running: { label: 'Running', tone: 'info' },
  completed: { label: 'Completed', tone: 'success' },
  succeeded: { label: 'Completed', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
  error: { label: 'Failed', tone: 'danger' },
  cancelled: { label: 'Cancelled', tone: 'warning' },
  canceled: { label: 'Cancelled', tone: 'warning' },
  aborted: { label: 'Cancelled', tone: 'warning' },
}

export function runStatusBadge(status: RunStatus | string | null | undefined): BadgeSpec {
  const key = (status ?? '').toLowerCase()
  return RUN_STATUS_MAP[key] ?? { label: status ? status : 'Unknown', tone: 'muted' }
}

const VERDICT_MAP: Record<string, BadgeSpec> = {
  PASS: { label: 'PASS', tone: 'success' },
  FAIL: { label: 'FAIL', tone: 'danger' },
  INCONCLUSIVE: { label: 'INCONCLUSIVE', tone: 'warning' },
}

export function verdictBadge(verdict: GateVerdict | string | null | undefined): BadgeSpec {
  const key = (verdict ?? '').toUpperCase()
  return VERDICT_MAP[key] ?? { label: verdict ? String(verdict) : 'Unknown', tone: 'muted' }
}

export function checkStatusBadge(status: string | null | undefined): BadgeSpec {
  const key = (status ?? '').toUpperCase()
  if (key === 'PASS' || key === 'PASSED' || key === 'OK') return { label: 'Pass', tone: 'success' }
  if (key === 'FAIL' || key === 'FAILED' || key === 'BREACH') return { label: 'Fail', tone: 'danger' }
  if (key === 'INCONCLUSIVE' || key === 'WARN' || key === 'WARNING') return { label: 'Inconclusive', tone: 'warning' }
  if (!key) return { label: '—', tone: 'muted' }
  return { label: key, tone: 'muted' }
}

export function severityBadge(severity: string | null | undefined): BadgeSpec {
  const key = (severity ?? '').toLowerCase()
  if (key === 'hard' || key === 'critical' || key === 'error') return { label: severity ?? '—', tone: 'danger' }
  if (key === 'warn' || key === 'warning' || key === 'medium') return { label: severity ?? '—', tone: 'warning' }
  if (key === 'info' || key === 'low') return { label: severity ?? '—', tone: 'info' }
  return { label: severity || '—', tone: 'muted' }
}

export function citationOutcomeBadge(outcome: string | null | undefined): BadgeSpec {
  const key = (outcome ?? '').toLowerCase()
  if (key === 'supported') return { label: 'Supported', tone: 'success' }
  if (key === 'unsupported') return { label: 'Unsupported', tone: 'danger' }
  if (key === 'irrelevant') return { label: 'Irrelevant', tone: 'warning' }
  if (key === 'structural_invalid') return { label: 'Structurally invalid', tone: 'danger' }
  return { label: outcome || 'Unknown', tone: 'muted' }
}

export function metricKindTone(kind: string | null | undefined): Tone {
  const key = (kind ?? '').toLowerCase()
  if (key === 'deterministic') return 'success'
  if (key === 'heuristic') return 'warning'
  if (key === 'reference_based') return 'info'
  if (key === 'judge_based' || key === 'llm_judge') return 'warning'
  if (key === 'embedding_based') return 'info'
  if (key === 'operational') return 'muted'
  return 'muted'
}

export type DeltaTone = 'up' | 'down' | 'flat' | 'unknown'

/**
 * Direction of a delta, used for colouring. `higherIsBetter` lets callers
 * invert the meaning for cost/latency style metrics.
 */
export function deltaTone(
  delta: number | null | undefined,
  higherIsBetter = true,
  epsilon = 1e-9,
): DeltaTone {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return 'unknown'
  if (Math.abs(delta) <= epsilon) return 'flat'
  const positive = delta > 0
  if (!higherIsBetter) return positive ? 'down' : 'up'
  return positive ? 'up' : 'down'
}

export function deltaToneClass(tone: DeltaTone): string {
  switch (tone) {
    case 'up':
      return 'delta-up'
    case 'down':
      return 'delta-down'
    case 'flat':
      return 'delta-flat'
    default:
      return 'delta-unknown'
  }
}

/** Metrics where a bigger number is worse. */
export const LOWER_IS_BETTER = new Set([
  'estimated_cost_usd',
  'latency_ms',
  'latency_p95_ms',
  'retrieval_latency_ms',
  'generation_latency_ms',
  'hallucination_rate',
  'citation_unsupported_rate',
  'contradiction_rate',
  'empty_answer',
  'empty_retrieval',
  'duplicate_chunk_rate',
  'missing_source_rate',
  'over_abstention',
  'input_tokens',
  'output_tokens',
  'request_error',
])

export function isHigherBetter(metric: string): boolean {
  return !LOWER_IS_BETTER.has(metric)
}

/**
 * Interpret a PSI (population stability index) value.
 * Thresholds follow the conventional 0.1 / 0.25 banding.
 */
export function psiInterpretation(psi: number | null | undefined): { label: string; tone: Tone } {
  if (psi === null || psi === undefined || Number.isNaN(psi)) return { label: 'Not computed', tone: 'muted' }
  if (psi < 0.1) return { label: 'No significant shift', tone: 'success' }
  if (psi < 0.25) return { label: 'Moderate shift — worth watching', tone: 'warning' }
  return { label: 'Large shift — likely drift', tone: 'danger' }
}

export function psiBand(psi: number | null | undefined): 'none' | 'moderate' | 'large' | 'unknown' {
  if (psi === null || psi === undefined || Number.isNaN(psi)) return 'unknown'
  if (psi < 0.1) return 'none'
  if (psi < 0.25) return 'moderate'
  return 'large'
}
