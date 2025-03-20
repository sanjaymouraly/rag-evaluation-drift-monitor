import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { MetricValue, RunStatusBadge } from '../components/common'
import RunMetricTable from '../components/RunMetricTable'
import BreakdownPanel from '../components/BreakdownPanel'
import ResultDrawer from '../components/ResultDrawer'
import { downloadBlob, exportFileName } from '../lib/download'
import { formatDateTime, formatDuration, formatNumber, metricLabel } from '../lib/format'
import type { RunResult } from '../types'

const EXPORT_FORMATS = [
  { format: 'md', label: 'Markdown' },
  { format: 'html', label: 'HTML' },
  { format: 'csv', label: 'CSV' },
  { format: 'json', label: 'JSON' },
  { format: 'ci', label: 'CI summary' },
]

export default function RunDetailPage() {
  const { id } = useParams()
  const runId = Number(id)
  const [category, setCategory] = useState('')
  const [cohort, setCohort] = useState('')
  const [failuresOnly, setFailuresOnly] = useState(false)
  const [selectedResult, setSelectedResult] = useState<RunResult | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportBusy, setExportBusy] = useState<string | null>(null)

  const run = useAsync(() => api.runs.get(runId), [runId])
  const results = useAsync(
    () =>
      api.runs.results(runId, {
        category: category || undefined,
        cohort: cohort || undefined,
        failures_only: failuresOnly ? true : undefined,
      }),
    [runId, category, cohort, failuresOnly],
  )

  const cancel = useMutation(() => api.runs.cancel(runId))
  const rerun = useMutation(() => api.runs.rerun(runId))

  const metricRows = useMemo(
    () =>
      Object.entries(run.data?.metrics?.metrics ?? {}).map(([key, aggregate]) => ({ key, aggregate })),
    [run.data],
  )

  const categories = useMemo(() => {
    const set = new Set<string>()
    for (const result of results.data ?? []) set.add(result.category)
    return Array.from(set).sort()
  }, [results.data])

  const cohorts = useMemo(() => {
    const set = new Set<string>()
    for (const result of results.data ?? []) for (const cohort of result.cohorts ?? []) set.add(cohort)
    return Array.from(set).sort()
  }, [results.data])

  async function handleExport(format: string) {
    setExportError(null)
    setExportBusy(format)
    try {
      const blob = await api.runs.exportBlob(runId, format)
      const name = exportFileName(`run-${runId}-report`, format)
      downloadBlob(blob, { fileName: name })
    } catch (cause) {
      setExportError(cause instanceof Error ? cause.message : 'The export failed.')
    } finally {
      setExportBusy(null)
    }
  }

  if (!Number.isFinite(runId)) {
    return (
      <>
        <PageHeader title="Run" />
        <ErrorState message="That run id is not valid." />
      </>
    )
  }

  if (run.loading) {
    return (
      <>
        <PageHeader title="Run detail" />
        <Card>
          <Skeleton rows={8} />
        </Card>
      </>
    )
  }

  if (run.error || !run.data) {
    return (
      <>
        <PageHeader title="Run detail" />
        <ErrorState message={run.error ?? 'The run could not be loaded.'} onRetry={run.reload} />
      </>
    )
  }

  const data = run.data
  const latency = data.metrics?.latency_ms

  return (
    <>
      <PageHeader
        title={`Run #${data.id}`}
        description={
          <>
            {data.app_name} · {data.app_version} evaluated against {data.dataset_name} in <code>{data.mode}</code> mode.
          </>
        }
        actions={
          <>
            {EXPORT_FORMATS.map((entry) => (
              <button
                key={entry.format}
                type="button"
                className="btn btn-secondary"
                onClick={() => handleExport(entry.format)}
                disabled={exportBusy !== null}
              >
                {exportBusy === entry.format ? 'Preparing…' : `Export ${entry.label}`}
              </button>
            ))}
          </>
        }
      />

      {exportError && <Notice tone="danger">{exportError}</Notice>}

      <div className="grid grid-kpi">
        <div className="stat">
          <span className="stat-label">Status</span>
          <span className="stat-value">
            <RunStatusBadge status={data.status} />
          </span>
          <span className="stat-hint">progress {formatNumber(data.progress, 0)}%</span>
        </div>
        <div className="stat">
          <span className="stat-label">Questions</span>
          <span className="stat-value">{formatNumber(data.metrics?.n_questions ?? null, 0)}</span>
          <span className="stat-hint">
            {formatNumber(data.metrics?.n_errors ?? 0, 0)} errors · {formatNumber(data.metrics?.n_abstained ?? 0, 0)}{' '}
            abstained
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">p95 latency</span>
          <span className="stat-value">{formatDuration(latency?.p95 ?? null)}</span>
          <span className="stat-hint">p50 {formatDuration(latency?.p50 ?? null)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Estimated cost</span>
          <span className="stat-value">
            {data.estimated_cost_usd === 0 ? '$0.00' : `$${data.estimated_cost_usd.toFixed(4)}`}
          </span>
          <span className="stat-hint">
            {formatNumber(data.total_input_tokens, 0)} in / {formatNumber(data.total_output_tokens, 0)} out tokens
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Started</span>
          <span className="stat-value text-small">{formatDateTime(data.created_at)}</span>
          <span className="stat-hint">finished {formatDateTime(data.finished_at)}</span>
        </div>
      </div>

      {data.error && <Notice tone="danger" title="Run error">{data.error}</Notice>}

      <div className="row">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => cancel.run()}
          disabled={cancel.busy || data.status === 'completed'}
        >
          {cancel.busy ? 'Cancelling…' : 'Cancel run'}
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => rerun.run()} disabled={rerun.busy}>
          {rerun.busy ? 'Rerunning…' : 'Rerun'}
        </button>
        {cancel.error && <span className="text-small delta-down">{cancel.error}</span>}
        {rerun.error && <span className="text-small delta-down">{rerun.error}</span>}
      </div>

      <Card title="Aggregate metrics" subtitle={`${metricRows.length} metrics computed for this run`}>
        <RunMetricTable rows={metricRows} caption="Aggregate metrics for this run" />
      </Card>

      <div className="grid grid-2">
        <BreakdownPanel
          title="By category"
          groups={data.metrics?.by_category}
          captionPrefix="category"
          emptyMessage="This run did not record a per-category breakdown."
        />
        <BreakdownPanel
          title="By cohort"
          groups={data.metrics?.by_cohort}
          captionPrefix="cohort"
          emptyMessage="This run did not record a per-cohort breakdown."
        />
      </div>

      <Card title="Results" subtitle="Per-question outcomes, metrics and retrieved evidence.">
        <Toolbar>
          <Field label="Category" htmlFor="result-category">
            <select id="result-category" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">All categories</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Cohort" htmlFor="result-cohort">
            <select id="result-cohort" value={cohort} onChange={(event) => setCohort(event.target.value)}>
              <option value="">All cohorts</option>
              {cohorts.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Failures only" htmlFor="result-failures">
            <input
              id="result-failures"
              type="checkbox"
              checked={failuresOnly}
              onChange={(event) => setFailuresOnly(event.target.checked)}
            />
          </Field>
        </Toolbar>

        {results.loading ? (
          <Skeleton rows={6} />
        ) : results.error ? (
          <ErrorState message={results.error} onRetry={results.reload} />
        ) : (results.data ?? []).length === 0 ? (
          <EmptyState
            title="No results match"
            message="No question matches the current filters for this run."
          />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Per-question results for run {data.id}</caption>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Question</th>
                  <th scope="col">Category</th>
                  <th scope="col">Recall@5</th>
                  <th scope="col">Token F1</th>
                  <th scope="col">Faithfulness</th>
                  <th scope="col">Citation support</th>
                  <th scope="col">Citations</th>
                  <th scope="col">Latency</th>
                </tr>
              </thead>
              <tbody>
                {(results.data ?? []).map((result) => (
                  <tr
                    key={result.id}
                    className="row-clickable"
                    tabIndex={0}
                    onClick={() => setSelectedResult(result)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        setSelectedResult(result)
                      }
                    }}
                  >
                    <td className="num">{result.item_id}</td>
                    <td>
                      <span className="truncate" title={result.question}>
                        {result.question}
                      </span>
                    </td>
                    <td className="text-small">{result.category}</td>
                    <td className="num">{formatNumber(result.metrics?.recall_at_5 ?? null, 3)}</td>
                    <td className="num">{formatNumber(result.metrics?.token_f1 ?? null, 3)}</td>
                    <td className="num">{formatNumber(result.metrics?.faithfulness ?? null, 3)}</td>
                    <td className="num">{formatNumber(result.metrics?.citation_support ?? null, 3)}</td>
                    <td className="num">{result.citations?.length ?? 0}</td>
                    <td className="num">{formatDuration(result.latency_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Run configuration" subtitle="The exact app and dataset configuration used for this run.">
        <pre>{JSON.stringify(data.config_snapshot ?? {}, null, 2)}</pre>
      </Card>

      <ResultDrawer result={selectedResult} onClose={() => setSelectedResult(null)} />
    </>
  )
}

export function metricRowLabel(name: string): string {
  return metricLabel(name)
}

export function metricAggregateValue(aggregate: { value: number | null; n: number; kind: string } | undefined) {
  return <MetricValue aggregate={aggregate} />
}
