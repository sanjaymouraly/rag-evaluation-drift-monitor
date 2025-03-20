import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Field, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { RunLink, RunStatusBadge } from '../components/common'
import { formatDateTime, formatNumber } from '../lib/format'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'completed', label: 'Completed' },
  { value: 'running', label: 'Running' },
  { value: 'queued', label: 'Queued' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
]

export default function RunsPage() {
  const [status, setStatus] = useState('')
  const [appId, setAppId] = useState('')
  const [datasetId, setDatasetId] = useState('')

  const apps = useAsync(() => api.apps.list(), [])
  const datasets = useAsync(() => api.datasets.list(), [])
  const runs = useAsync(
    () =>
      api.runs.list({
        status: status || undefined,
        app_id: appId ? Number(appId) : undefined,
        dataset_id: datasetId ? Number(datasetId) : undefined,
      }),
    [status, appId, datasetId],
  )

  const rows = useMemo(() => runs.data ?? [], [runs.data])

  return (
    <>
      <PageHeader
        title="Evaluation runs"
        description="Every evaluation of an application version against a dataset."
        actions={
          <Link className="btn btn-primary" to="/runs/new">
            New evaluation
          </Link>
        }
      />

      <Card title="Filters">
        <Toolbar>
          <Field label="Status" htmlFor="filter-status">
            <select id="filter-status" value={status} onChange={(event) => setStatus(event.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Application" htmlFor="filter-app">
            <select id="filter-app" value={appId} onChange={(event) => setAppId(event.target.value)}>
              <option value="">All applications</option>
              {(apps.data ?? []).map((app) => (
                <option key={app.id} value={app.id}>
                  {app.name} · {app.version_label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Dataset" htmlFor="filter-dataset">
            <select id="filter-dataset" value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
              <option value="">All datasets</option>
              {(datasets.data ?? []).map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name} v{dataset.version}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setStatus('')
              setAppId('')
              setDatasetId('')
            }}
          >
            Clear filters
          </button>
        </Toolbar>
      </Card>

      <Card title="Runs" subtitle={`${rows.length} run(s) match the current filters`}>
        {runs.loading ? (
          <Skeleton rows={6} />
        ) : runs.error ? (
          <ErrorState message={runs.error} onRetry={runs.reload} />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No runs match"
            message="No evaluation run matches the selected filters. Clear them or launch a new evaluation."
            action={
              <Link className="btn btn-primary" to="/runs/new">
                Start an evaluation
              </Link>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Evaluation runs</caption>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Application</th>
                  <th scope="col">Version</th>
                  <th scope="col">Dataset</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Status</th>
                  <th scope="col">Progress</th>
                  <th scope="col">Questions</th>
                  <th scope="col">Cost</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <RunLink id={run.id} />
                    </td>
                    <td>{run.app_name}</td>
                    <td className="text-small">{run.app_version}</td>
                    <td>{run.dataset_name}</td>
                    <td className="text-small">{run.mode}</td>
                    <td>
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="num">{formatNumber(run.progress, 0)}%</td>
                    <td className="num">{formatNumber(run.metrics?.n_questions ?? null, 0)}</td>
                    <td className="num">
                      {run.estimated_cost_usd === 0
                        ? '$0.00'
                        : `$${run.estimated_cost_usd.toFixed(4)}`}
                      {run.cost_is_estimate && <span className="text-faint text-small"> est.</span>}
                    </td>
                    <td className="text-small">{formatDateTime(run.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
