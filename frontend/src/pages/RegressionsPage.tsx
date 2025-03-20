import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Card, EmptyState, ErrorState, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { RunLink, VerdictBadge } from '../components/common'
import GateCheckTable from '../components/GateCheckTable'
import { formatDateTime } from '../lib/format'

export default function RegressionsPage() {
  const evaluations = useAsync(() => api.gateEvaluations.list(), [])
  const policies = useAsync(() => api.gatePolicies.list(), [])
  const [verdictFilter, setVerdictFilter] = useState('')
  const [policyFilter, setPolicyFilter] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)

  const rows = useMemo(() => {
    let list = evaluations.data ?? []
    if (verdictFilter) list = list.filter((item) => item.verdict === verdictFilter)
    if (policyFilter) list = list.filter((item) => String(item.policy_id) === policyFilter)
    return list
  }, [evaluations.data, verdictFilter, policyFilter])

  const failing = useMemo(() => (evaluations.data ?? []).filter((item) => item.verdict === 'FAIL').length, [evaluations.data])

  return (
    <>
      <PageHeader
        title="Regressions"
        description="Every release-gate evaluation with the evidence behind each verdict. A FAIL row is a release blocker; INCONCLUSIVE means the evidence is missing, not that the change is safe."
      />

      <div className="grid grid-kpi">
        <div className="stat">
          <span className="stat-label">Evaluations</span>
          <span className="stat-value">{(evaluations.data ?? []).length}</span>
        </div>
        <div className="stat stat-danger">
          <span className="stat-label">Failing</span>
          <span className="stat-value">{failing}</span>
          <span className="stat-hint">release blockers</span>
        </div>
        <div className="stat stat-warning">
          <span className="stat-label">Inconclusive</span>
          <span className="stat-value">
            {(evaluations.data ?? []).filter((item) => item.verdict === 'INCONCLUSIVE').length}
          </span>
          <span className="stat-hint">insufficient evidence</span>
        </div>
        <div className="stat stat-success">
          <span className="stat-label">Passing</span>
          <span className="stat-value">
            {(evaluations.data ?? []).filter((item) => item.verdict === 'PASS').length}
          </span>
        </div>
      </div>

      <Card title="Filters">
        <Toolbar>
          <label htmlFor="regression-verdict">Verdict</label>
          <select
            id="regression-verdict"
            value={verdictFilter}
            onChange={(event) => setVerdictFilter(event.target.value)}
            style={{ maxWidth: 220 }}
          >
            <option value="">All verdicts</option>
            <option value="PASS">PASS</option>
            <option value="FAIL">FAIL</option>
            <option value="INCONCLUSIVE">INCONCLUSIVE</option>
          </select>
          <label htmlFor="regression-policy">Policy</label>
          <select
            id="regression-policy"
            value={policyFilter}
            onChange={(event) => setPolicyFilter(event.target.value)}
            style={{ maxWidth: 260 }}
          >
            <option value="">All policies</option>
            {(policies.data ?? []).map((policy) => (
              <option key={policy.id} value={policy.id}>
                {policy.name}
              </option>
            ))}
          </select>
        </Toolbar>
      </Card>

      {evaluations.loading ? (
        <Card>
          <Skeleton rows={6} />
        </Card>
      ) : evaluations.error ? (
        <ErrorState message={evaluations.error} onRetry={evaluations.reload} />
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            title="No evaluations yet"
            message="Evaluate a candidate run against a gate policy to see verdicts and the evidence behind them."
          />
        </Card>
      ) : (
        <Card title="Gate evaluations" subtitle={`${rows.length} evaluation(s)`}>
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Gate evaluations</caption>
              <thead>
                <tr>
                  <th scope="col">Evaluation</th>
                  <th scope="col">Verdict</th>
                  <th scope="col">Policy</th>
                  <th scope="col">Candidate</th>
                  <th scope="col">Baseline</th>
                  <th scope="col">Summary</th>
                  <th scope="col">Created</th>
                  <th scope="col">Details</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((evaluation) => {
                  const policy = (policies.data ?? []).find((item) => item.id === evaluation.policy_id)
                  const isOpen = expanded === evaluation.id
                  return (
                    <tr
                      key={evaluation.id}
                      className={evaluation.verdict === 'FAIL' ? 'row-danger' : evaluation.verdict === 'INCONCLUSIVE' ? 'row-warning' : ''}
                    >
                      <td className="num">#{evaluation.id}</td>
                      <td>
                        <VerdictBadge verdict={evaluation.verdict} />
                      </td>
                      <td className="text-small">{policy?.name ?? `Policy #${evaluation.policy_id}`}</td>
                      <td>
                        <RunLink id={evaluation.candidate_run_id} />
                      </td>
                      <td>
                        {evaluation.baseline_run_id ? <RunLink id={evaluation.baseline_run_id} /> : <span className="text-faint">—</span>}
                      </td>
                      <td className="text-small">{evaluation.summary}</td>
                      <td className="text-small">{formatDateTime(evaluation.created_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          aria-expanded={isOpen}
                          aria-label={`${isOpen ? 'Hide' : 'Show'} checks of evaluation ${evaluation.id}`}
                          onClick={() => setExpanded(isOpen ? null : evaluation.id)}
                        >
                          {isOpen ? 'Hide' : 'Show'} checks
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {rows
            .filter((evaluation) => expanded === evaluation.id)
            .map((evaluation) => (
              <div className="evaluation-detail" key={`detail-${evaluation.id}`}>
                <h3>Checks for evaluation #{evaluation.id}</h3>
                <GateCheckTable checks={evaluation.checks ?? []} caption={`Checks of gate evaluation ${evaluation.id}`} />
              </div>
            ))}
        </Card>
      )}
    </>
  )
}
