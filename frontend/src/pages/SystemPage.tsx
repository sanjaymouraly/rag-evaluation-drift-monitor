import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Badge, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { RunLink, RunStatusBadge } from '../components/common'
import { formatDateTime, formatNumber } from '../lib/format'
import type { ScheduledJob } from '../types'

export default function SystemPage() {
  const system = useAsync(() => api.system.get(), [])
  const alerts = useAsync(() => api.alerts.list(), [])
  const jobs = useAsync(() => api.scheduledJobs.list(), [])
  const projects = useAsync(() => api.projects.list(), [])
  const apps = useAsync(() => api.apps.list(), [])
  const datasets = useAsync(() => api.datasets.list(), [])

  const [jobForm, setJobForm] = useState({
    project_id: 0,
    name: '',
    app_id: 0,
    dataset_id: 0,
    policy_id: 0,
    interval_minutes: 60,
    mode: 'end_to_end',
    enabled: true,
  })

  const acknowledge = useMutation((id: number) => api.alerts.acknowledge(id))
  const createJob = useMutation(async () => {
    if (!jobForm.name.trim()) throw new Error('The job name is required.')
    if (!jobForm.project_id) throw new Error('Select a project.')
    if (!jobForm.app_id) throw new Error('Select an application.')
    if (!jobForm.dataset_id) throw new Error('Select a dataset.')
    return api.scheduledJobs.create({
      project_id: jobForm.project_id,
      name: jobForm.name.trim(),
      app_id: jobForm.app_id,
      dataset_id: jobForm.dataset_id,
      policy_id: jobForm.policy_id || null,
      interval_minutes: jobForm.interval_minutes,
      mode: jobForm.mode,
      enabled: jobForm.enabled,
    })
  })

  const removeJob = useMutation((id: number) => api.scheduledJobs.remove(id))

  const executionLog = useMemo(
    () => (system.data?.execution_log ?? []).filter((entry) => entry.status !== 'completed'),
    [system.data],
  )

  async function handleAcknowledge(id: number) {
    const result = await acknowledge.run(id)
    if (result) alerts.reload()
  }

  async function handleCreateJob() {
    const result = await createJob.run()
    if (result) {
      setJobForm({ ...jobForm, name: '' })
      jobs.reload()
    }
  }

  if (system.loading) {
    return (
      <>
        <PageHeader title="System" />
        <Card>
          <Skeleton rows={8} />
        </Card>
      </>
    )
  }

  if (system.error || !system.data) {
    return (
      <>
        <PageHeader title="System" />
        <ErrorState message={system.error ?? 'The system configuration could not be loaded.'} onRetry={system.reload} />
      </>
    )
  }

  const info = system.data

  return (
    <>
      <PageHeader
        title="System"
        description="Runtime configuration, execution log, alerts and scheduled evaluations. Secrets are redacted by the backend."
      />

      <div className="grid grid-kpi">
        <div className="stat">
          <span className="stat-label">Version</span>
          <span className="stat-value text-small">{info.version}</span>
          <span className="stat-hint">{info.environment}</span>
        </div>
        <div className="stat">
          <span className="stat-label">API key auth</span>
          <span className="stat-value text-small">{info.api_key_auth_enabled ? 'enabled' : 'disabled'}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Max workers</span>
          <span className="stat-value">{info.max_workers}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Rate limit / min</span>
          <span className="stat-value">{info.rate_limit_per_minute}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Max upload</span>
          <span className="stat-value text-small">{(info.max_upload_bytes / 1024 / 1024).toFixed(1)} MB</span>
        </div>
        <div className="stat">
          <span className="stat-label">Scheduler</span>
          <span className="stat-value text-small">{info.scheduler_enabled ? 'enabled' : 'disabled'}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Default budget</span>
          <span className="stat-value">${info.default_budget_usd?.toFixed(2)}</span>
          <span className="stat-hint">hard limit ${info.hard_cost_limit_usd?.toFixed(2)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Demo mode</span>
          <span className="stat-value text-small">{info.demo_mode ? 'on' : 'off'}</span>
        </div>
      </div>

      <Card title="Configuration" subtitle="Values are redacted where they could contain a secret.">
        <table className="kv-table">
          <caption className="sr-only">System configuration</caption>
          <tbody>
            <tr>
              <th scope="row">Database</th>
              <td>{info.database}</td>
            </tr>
            <tr>
              <th scope="row">CORS origins</th>
              <td>{info.cors_origins.join(', ') || '—'}</td>
            </tr>
            <tr>
              <th scope="row">Trusted hosts</th>
              <td>{info.trusted_hosts.join(', ') || '—'}</td>
            </tr>
            <tr>
              <th scope="row">Alert webhook</th>
              <td>{info.alert_webhook_configured ? 'configured' : 'not configured'}</td>
            </tr>
            <tr>
              <th scope="row">Max run cost</th>
              <td>${info.max_run_cost_usd?.toFixed(2)}</td>
            </tr>
            <tr>
              <th scope="row">Counts</th>
              <td>
                {Object.entries(info.counts ?? {})
                  .map(([key, value]) => `${key}: ${value}`)
                  .join(' · ')}
              </td>
            </tr>
          </tbody>
        </table>
      </Card>

      <Card title="Execution log" subtitle="Failed or cancelled runs are the ones worth reading.">
        {executionLog.length === 0 ? (
          <EmptyState title="No failures recorded" message="No run has failed or been cancelled recently." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Execution log of failed and cancelled runs</caption>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Status</th>
                  <th scope="col">Error</th>
                  <th scope="col">Created</th>
                  <th scope="col">Finished</th>
                </tr>
              </thead>
              <tbody>
                {executionLog.map((entry) => (
                  <tr key={`${entry.run_id}-${entry.created_at}`} className="row-danger">
                    <td>
                      <RunLink id={entry.run_id} />
                    </td>
                    <td>
                      <RunStatusBadge status={entry.status} />
                    </td>
                    <td className="text-small">{entry.error || '—'}</td>
                    <td className="text-small">{formatDateTime(entry.created_at)}</td>
                    <td className="text-small">{formatDateTime(entry.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Alerts" subtitle={`${(alerts.data ?? []).length} alert(s)`}>
        {alerts.loading ? (
          <Skeleton rows={4} />
        ) : alerts.error ? (
          <ErrorState message={alerts.error} onRetry={alerts.reload} />
        ) : (alerts.data ?? []).length === 0 ? (
          <EmptyState title="No alerts" message="Nothing has been flagged by the drift or gate monitors." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Alerts</caption>
              <thead>
                <tr>
                  <th scope="col">Alert</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Severity</th>
                  <th scope="col">Message</th>
                  <th scope="col">Status</th>
                  <th scope="col">Created</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(alerts.data ?? []).map((alert) => (
                  <tr key={alert.id} className={alert.status === 'open' ? 'row-warning' : ''}>
                    <td className="num">#{alert.id}</td>
                    <td className="text-small">{alert.kind}</td>
                    <td>
                      <Badge tone={alert.severity === 'critical' ? 'danger' : 'warning'}>{alert.severity}</Badge>
                    </td>
                    <td className="text-small">{alert.message}</td>
                    <td>
                      <Badge tone={alert.status === 'open' ? 'warning' : 'success'}>{alert.status}</Badge>
                    </td>
                    <td className="text-small">{formatDateTime(alert.created_at)}</td>
                    <td>
                      {alert.status === 'open' ? (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleAcknowledge(alert.id)}
                          disabled={acknowledge.busy}
                          aria-label={`Acknowledge alert ${alert.id}`}
                        >
                          Acknowledge
                        </button>
                      ) : (
                        <span className="text-faint text-small">acknowledged</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {acknowledge.error && <Notice tone="danger">{acknowledge.error}</Notice>}
      </Card>

      <Card title="Scheduled jobs" subtitle="Recurring evaluations that keep the quality signals fresh.">
        {jobs.loading ? (
          <Skeleton rows={4} />
        ) : jobs.error ? (
          <ErrorState message={jobs.error} onRetry={jobs.reload} />
        ) : (jobs.data ?? []).length === 0 ? (
          <EmptyState title="No scheduled jobs" message="Nothing is scheduled yet. Create one below." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Scheduled jobs</caption>
              <thead>
                <tr>
                  <th scope="col">Job</th>
                  <th scope="col">Application</th>
                  <th scope="col">Dataset</th>
                  <th scope="col">Interval</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Enabled</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(jobs.data ?? []).map((job: ScheduledJob) => (
                  <tr key={job.id}>
                    <th scope="row">{job.name}</th>
                    <td className="text-small">
                      {(apps.data ?? []).find((app) => app.id === job.app_id)?.name ?? `#${job.app_id}`}
                    </td>
                    <td className="text-small">
                      {(datasets.data ?? []).find((dataset) => dataset.id === job.dataset_id)?.name ?? `#${job.dataset_id}`}
                    </td>
                    <td className="num">{formatNumber(job.interval_minutes, 0)} min</td>
                    <td className="text-small">{job.mode}</td>
                    <td>{job.enabled ? <Badge tone="success">yes</Badge> : <Badge tone="muted">no</Badge>}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={async () => {
                          if (!window.confirm(`Delete scheduled job “${job.name}”?`)) return
                          const result = await removeJob.run(job.id)
                          if (result !== null) jobs.reload()
                        }}
                        aria-label={`Delete scheduled job ${job.name}`}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {removeJob.error && <Notice tone="danger">{removeJob.error}</Notice>}
      </Card>

      <Card title="Create a scheduled job">
        <Toolbar>
          <Field label="Name" htmlFor="job-name" required>
            <input
              id="job-name"
              value={jobForm.name}
              onChange={(event) => setJobForm({ ...jobForm, name: event.target.value })}
            />
          </Field>
          <Field label="Project" htmlFor="job-project" required>
            <select
              id="job-project"
              value={jobForm.project_id}
              onChange={(event) => setJobForm({ ...jobForm, project_id: Number(event.target.value) })}
            >
              <option value={0}>Select…</option>
              {(projects.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Application" htmlFor="job-app" required>
            <select
              id="job-app"
              value={jobForm.app_id}
              onChange={(event) => setJobForm({ ...jobForm, app_id: Number(event.target.value) })}
            >
              <option value={0}>Select…</option>
              {(apps.data ?? []).map((app) => (
                <option key={app.id} value={app.id}>
                  {app.name} · {app.version_label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Dataset" htmlFor="job-dataset" required>
            <select
              id="job-dataset"
              value={jobForm.dataset_id}
              onChange={(event) => setJobForm({ ...jobForm, dataset_id: Number(event.target.value) })}
            >
              <option value={0}>Select…</option>
              {(datasets.data ?? []).map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name} v{dataset.version}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Interval (minutes)" htmlFor="job-interval" required>
            <input
              id="job-interval"
              type="number"
              min="1"
              value={jobForm.interval_minutes}
              onChange={(event) => setJobForm({ ...jobForm, interval_minutes: Number(event.target.value) })}
            />
          </Field>
          <Field label="Mode" htmlFor="job-mode">
            <select id="job-mode" value={jobForm.mode} onChange={(event) => setJobForm({ ...jobForm, mode: event.target.value })}>
              <option value="end_to_end">end_to_end</option>
              <option value="retrieval_only">retrieval_only</option>
              <option value="generation_only">generation_only</option>
            </select>
          </Field>
        </Toolbar>
        {createJob.error && <Notice tone="danger">{createJob.error}</Notice>}
        <div className="row">
          <button type="button" className="btn btn-primary" onClick={handleCreateJob} disabled={createJob.busy}>
            {createJob.busy ? 'Creating…' : 'Create scheduled job'}
          </button>
        </div>
      </Card>
    </>
  )
}
