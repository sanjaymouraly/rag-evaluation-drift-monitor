import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { MetricKindBadge } from '../components/common'
import { formatDateTime, formatNumber, metricLabel } from '../lib/format'

export default function MetricsPage() {
  const catalogue = useAsync(() => api.metrics.catalogue(), [])
  const runs = useAsync(() => api.runs.list(), [])
  const [search, setSearch] = useState('')
  const [metricName, setMetricName] = useState('recall_at_5')
  const [runId, setRunId] = useState('')

  const effectiveRunId = runId || String(runs.data?.[0]?.id ?? '')

  const history = useAsync(
    () => (effectiveRunId ? api.runs.history(Number(effectiveRunId), metricName, 50) : Promise.resolve(null)),
    [effectiveRunId, metricName],
  )

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    const metrics = catalogue.data?.metrics ?? []
    if (!needle) return metrics
    return metrics.filter(
      (metric) =>
        metric.name.toLowerCase().includes(needle) ||
        metric.description.toLowerCase().includes(needle) ||
        metric.kind.toLowerCase().includes(needle) ||
        metric.requires.some((requirement) => requirement.toLowerCase().includes(needle)),
    )
  }, [catalogue.data, search])

  const chartData = (history.data?.series ?? []).map((point) => ({
    label: `${point.app_version} · run ${point.run_id}`,
    value: point.value,
    run_id: point.run_id,
    app_version: point.app_version,
    created_at: point.created_at,
  }))

  return (
    <>
      <PageHeader
        title="Metric catalogue"
        description="Every metric the platform can compute, how it is measured and what evidence it needs."
      />

      <Card
        title="Metric history"
        subtitle="A metric measured across the runs of one application."
        actions={
          <div className="row">
            <Field label="Application run" htmlFor="metric-history-run">
              <select id="metric-history-run" value={effectiveRunId} onChange={(event) => setRunId(event.target.value)}>
                {(runs.data ?? []).map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.app_name} · {run.app_version} (run {run.id})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Metric" htmlFor="metric-history-metric">
              <select id="metric-history-metric" value={metricName} onChange={(event) => setMetricName(event.target.value)}>
                {(catalogue.data?.metrics ?? []).map((metric) => (
                  <option key={metric.name} value={metric.name}>
                    {metric.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        }
      >
        {history.loading ? (
          <Skeleton rows={5} />
        ) : history.error ? (
          <ErrorState message={history.error} onRetry={history.reload} />
        ) : chartData.length === 0 ? (
          <EmptyState
            title="No history for this selection"
            message="This application has not been evaluated with the selected metric yet."
          />
        ) : (
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} width={46} />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--surface-border-strong)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown) => [
                    value === null || value === undefined ? '—' : formatNumber(Number(value), 3),
                    metricLabel(metricName),
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  name={metricLabel(metricName)}
                  stroke="#3d5afe"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <p className="text-faint text-small">
          {history.data?.metric ? `Metric: ${history.data.metric} · app #${history.data.app_id}` : null}
          {chartData.length > 0 ? ` · last point ${formatDateTime(chartData[chartData.length - 1].created_at)}` : null}
        </p>
      </Card>

      <Card title="Catalogue" subtitle={`${filtered.length} metric(s) match your search`}>
        <Toolbar>
          <Field label="Search metrics" htmlFor="metric-search">
            <input
              id="metric-search"
              type="search"
              value={search}
              placeholder="recall, citation, latency…"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
        </Toolbar>

        {catalogue.loading ? (
          <Skeleton rows={8} />
        ) : catalogue.error ? (
          <ErrorState message={catalogue.error} onRetry={catalogue.reload} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No metric matches"
            message="No metric in the catalogue matches your search. Try a different term."
          />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Metric catalogue</caption>
              <thead>
                <tr>
                  <th scope="col">Metric</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Description</th>
                  <th scope="col">Requires</th>
                  <th scope="col">Evidence requirements</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((metric) => (
                  <tr key={metric.name}>
                    <th scope="row">
                      <code>{metric.name}</code>
                    </th>
                    <td>
                      <MetricKindBadge kind={metric.kind} />
                    </td>
                    <td className="text-small">
                      {metric.description}
                      <br />
                      <span className="text-faint text-small">{metric.kind_description}</span>
                    </td>
                    <td>
                      {metric.requires.length === 0 ? (
                        <span className="text-faint">—</span>
                      ) : (
                        <span className="chip-list">
                          {metric.requires.map((requirement) => (
                            <span className="chip" key={requirement}>
                              {requirement}
                            </span>
                          ))}
                        </span>
                      )}
                    </td>
                    <td className="text-small">
                      {metric.requirements.length === 0 ? (
                        <span className="text-faint">—</span>
                      ) : (
                        <ul className="bullet-list">
                          {metric.requirements.map((requirement) => (
                            <li key={requirement}>{requirement}</li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Judge dimensions &amp; retrievers">
        <div className="grid grid-2">
          <div>
            <h3>Judge dimensions</h3>
            {(catalogue.data?.judge_dimensions ?? []).length === 0 ? (
              <p className="text-muted text-small">No judge dimensions are registered.</p>
            ) : (
              <ul className="bullet-list">
                {(catalogue.data?.judge_dimensions ?? []).map((dimension) => (
                  <li key={dimension}>{dimension}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3>Retrievers</h3>
            {Object.keys(catalogue.data?.retrievers ?? {}).length === 0 ? (
              <p className="text-muted text-small">No retrievers are registered.</p>
            ) : (
              <table className="kv-table">
                <caption className="sr-only">Registered retrievers</caption>
                <tbody>
                  {Object.entries(catalogue.data?.retrievers ?? {}).map(([name, description]) => (
                    <tr key={name}>
                      <th scope="row">{name}</th>
                      <td>{description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <Notice tone="info" title="How to read a kind badge">
          A <strong>deterministic</strong> metric is an exact formula over the supplied evidence. A{' '}
          <strong>heuristic</strong> metric is an estimate and may disagree with human judgement.{' '}
          <strong>Reference-based</strong> metrics need a reference answer, and <strong>LLM-judge</strong> metrics are
          opinion signals, never proof.
        </Notice>
      </Card>
    </>
  )
}
