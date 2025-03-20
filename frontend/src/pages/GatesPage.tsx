import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Badge, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { RunLink, VerdictBadge, DemoBadge } from '../components/common'
import PolicyEditor, { draftToPolicy, policyToDraft } from '../components/PolicyEditor'
import type { PolicyDraft } from '../components/PolicyEditor'
import GateCheckTable from '../components/GateCheckTable'
import { formatDateTime } from '../lib/format'
import type { GatePolicy } from '../types'

export default function GatesPage() {
  const policies = useAsync(() => api.gatePolicies.list(), [])
  const projects = useAsync(() => api.projects.list(), [])
  const runs = useAsync(() => api.runs.list(), [])
  const catalogue = useAsync(() => api.metrics.catalogue(), [])
  const evaluations = useAsync(() => api.gateEvaluations.list(), [])

  const [editing, setEditing] = useState<GatePolicy | null>(null)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<PolicyDraft | null>(null)
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null)
  const [candidateRunId, setCandidateRunId] = useState('')
  const [baselineRunId, setBaselineRunId] = useState('')
  const [lastEvaluationId, setLastEvaluationId] = useState<number | null>(null)
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger' | 'warning'; text: string } | null>(null)

  const metricOptions = useMemo(
    () => (catalogue.data?.metrics ?? []).map((metric) => metric.name),
    [catalogue.data],
  )

  const projectOptions = useMemo(
    () => (projects.data ?? []).map((project) => ({ id: project.id, name: project.name })),
    [projects.data],
  )

  const runOptions = useMemo(
    () =>
      (runs.data ?? []).map((run) => ({
        id: run.id,
        label: `#${run.id} · ${run.app_name} ${run.app_version} · ${run.dataset_name}`,
      })),
    [runs.data],
  )

  const save = useMutation(async (id: number | null, payload: ReturnType<typeof draftToPolicy>) => {
    if (!payload.name) throw new Error('The policy name is required.')
    if (payload.rules.length === 0) throw new Error('Add at least one rule before saving the policy.')
    if (id === null) return api.gatePolicies.create(payload)
    return api.gatePolicies.update(id, payload)
  })

  const remove = useMutation((id: number) => api.gatePolicies.remove(id))

  const evaluate = useMutation(async (policyId: number) => {
    if (!candidateRunId) throw new Error('Pick the candidate run to evaluate.')
    return api.gatePolicies.evaluate(policyId, {
      candidate_run_id: Number(candidateRunId),
      baseline_run_id: baselineRunId ? Number(baselineRunId) : null,
    })
  })

  function startCreate() {
    setCreating(true)
    setEditing(null)
    setNotice(null)
    setDraft({
      project_id: projectOptions[0]?.id ?? 0,
      name: '',
      description: '',
      baseline_run_id: runs.data?.[0]?.id ?? null,
      min_samples: 5,
      rules: [
        {
          metric: metricOptions[0] ?? 'recall_at_5',
          type: 'min',
          threshold: 0.8,
          severity: 'hard',
          tolerance: null,
          label: '',
          scopeCategory: '',
          scopeCohort: '',
        },
      ],
    })
  }

  function startEdit(policy: GatePolicy) {
    setCreating(false)
    setEditing(policy)
    setNotice(null)
    setDraft(policyToDraft(policy))
  }

  async function handleSave() {
    if (!draft) return
    setNotice(null)
    const result = await save.run(editing?.id ?? null, draftToPolicy(draft))
    if (result) {
      setNotice({ tone: 'success', text: `Policy “${result.name}” was saved.` })
      setCreating(false)
      setEditing(null)
      setDraft(null)
      policies.reload()
    } else {
      setNotice({ tone: 'danger', text: save.error ?? 'The policy could not be saved.' })
    }
  }

  async function handleDelete(policy: GatePolicy) {
    if (!window.confirm(`Delete policy “${policy.name}”?`)) return
    const result = await remove.run(policy.id)
    if (result !== null) {
      policies.reload()
      evaluations.reload()
    }
  }

  async function handleEvaluate(policy: GatePolicy) {
    setSelectedPolicyId(policy.id)
    setNotice(null)
    const result = await evaluate.run(policy.id)
    if (result) {
      setLastEvaluationId(result.id)
      setNotice({
        tone: result.verdict === 'FAIL' ? 'danger' : result.verdict === 'PASS' ? 'success' : 'warning',
        text: `Verdict ${result.verdict}: ${result.summary}`,
      })
      evaluations.reload()
    } else {
      setNotice({ tone: 'danger', text: evaluate.error ?? 'The evaluation failed.' })
    }
  }

  const lastEvaluation = useMemo(
    () => (evaluations.data ?? []).find((item) => item.id === lastEvaluationId) ?? null,
    [evaluations.data, lastEvaluationId],
  )

  return (
    <>
      <PageHeader
        title="Gate policies"
        description="Release gates turn metric changes into a verdict. A policy defines the rules; an evaluation applies them to a candidate run."
        actions={
          <button type="button" className="btn btn-primary" onClick={startCreate}>
            New policy
          </button>
        }
      />

      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}

      {(creating || editing) && draft && (
        <Card
          title={editing ? `Edit policy “${editing.name}”` : 'New gate policy'}
          actions={
            <button
              type="button"
              className="btn btn-icon"
              onClick={() => {
                setCreating(false)
                setEditing(null)
                setDraft(null)
              }}
              aria-label="Close the policy editor"
            >
              ✕
            </button>
          }
        >
          <PolicyEditor
            draft={draft}
            onChange={setDraft}
            metricOptions={metricOptions}
            projectOptions={projectOptions}
            runOptions={runOptions}
            idPrefix={editing ? `edit-policy-${editing.id}` : 'new-policy'}
          />
          {save.error && <Notice tone="danger">{save.error}</Notice>}
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={save.busy}>
              {save.busy ? 'Saving…' : 'Save policy'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setCreating(false)
                setEditing(null)
                setDraft(null)
              }}
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      <Card title="Evaluate a candidate run" subtitle="Apply a policy to a candidate run and compare it to a baseline.">
        <Toolbar>
          <Field label="Candidate run" htmlFor="gate-candidate-run" required>
            <select id="gate-candidate-run" value={candidateRunId} onChange={(event) => setCandidateRunId(event.target.value)}>
              <option value="">Select a run…</option>
              {runOptions.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Baseline run" htmlFor="gate-baseline-run" hint="Defaults to the policy baseline.">
            <select id="gate-baseline-run" value={baselineRunId} onChange={(event) => setBaselineRunId(event.target.value)}>
              <option value="">Use the policy baseline</option>
              {runOptions.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.label}
                </option>
              ))}
            </select>
          </Field>
        </Toolbar>
        <div className="row">
          {(policies.data ?? []).map((policy) => (
            <button
              key={policy.id}
              type="button"
              className="btn btn-primary"
              onClick={() => handleEvaluate(policy)}
              disabled={evaluate.busy || !candidateRunId}
              aria-label={`Evaluate ${policy.name} against the selected candidate run`}
            >
              {evaluate.busy && selectedPolicyId === policy.id ? 'Evaluating…' : `Evaluate “${policy.name}”`}
            </button>
          ))}
          {(policies.data ?? []).length === 0 && <p className="text-muted text-small">Create a policy first.</p>}
        </div>
        {evaluate.error && <Notice tone="danger">{evaluate.error}</Notice>}
      </Card>

      {lastEvaluation && (
        <Card title={`Evaluation #${lastEvaluation.id} — ${lastEvaluation.verdict}`} subtitle={lastEvaluation.summary}>
          <GateCheckTable checks={lastEvaluation.checks ?? []} caption={`Checks of evaluation ${lastEvaluation.id}`} />
        </Card>
      )}

      <Card title="Policies" subtitle={`${(policies.data ?? []).length} policy/policies`}>
        {policies.loading ? (
          <Skeleton rows={5} />
        ) : policies.error ? (
          <ErrorState message={policies.error} onRetry={policies.reload} />
        ) : (policies.data ?? []).length === 0 ? (
          <EmptyState
            title="No gate policies"
            message="Create a policy with quality floors and regression limits to guard your releases."
            action={
              <button type="button" className="btn btn-primary" onClick={startCreate}>
                New policy
              </button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Gate policies</caption>
              <thead>
                <tr>
                  <th scope="col">Policy</th>
                  <th scope="col">Project</th>
                  <th scope="col">Baseline</th>
                  <th scope="col">Rules</th>
                  <th scope="col">Min samples</th>
                  <th scope="col">Created</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(policies.data ?? []).map((policy) => {
                  const project = (projects.data ?? []).find((item) => item.id === policy.project_id)
                  return (
                    <tr key={policy.id}>
                      <th scope="row">
                        {policy.name}
                        {policy.description ? <div className="text-faint text-small">{policy.description}</div> : null}
                      </th>
                      <td className="text-small">
                        {project?.name ?? `#${policy.project_id}`}{' '}
                        {project?.is_demo ? <DemoBadge /> : null}
                      </td>
                      <td className="text-small">
                        {policy.baseline_run_id ? <RunLink id={policy.baseline_run_id} /> : '—'}
                      </td>
                      <td>
                        <ul className="bullet-list">
                          {(policy.rules ?? []).map((rule, index) => (
                            <li key={index} className="text-small">
                              {rule.metric} · {rule.type} {rule.threshold}
                              {rule.severity ? (
                                <>
                                  {' '}
                                  <Badge tone={rule.severity === 'hard' ? 'danger' : 'warning'}>{rule.severity}</Badge>
                                </>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </td>
                      <td className="num">{policy.min_samples}</td>
                      <td className="text-small">{formatDateTime(policy.created_at)}</td>
                      <td>
                        <div className="row">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => startEdit(policy)}
                            aria-label={`Edit policy ${policy.name}`}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => handleDelete(policy)}
                            aria-label={`Delete policy ${policy.name}`}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {remove.error && <Notice tone="danger">{remove.error}</Notice>}
      </Card>

      <Card title="Evaluation history" subtitle="Every verdict this platform has produced.">
        {evaluations.loading ? (
          <Skeleton rows={5} />
        ) : evaluations.error ? (
          <ErrorState message={evaluations.error} onRetry={evaluations.reload} />
        ) : (evaluations.data ?? []).length === 0 ? (
          <EmptyState title="No evaluations yet" message="Evaluate a candidate run to build the history." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Gate evaluation history</caption>
              <thead>
                <tr>
                  <th scope="col">Evaluation</th>
                  <th scope="col">Verdict</th>
                  <th scope="col">Policy</th>
                  <th scope="col">Candidate</th>
                  <th scope="col">Baseline</th>
                  <th scope="col">Summary</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {(evaluations.data ?? []).map((evaluation) => (
                  <tr
                    key={evaluation.id}
                    className={
                      evaluation.verdict === 'FAIL' ? 'row-danger' : evaluation.verdict === 'INCONCLUSIVE' ? 'row-warning' : ''
                    }
                  >
                    <td className="num">#{evaluation.id}</td>
                    <td>
                      <VerdictBadge verdict={evaluation.verdict} />
                    </td>
                    <td className="text-small">#{evaluation.policy_id}</td>
                    <td>
                      <RunLink id={evaluation.candidate_run_id} />
                    </td>
                    <td>
                      {evaluation.baseline_run_id ? <RunLink id={evaluation.baseline_run_id} /> : '—'}
                    </td>
                    <td className="text-small">{evaluation.summary}</td>
                    <td className="text-small">{formatDateTime(evaluation.created_at)}</td>
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
