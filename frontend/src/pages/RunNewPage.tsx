import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton } from '../components/ui'
import { DemoBadge } from '../components/common'
import { errorMessage } from '../lib/errors'
import type { Run } from '../types'

const MODES = [
  {
    value: 'end_to_end',
    label: 'End to end',
    hint: 'Retrieve, generate and score the whole pipeline.',
  },
  {
    value: 'retrieval_only',
    label: 'Retrieval only',
    hint: 'Score retrieval quality without generating an answer.',
  },
  {
    value: 'generation_only',
    label: 'Generation only',
    hint: 'Score the generator against a pre-supplied context.',
  },
]

const STEPS = ['Select an application', 'Select a dataset', 'Options & launch']

export default function RunNewPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [appId, setAppId] = useState<number | null>(null)
  const [datasetId, setDatasetId] = useState<number | null>(null)
  const [mode, setMode] = useState('end_to_end')
  const [wait, setWait] = useState(false)
  const [judgeProviderId, setJudgeProviderId] = useState('')
  const [judgeBudget, setJudgeBudget] = useState('1.0')
  const [judgeDimensions, setJudgeDimensions] = useState<string[]>([])
  const [launchError, setLaunchError] = useState<string | null>(null)

  const projects = useAsync(() => api.projects.list(), [])
  const apps = useAsync(() => api.apps.list(), [])
  const datasets = useAsync(() => api.datasets.list(), [])
  const providers = useAsync(() => api.providers.list(), [])
  const catalogue = useAsync(() => api.metrics.catalogue(), [])

  const demoIds = useMemo(() => new Set(projects.data?.filter((p) => p.is_demo).map((p) => p.id) ?? []), [projects.data])

  const selectedApp = useMemo(() => (apps.data ?? []).find((app) => app.id === appId) ?? null, [apps.data, appId])
  const selectedDataset = useMemo(
    () => (datasets.data ?? []).find((dataset) => dataset.id === datasetId) ?? null,
    [datasets.data, datasetId],
  )

  const launch = useMutation(async () => {
    const body: Record<string, unknown> = {
      app_id: appId,
      dataset_id: datasetId,
      mode,
      wait,
    }
    if (judgeProviderId) {
      body.judge_provider_id = Number(judgeProviderId)
      body.judge_budget_usd = Number(judgeBudget) || 0
      body.judge_dimensions = judgeDimensions
    }
    return api.runs.create(body)
  })

  async function handleLaunch() {
    setLaunchError(null)
    if (appId === null || datasetId === null) {
      setLaunchError('Select an application and a dataset before launching.')
      return
    }
    const run: Run | null = await launch.run()
    if (run) navigate(`/runs/${run.id}`)
  }

  const canContinue = step === 0 ? appId !== null : step === 1 ? datasetId !== null : true

  return (
    <>
      <PageHeader
        title="New evaluation"
        description="Pick an application version, a dataset and how the run should be executed."
      />

      <Card title="Progress">
        <ol className="wizard-steps">
          {STEPS.map((label, index) => (
            <li
              key={label}
              aria-current={index === step ? 'step' : undefined}
              className={index < step ? 'done' : index === step ? '' : ''}
            >
              <span className="step-number" aria-hidden="true">
                {index < step ? '✓' : index + 1}
              </span>
              {label}
            </li>
          ))}
        </ol>
      </Card>

      {step === 0 && (
        <Card title="Step 1 — Choose an application version">
          {apps.loading ? (
            <Skeleton rows={5} />
          ) : apps.error ? (
            <ErrorState message={apps.error} onRetry={apps.reload} />
          ) : (apps.data ?? []).length === 0 ? (
            <EmptyState
              title="No applications yet"
              message="Create an application version before evaluating it."
              action={
                <a className="btn btn-primary" href="/applications">
                  Create an application
                </a>
              }
            />
          ) : (
            <div className="pick-list">
              {(apps.data ?? []).map((app) => {
                const project = (projects.data ?? []).find((p) => p.id === app.project_id)
                return (
                  <label key={app.id} className={`pick${appId === app.id ? ' pick-selected' : ''}`}>
                    <input
                      type="radio"
                      name="app-pick"
                      value={app.id}
                      checked={appId === app.id}
                      onChange={() => setAppId(app.id)}
                    />
                    <span>
                      <span className="pick-title">
                        {app.name} · {app.version_label}{' '}
                        {project && demoIds.has(project.id) ? <DemoBadge /> : null}
                      </span>
                      <span className="pick-meta">
                        {project?.name ?? `Project #${app.project_id}`} · {app.environment} ·{' '}
                        {app.description || 'no description'}
                      </span>
                    </span>
                  </label>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {step === 1 && (
        <Card title="Step 2 — Choose a dataset">
          {datasets.loading ? (
            <Skeleton rows={5} />
          ) : datasets.error ? (
            <ErrorState message={datasets.error} onRetry={datasets.reload} />
          ) : (datasets.data ?? []).length === 0 ? (
            <EmptyState
              title="No datasets yet"
              message="Create a dataset with evaluation questions before running an evaluation."
              action={
                <a className="btn btn-primary" href="/datasets">
                  Create a dataset
                </a>
              }
            />
          ) : (
            <div className="pick-list">
              {(datasets.data ?? []).map((dataset) => {
                const project = (projects.data ?? []).find((p) => p.id === dataset.project_id)
                return (
                  <label key={dataset.id} className={`pick${datasetId === dataset.id ? ' pick-selected' : ''}`}>
                    <input
                      type="radio"
                      name="dataset-pick"
                      value={dataset.id}
                      checked={datasetId === dataset.id}
                      onChange={() => setDatasetId(dataset.id)}
                    />
                    <span>
                      <span className="pick-title">
                        {dataset.name} v{dataset.version}{' '}
                        {project && demoIds.has(project.id) ? <DemoBadge /> : null}
                      </span>
                      <span className="pick-meta">
                        {dataset.n_items} items · {dataset.reviewed ? 'human reviewed' : 'not reviewed'} ·{' '}
                        {dataset.is_synthetic ? 'synthetic' : 'curated'} ·{' '}
                        {dataset.description || 'no description'}
                      </span>
                    </span>
                  </label>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {step === 2 && (
        <div className="grid grid-2">
          <Card title="Step 3 — Execution mode">
            <fieldset>
              <legend>Mode</legend>
              {MODES.map((option) => (
                <label key={option.value} className="pick" style={{ marginBottom: 8 }}>
                  <input
                    type="radio"
                    name="mode-pick"
                    value={option.value}
                    checked={mode === option.value}
                    onChange={() => setMode(option.value)}
                  />
                  <span>
                    <span className="pick-title">{option.label}</span>
                    <span className="pick-meta">{option.hint}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            <Field
              label="Run synchronously"
              htmlFor="run-wait"
              hint="Wait for the run to finish before returning. Long runs may exceed the request timeout."
            >
              <input
                id="run-wait"
                type="checkbox"
                checked={wait}
                onChange={(event) => setWait(event.target.checked)}
              />
            </Field>
          </Card>

          <Card
            title="LLM judge (optional)"
            subtitle="Adds judge scores on top of the deterministic metrics."
          >
            <Field label="Judge provider" htmlFor="judge-provider">
              <select
                id="judge-provider"
                value={judgeProviderId}
                onChange={(event) => setJudgeProviderId(event.target.value)}
              >
                <option value="">No judge</option>
                {(providers.data ?? [])
                  .filter((provider) => provider.enabled)
                  .map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name} ({provider.model})
                    </option>
                  ))}
              </select>
            </Field>

            <Field label="Judge budget (USD)" htmlFor="judge-budget">
              <input
                id="judge-budget"
                type="number"
                min="0"
                step="0.1"
                value={judgeBudget}
                disabled={!judgeProviderId}
                onChange={(event) => setJudgeBudget(event.target.value)}
              />
            </Field>

            <fieldset>
              <legend>Judge dimensions</legend>
              {(catalogue.data?.judge_dimensions ?? []).map((dimension) => (
                <label key={dimension} className="row" style={{ marginBottom: 6 }}>
                  <input
                    type="checkbox"
                    value={dimension}
                    checked={judgeDimensions.includes(dimension)}
                    onChange={(event) =>
                      setJudgeDimensions((current) =>
                        event.target.checked
                          ? [...current, dimension]
                          : current.filter((item) => item !== dimension),
                      )
                    }
                  />
                  <span>{dimension}</span>
                </label>
              ))}
              {(catalogue.data?.judge_dimensions ?? []).length === 0 && (
                <p className="text-muted text-small">The metric catalogue did not list any judge dimensions.</p>
              )}
            </fieldset>
            <Notice tone="warning" title="Judge scores are opinion signals">
              LLM-judge scores are not proof of correctness. Always read the citation evidence before trusting a
              judge verdict.
            </Notice>
          </Card>
        </div>
      )}

      <Card title="Summary">
        <div className="summary-grid">
          <div>
            <span className="text-faint text-small">Application</span>
            <div>{selectedApp ? `${selectedApp.name} · ${selectedApp.version_label}` : '—'}</div>
          </div>
          <div>
            <span className="text-faint text-small">Dataset</span>
            <div>{selectedDataset ? `${selectedDataset.name} v${selectedDataset.version}` : '—'}</div>
          </div>
          <div>
            <span className="text-faint text-small">Mode</span>
            <div>{mode}</div>
          </div>
          <div>
            <span className="text-faint text-small">Execution</span>
            <div>{wait ? 'synchronous (wait)' : 'asynchronous (background)'}</div>
          </div>
        </div>
        {launchError && <Notice tone="danger">{launchError}</Notice>}
        {launch.error && <Notice tone="danger">{launch.error}</Notice>}
        <div className="row">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setStep((current) => Math.max(0, current - 1))}
            disabled={step === 0}
          >
            Back
          </button>
          {step < 2 ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setStep((current) => Math.min(2, current + 1))}
              disabled={!canContinue}
            >
              Continue
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={handleLaunch} disabled={launch.busy}>
              {launch.busy ? 'Launching…' : 'Launch evaluation'}
            </button>
          )}
        </div>
      </Card>
    </>
  )
}

export function summariseError(cause: unknown): string {
  return errorMessage(cause, 'The run could not be launched.')
}
