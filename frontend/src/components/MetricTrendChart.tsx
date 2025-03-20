import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDateTime, formatNumber } from '../lib/format'
import type { Overview } from '../types'

export const HISTORY_METRICS = [
  { key: 'recall_at_5', label: 'Recall@5' },
  { key: 'token_f1', label: 'Token F1' },
  { key: 'faithfulness', label: 'Faithfulness' },
  { key: 'citation_support', label: 'Citation support' },
] as const

export type HistoryMetricKey = (typeof HISTORY_METRICS)[number]['key']

const COLORS: Record<string, string> = {
  recall_at_5: '#3d5afe',
  token_f1: '#0f8a5f',
  faithfulness: '#b26a00',
  citation_support: '#8b5cf6',
  latency_p95_ms: '#0ea5e9',
  estimated_cost_usd: '#c02637',
}

interface ChartDatum {
  label: string
  run_id: number
  app_version: string
  created_at: string
  [key: string]: number | string | null
}

export default function MetricTrendChart({
  history,
  metrics,
  height = 300,
}: {
  history: Overview['history']
  metrics: readonly HistoryMetricKey[]
  height?: number
}) {
  const data: ChartDatum[] = history.map((point) => ({
    label: `${point.app_version} · run ${point.run_id}`,
    run_id: point.run_id,
    app_version: point.app_version,
    created_at: point.created_at,
    recall_at_5: point.recall_at_5,
    token_f1: point.token_f1,
    faithfulness: point.faithfulness,
    citation_support: point.citation_support,
  }))

  return (
    <div className="chart-frame" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} interval="preserveStartEnd" />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            width={44}
            tickFormatter={(value: number) => value.toFixed(2)}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--surface-border-strong)',
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(_label, payload) => {
              const point = payload?.[0]?.payload as ChartDatum | undefined
              return point ? `Run #${point.run_id} · ${point.app_version}` : ''
            }}
            formatter={(value: unknown, name: unknown) => [
              value === null || value === undefined ? '—' : formatNumber(Number(value), 3),
              String(name),
            ]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {metrics.map((metric) => (
            <Line
              key={metric}
              type="monotone"
              dataKey={metric}
              name={HISTORY_METRICS.find((m) => m.key === metric)?.label ?? metric}
              stroke={COLORS[metric] ?? '#3d5afe'}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function HistoryTooltipHint({ createdAt }: { createdAt: string }) {
  return <span className="text-faint text-small">{formatDateTime(createdAt)}</span>
}
