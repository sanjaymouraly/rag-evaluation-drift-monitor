import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from './ui'
import { formatMetricValue, metricKindLabel } from '../lib/format'
import { metricKindTone, runStatusBadge, verdictBadge } from '../lib/status'
import type { MetricAggregate, MetricKind, RunStatus } from '../types'

export function DemoBadge({ title = 'Demo project — sample data, not your production corpus.' }: { title?: string }) {
  return (
    <Badge tone="info" title={title}>
      DEMO
    </Badge>
  )
}

export function RunStatusBadge({ status }: { status: RunStatus | string }) {
  const spec = runStatusBadge(status)
  return <Badge tone={spec.tone}>{spec.label}</Badge>
}

export function VerdictBadge({ verdict }: { verdict: string }) {
  const spec = verdictBadge(verdict)
  return <Badge tone={spec.tone}>{spec.label}</Badge>
}

export function MetricKindBadge({ kind }: { kind: MetricKind | string | null | undefined }) {
  if (!kind) return <Badge tone="muted">Unknown</Badge>
  return (
    <Badge tone={metricKindTone(kind)} title={metricKindLabel(kind)}>
      {metricKindLabel(kind)}
    </Badge>
  )
}

/**
 * Render a metric value. `null` becomes an em dash, `n === 0` additionally
 * shows a "no evidence" hint so a 0 is never mistaken for a measured result.
 */
export function MetricValue({
  aggregate,
  digits = 3,
  showKind = false,
}: {
  aggregate: MetricAggregate | null | undefined
  digits?: number
  showKind?: boolean
}) {
  if (!aggregate) return <span className="text-faint">—</span>
  const formatted = formatMetricValue(aggregate, digits)
  return (
    <span>
      {formatted.text}
      {formatted.hint && <span className="text-faint text-small"> ({formatted.hint})</span>}
      {showKind && (
        <>
          {' '}
          <MetricKindBadge kind={aggregate.kind} />
        </>
      )}
    </span>
  )
}

export function RunLink({ id, children }: { id: number; children?: ReactNode }) {
  return <Link to={`/runs/${id}`}>{children ?? `Run #${id}`}</Link>
}

export function ErrorInline({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="text-small" style={{ color: 'var(--danger)' }} role="alert">
      {message}
    </p>
  )
}
