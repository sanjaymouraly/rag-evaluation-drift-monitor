/**
 * Presentation helpers for metric values.
 *
 * Rule of the house: never invent a number. A metric with `value === null`
 * renders as an em dash, and a metric computed over zero samples is flagged
 * as "no evidence" instead of being shown as 0.
 */
import type { MetricAggregate, MetricKind } from '../types'

export const NO_VALUE = '—'
export const NO_EVIDENCE = 'no evidence'

export function isNoEvidence(aggregate: { n?: number; value: number | null } | null | undefined): boolean {
  if (!aggregate) return false
  if (aggregate.n === undefined) return false
  return aggregate.n === 0
}

/**
 * Format a metric value for display.
 * - `null`/`undefined` -> em dash
 * - `n === 0` -> em dash plus a "no evidence" hint
 */
export function formatMetricValue(
  aggregate: MetricAggregate | null | undefined,
  digits = 3,
): { text: string; hint?: string; hasEvidence: boolean } {
  if (!aggregate) return { text: NO_VALUE, hint: 'not computed', hasEvidence: false }
  if (isNoEvidence(aggregate)) return { text: NO_VALUE, hint: NO_EVIDENCE, hasEvidence: false }
  if (aggregate.value === null || aggregate.value === undefined) {
    return { text: NO_VALUE, hint: 'not computed', hasEvidence: false }
  }
  return { text: formatNumber(aggregate.value, digits), hasEvidence: true }
}

export function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_VALUE
  const abs = Math.abs(value)
  if (abs !== 0 && (abs < 0.001 || abs >= 1_000_000)) return value.toExponential(2)
  return value.toFixed(digits)
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_VALUE
  return `${(value * 100).toFixed(digits)}%`
}

export function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_VALUE
  if (value === 0) return '$0.00'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return NO_VALUE
  if (ms < 1000) return `${ms.toFixed(ms < 10 ? 2 : 0)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return NO_VALUE
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return NO_VALUE
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const deltaSeconds = Math.round((Date.now() - date.getTime()) / 1000)
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['second', 60],
    ['minute', 60],
    ['hour', 24],
    ['day', 7],
    ['week', 4.35],
    ['month', 12],
    ['year', Number.POSITIVE_INFINITY],
  ]
  let amount = deltaSeconds
  for (const [unit, size] of units) {
    if (Math.abs(amount) < size) {
      return new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(-Math.round(amount), unit)
    }
    amount = amount / size
  }
  return date.toLocaleDateString()
}

/** Human label for a metric kind. */
const METRIC_KIND_LABELS: Record<string, string> = {
  deterministic: 'Deterministic',
  heuristic: 'Heuristic',
  reference_based: 'Reference-based',
  embedding_based: 'Embedding-based',
  judge_based: 'LLM-judge',
  operational: 'Operational',
}

export function metricKindLabel(kind: MetricKind | null | undefined): string {
  if (!kind) return 'unknown'
  return METRIC_KIND_LABELS[kind] ?? kind
}

/** Convert a snake_case metric name into a readable label. */
export function metricLabel(name: string): string {
  const special: Record<string, string> = {
    recall_at_5: 'Recall@5',
    recall_at_3: 'Recall@3',
    precision_at_5: 'Precision@5',
    hit_at_5: 'Hit@5',
    ndcg_at_5: 'NDCG@5',
    token_f1: 'Token F1',
    latency_ms: 'Latency',
    latency_p95_ms: 'Latency p95',
    estimated_cost_usd: 'Est. cost',
  }
  if (special[name]) return special[name]
  return name
    .split('_')
    .map((part) => (part.length <= 2 ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1)))
    .join(' ')
}
