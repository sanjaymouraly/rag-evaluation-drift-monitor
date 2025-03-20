import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Card, EmptyState, ErrorState, PageHeader, Skeleton, StatCard, Toolbar } from '../components/ui'
import { DemoBadge, MetricKindBadge, MetricValue, RunLink, RunStatusBadge, VerdictBadge } from '../components/common'
import MetricTrendChart, { HISTORY_METRICS } from '../components/MetricTrendChart'
import type { HistoryMetricKey } from '../components/MetricTrendChart'
import { formatDateTime, formatNumber, metricLabel } from '../lib/format'

const RUN_COLUMNS = [
  'Run',
  'Application',
  'Version',
  'Dataset',
  'Mode',
  'Status',
  'Recall@5',
  'Token F1',
  'Faithfulness',
  'Created',
]

function latestMetric(run: { metrics: { metrics?: Record<string, { value: number | null; n: number; kind: string }> } }, name: string) {
  return run.metrics?.metrics?.[name]
}

export default function OverviewPage() {
  const overview = useAsync(() => api.overview(), [])
  const [selected, setSelected] = useState<HistoryMetricKey[]>(['recall_at_5', 'faithfulness'])

  const demoIds = useMemo(() => new Set(overview.data?.demo_project_ids ?? []), [overview.data])

  function toggleMetric(metric: HistoryMetricKey) {
    setSelected((current) => {
      if (current.includes(metric)) {
        return current.length === 1 ? current : current.filter((item) => item !== metric)
      }
      return [...current, metric]
    })
  }

  if (overview.loading) {
    return (
      <>
        <PageHeader title="Overview" description="Live quality signals across every project, application and evaluation run." />
        <Card>
          <Skeleton rows={8} />
        </Card>
      </>
    )
  }

  if (overview.error || !overview.data) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorState message={overview.error ?? 'The overview could not be loaded.'} onRetry={overview.reload} />
      </>
    )
  }

  const data = overview.data
  const counts = data.counts
  const latest = data.latest_metrics ?? {}

  return (
    <>
      <PageHeader
        title="Overview"
        description="Live quality signals across every project, application and evaluation run."
        actions={
          <Link className="btn btn-primary" to="/runs/new">
            Start an evaluation
          </Link>
        }
      />

      <section aria-label="Key performance indicators">
        <div className="grid grid-kpi">
          <StatCard
            label="Projects"
            value={formatNumber(counts.projects, 0)}
            hint={demoIds.size > 0 ? `${demoIds.size} demo project(s)` : 'No demo projects'}
            tone="neutral"
          />
          <StatCard label="Applications" value={formatNumber(counts.apps, 0)} tone="neutral" />
          <StatCard label="Datasets" value={formatNumber(counts.datasets, 0)} tone="neutral" />
          <StatCard
            label="Runs"
            value={formatNumber(counts.runs, 0)}
            hint={`${counts.runs_completed ?? 0} completed · ${counts.runs_failed ?? 0} failed`}
            tone={(counts.runs_failed ?? 0) > 0 ? 'warning' : 'success'}
          />
          <StatCard
            label="Gate evaluations"
            value={formatNumber(counts.gate_evaluations, 0)}
            tone="info"
          />
          <StatCard
            label="Open alerts"
            value={formatNumber(counts.alerts_open, 0)}
            hint={counts.alerts_open > 0 ? 'Needs attention' : 'All clear'}
            tone={(counts.alerts_open ?? 0) > 0 ? 'danger' : 'success'}
          />
          <StatCard label="Scheduled jobs" value={formatNumber(counts.scheduled_jobs, 0)} tone="neutral" />
          <StatCard
            label="Latest Recall@5"
            value={<MetricValue aggregate={latest.recall_at_5} />}
            hint={latest.recall_at_5 ? `n = ${latest.recall_at_5.n}` : 'no evidence'}
            tone="success"
          />
          <StatCard
            label="Latest Faithfulness"
            value={<MetricValue aggregate={latest.faithfulness} />}
            hint={latest.faithfulness ? `n = ${latest.faithfulness.n}` : 'no evidence'}
            tone="success"
          />
          <StatCard
            label="Latest Token F1"
            value={<MetricValue aggregate={latest.token_f1} />}
            hint={latest.token_f1 ? `n = ${latest.token_f1.n}` : 'no evidence'}
            tone="info"
          />
          <StatCard
            label="Latest Citation support"
            value={<MetricValue aggregate={latest.citation_support} />}
            hint={latest.citation_support ? `n = ${latest.citation_support.n}` : 'no evidence'}
            tone="info"
          />
        </div>
      </section>

      <Card
        title="Metric trend"
        subtitle="Each point is one evaluation run, ordered by creation time."
        actions={
          <div className="metric-toggle" role="group" aria-label="Metrics to display">
            {HISTORY_METRICS.map((metric) => (
              <button
                key={metric.key}
                type="button"
                aria-pressed={selected.includes(metric.key)}
                onClick={() => toggleMetric(metric.key)}
              >
                {metric.label}
              </button>
            ))}
          </div>
        }
      >
        {data.history.length === 0 ? (
          <EmptyState
            title="No runs yet"
            message="Once you launch an evaluation the metric history will be charted here."
            action={
              <Link className="btn btn-primary" to="/runs/new">
                Start an evaluation
              </Link>
            }
          />
        ) : (
          <MetricTrendChart history={data.history} metrics={selected} />
        )}
      </Card>

      <div className="grid grid-2">
        <Card title="Recent runs" subtitle={`${data.recent_runs.length} most recent evaluation runs`}>
          {data.recent_runs.length === 0 ? (
            <EmptyState
              title="No evaluation runs"
              message="Nothing has been evaluated yet. Launch a run to see quality signals."
              action={
                <Link className="btn btn-primary" to="/runs/new">
                  Start an evaluation
                </Link>
              }
            />
          ) : (
            <div className="table-wrap">
              <table className="data">
                <caption className="sr-only">Recent evaluation runs</caption>
                <thead>
                  <tr>
                    {RUN_COLUMNS.map((column) => (
                      <th scope="col" key={column}>
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.recent_runs.map((run) => (
                    <tr key={run.id}>
                      <td>
                        <RunLink id={run.id} />
                      </td>
                      <td>{run.app_name}</td>
                      <td>
                        <span className="text-small">{run.app_version}</span>
                      </td>
                      <td>{run.dataset_name}</td>
                      <td>
                        <span className="text-small">{run.mode}</span>
                      </td>
                      <td>
                        <RunStatusBadge status={run.status} />
                      </td>
                      <td className="num">
                        <MetricValue aggregate={latestMetric(run, 'recall_at_5')} />
                      </td>
                      <td className="num">
                        <MetricValue aggregate={latestMetric(run, 'token_f1')} />
                      </td>
                      <td className="num">
                        <MetricValue aggregate={latestMetric(run, 'faithfulness')} />
                      </td>
                      <td className="text-small">{formatDateTime(run.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="stack">
          <Card title="Gate verdicts" subtitle="Most recent release-gate decisions">
            {data.gate_verdicts.length === 0 ? (
              <EmptyState
                title="No gate evaluations"
                message="Evaluate a candidate run against a policy to see verdicts here."
                action={
                  <Link className="btn btn-secondary" to="/gates">
                    Open gate policies
                  </Link>
                }
              />
            ) : (
              <ul className="verdict-list">
                {data.gate_verdicts.map((verdict) => (
                  <li key={verdict.id} className="verdict-item">
                    <VerdictBadge verdict={verdict.verdict} />
                    <div className="verdict-body">
                      <p className="text-small">{verdict.summary}</p>
                      <p className="text-faint text-small">
                        candidate <RunLink id={verdict.candidate_run_id} /> · baseline{' '}
                        {verdict.baseline_run_id ? <RunLink id={verdict.baseline_run_id} /> : '—'} ·{' '}
                        {formatDateTime(verdict.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            title="Demo projects"
            subtitle="Demo projects are marked so sample data is never mistaken for real measurements."
          >
            <ul className="verdict-list">
              {Array.from(demoIds).map((id) => (
                <li key={id} className="verdict-item">
                  <DemoBadge />
                  <div className="verdict-body">
                    <p className="text-small">Project #{id} is a built-in demo project.</p>
                  </div>
                </li>
              ))}
              {demoIds.size === 0 && <li className="text-muted text-small">No demo projects are registered.</li>}
            </ul>
          </Card>

          <Card title="Latest metric kinds" subtitle="How each headline metric was measured.">
            <ul className="verdict-list">
              {(['recall_at_5', 'token_f1', 'faithfulness', 'citation_support'] as const).map((name) => {
                const aggregate = latest[name]
                return (
                  <li key={name} className="verdict-item">
                    <MetricKindBadge kind={aggregate?.kind} />
                    <div className="verdict-body">
                      <p className="text-small">{metricLabel(name)}</p>
                    </div>
                    <MetricValue aggregate={aggregate} />
                  </li>
                )
              })}
            </ul>
          </Card>
        </div>
      </div>

      <Toolbar>
        <Link className="btn btn-secondary" to="/regressions">
          Review regressions
        </Link>
        <Link className="btn btn-secondary" to="/drift">
          Check drift
        </Link>
        <Link className="btn btn-secondary" to="/compare">
          Compare runs
        </Link>
      </Toolbar>
    </>
  )
}
