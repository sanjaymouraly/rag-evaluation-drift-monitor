import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { MetricKindBadge } from '../components/common'
import { deltaTone, deltaToneClass, isHigherBetter } from '../lib/status'
import { formatNumber, metricLabel, NO_VALUE } from '../lib/format'
import { pickComparablePair } from '../lib/runs'

const CHART_METRICS = ['recall_at_5', 'token_f1', 'faithfulness', 'citation_support', 'context_precision', 'latency_ms']

export default function ComparePage() {
  const runs = useAsync(() => api.runs.list(), [])
  const [a, setA] = useState('')
  const [b, setB] = useState('')

  const defaults = useMemo(() => pickComparablePair(runs.data ?? []), [runs.data])
  const runA = a || (defaults.a !== null ? String(defaults.a) : '')
  const runB = b || (defaults.b !== null ? String(defaults.b) : '')

  const comparison = useAsync(
    () =>
      runA && runB ? api.compare.two(Number(runA), Number(runB)) : Promise.resolve(null),
    [runA, runB],
  )

  const chartData = useMemo(() => {
    const metrics = comparison.data?.metrics ?? []
    return CHART_METRICS.map((metric) => {
      const row = metrics.find((entry) => entry.metric === metric)
      return {
        metric: metricLabel(metric),
        key: metric,
        runA: row?.a ?? null,
        runB: row?.b ?? null,
      }
    }).filter((row) => row.runA !== null || row.runB !== null)
  }, [comparison.data])

  const perQuestion = comparison.data?.per_question ?? []

  return (
    <>
      <PageHeader
        title="Compare runs"
        description="Compare two evaluation runs question by question to see exactly what changed."
      />

      <Card title="Choose the runs to compare">
        <Toolbar>
          <Field label="Baseline run (A)" htmlFor="compare-run-a">
            <select id="compare-run-a" value={runA} onChange={(event) => setA(event.target.value)}>
              {(runs.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} · {run.app_name} {run.app_version} · {run.dataset_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Candidate run (B)" htmlFor="compare-run-b">
            <select id="compare-run-b" value={runB} onChange={(event) => setB(event.target.value)}>
              {(runs.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} · {run.app_name} {run.app_version} · {run.dataset_name}
                </option>
              ))}
            </select>
          </Field>
        </Toolbar>
        {comparison.data && !comparison.data.comparable && comparison.data.warning && (
          <Notice tone="warning" title="These runs are not directly comparable">
            {comparison.data.warning}
          </Notice>
        )}
      </Card>

      {runs.loading || comparison.loading ? (
        <Card>
          <Skeleton rows={8} />
        </Card>
      ) : comparison.error ? (
        <ErrorState message={comparison.error} onRetry={comparison.reload} />
      ) : !comparison.data ? (
        <Card>
          <EmptyState title="Pick two runs" message="Choose a baseline and a candidate run to compare them." />
        </Card>
      ) : (
        <>
          <Card
            title="Metric deltas"
            subtitle={`Run #${comparison.data.run_a.id} (${comparison.data.run_a.app_version}) → run #${comparison.data.run_b.id} (${comparison.data.run_b.app_version})`}
          >
            <div className="table-wrap">
              <table className="data">
                <caption className="sr-only">Metric deltas between the two selected runs</caption>
                <thead>
                  <tr>
                    <th scope="col">Metric</th>
                    <th scope="col">Run A</th>
                    <th scope="col">Run B</th>
                    <th scope="col">Delta (B − A)</th>
                    <th scope="col">Samples</th>
                    <th scope="col">Kind</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.data.metrics.map((row) => {
                    const tone = deltaTone(row.delta_b_minus_a, isHigherBetter(row.metric))
                    return (
                      <tr key={row.metric}>
                        <th scope="row">{metricLabel(row.metric)}</th>
                        <td className="num">
                          {row.a === null ? NO_VALUE : formatNumber(row.a, 3)}
                          <span className="text-faint text-small"> (n={row.n_a})</span>
                        </td>
                        <td className="num">
                          {row.b === null ? NO_VALUE : formatNumber(row.b, 3)}
                          <span className="text-faint text-small"> (n={row.n_b})</span>
                        </td>
                        <td className={`num ${deltaToneClass(tone)}`}>
                          {row.delta_b_minus_a === null ? NO_VALUE : formatNumber(row.delta_b_minus_a, 3)}
                        </td>
                        <td className="num text-small">
                          {row.n_a} / {row.n_b}
                        </td>
                        <td>
                          <MetricKindBadge kind={row.kind} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Key metrics side by side" subtitle="Baseline and candidate values for the headline metrics.">
            {chartData.length === 0 ? (
              <EmptyState title="Nothing to chart" message="These runs share no comparable headline metric." />
            ) : (
              <div className="chart-frame chart-tall">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" />
                    <XAxis dataKey="metric" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} width={46} />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--surface-border-strong)',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(value: unknown) =>
                        value === null || value === undefined ? NO_VALUE : formatNumber(Number(value), 3)
                      }
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="runA" name={`Run #${comparison.data.run_a.id}`} fill="#8b94a7" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="runB" name={`Run #${comparison.data.run_b.id}`} fill="#3d5afe" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <Card
            title="Per-question comparison"
            subtitle={`${perQuestion.length} question(s) compared. Rows where the top-5 documents changed are highlighted.`}
          >
            {perQuestion.length === 0 ? (
              <EmptyState title="No comparable questions" message="The two runs did not share any question ids." />
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <caption className="sr-only">Per-question comparison between the two runs</caption>
                  <thead>
                    <tr>
                      <th scope="col">Item</th>
                      <th scope="col">Question</th>
                      <th scope="col">Category</th>
                      <th scope="col">F1 A</th>
                      <th scope="col">F1 B</th>
                      <th scope="col">Δ F1</th>
                      <th scope="col">Recall A</th>
                      <th scope="col">Recall B</th>
                      <th scope="col">Citation support A</th>
                      <th scope="col">Citation support B</th>
                      <th scope="col">Top-5 changed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perQuestion.map((row) => (
                      <tr key={row.item_id} className={row.top5_changed ? 'row-warning' : ''}>
                        <td className="num">{row.item_id}</td>
                        <th scope="row">
                          <span className="truncate" title={row.question}>
                            {row.question}
                          </span>
                        </th>
                        <td className="text-small">{row.category}</td>
                        <td className="num">{formatNumber(row.f1_a, 3)}</td>
                        <td className="num">{formatNumber(row.f1_b, 3)}</td>
                        <td className={`num ${deltaToneClass(deltaTone(row.f1_delta, true))}`}>
                          {row.f1_delta === null ? NO_VALUE : formatNumber(row.f1_delta, 3)}
                        </td>
                        <td className="num">{formatNumber(row.recall_a, 3)}</td>
                        <td className="num">{formatNumber(row.recall_b, 3)}</td>
                        <td className="num">{formatNumber(row.citation_support_a, 3)}</td>
                        <td className="num">{formatNumber(row.citation_support_b, 3)}</td>
                        <td className="text-small">{row.top5_changed ? 'yes' : 'no'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}
