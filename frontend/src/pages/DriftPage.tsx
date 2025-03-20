import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Badge, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { psiBand, psiInterpretation } from '../lib/status'
import { formatNumber, metricLabel, NO_VALUE } from '../lib/format'
import { pickComparablePair } from '../lib/runs'
import type { DriftSignal } from '../types'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export default function DriftPage() {
  const runs = useAsync(() => api.runs.list(), [])
  const [baseline, setBaseline] = useState('')
  const [candidate, setCandidate] = useState('')

  const defaults = useMemo(() => pickComparablePair(runs.data ?? []), [runs.data])

  const baselineId = baseline || (defaults.a !== null ? String(defaults.a) : '')
  const candidateId = candidate || (defaults.b !== null ? String(defaults.b) : '')

  const report = useAsync(
    () =>
      baselineId && candidateId
        ? api.drift.compare(Number(baselineId), Number(candidateId))
        : Promise.resolve(null),
    [baselineId, candidateId],
  )

  const signals = useMemo(() => {
    const entries = Object.entries(report.data?.signals ?? {})
    return entries
      .filter(([, signal]) => typeof signal?.psi === 'number')
      .sort((a, b) => (b[1].psi ?? 0) - (a[1].psi ?? 0))
  }, [report.data])

  const structured = useMemo(() => {
    const all = report.data?.signals ?? {}
    return {
      corpus: all.corpus,
      config_diff: all.config_diff,
      dataset: all.dataset,
    }
  }, [report.data])

  return (
    <>
      <PageHeader
        title="Drift"
        description="Compare the distributions of two runs. Drift describes a change in what was observed — it is a hypothesis generator, not proof of a regression."
      />

      <Card title="Choose the runs to compare">
        <Toolbar>
          <Field label="Baseline run" htmlFor="drift-baseline">
            <select id="drift-baseline" value={baselineId} onChange={(event) => setBaseline(event.target.value)}>
              {(runs.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} · {run.app_name} {run.app_version}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Candidate run" htmlFor="drift-candidate">
            <select id="drift-candidate" value={candidateId} onChange={(event) => setCandidate(event.target.value)}>
              {(runs.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} · {run.app_name} {run.app_version}
                </option>
              ))}
            </select>
          </Field>
        </Toolbar>
      </Card>

      {runs.loading || report.loading ? (
        <Card>
          <Skeleton rows={8} />
        </Card>
      ) : report.error ? (
        <ErrorState message={report.error} onRetry={report.reload} />
      ) : !report.data ? (
        <Card>
          <EmptyState title="Pick two runs" message="Choose a baseline and a candidate run to compare their distributions." />
        </Card>
      ) : (
        <>
          <Notice tone="warning" title="Drift is not proof of regression">
            {report.data.disclaimer}
          </Notice>

          <Card
            title="Signals"
            subtitle={`${signals.length} signal(s) with a population stability index, sorted by magnitude.`}
          >
            {signals.length === 0 ? (
              <EmptyState title="No comparable signals" message="These runs share no metric that can be compared." />
            ) : (
              <div className="grid grid-kpi">
                {signals.map(([name, signal]) => (
                  <SignalCard key={name} name={name} signal={signal} />
                ))}
              </div>
            )}
          </Card>

          <Card title="Distribution shift detail" subtitle="Population stability index and Kolmogorov–Smirnov test per signal.">
            <div className="table-wrap">
              <table className="data">
                <caption className="sr-only">Drift signals with PSI and KS statistics</caption>
                <thead>
                  <tr>
                    <th scope="col">Signal</th>
                    <th scope="col">PSI</th>
                    <th scope="col">Interpretation</th>
                    <th scope="col">Mean baseline</th>
                    <th scope="col">Mean candidate</th>
                    <th scope="col">KS statistic</th>
                    <th scope="col">KS p-value</th>
                    <th scope="col">n baseline / candidate</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map(([name, signal]) => {
                    const interpretation = psiInterpretation(signal.psi)
                    return (
                      <tr key={name}>
                        <th scope="row">{metricLabel(name)}</th>
                        <td className="num">{formatNumber(signal.psi, 4)}</td>
                        <td>
                          <Badge tone={interpretation.tone}>{interpretation.label}</Badge>
                        </td>
                        <td className="num">{formatNumber(signal.mean_baseline ?? null, 4)}</td>
                        <td className="num">{formatNumber(signal.mean_candidate ?? null, 4)}</td>
                        <td className="num">{formatNumber(signal.ks?.statistic ?? null, 4)}</td>
                        <td className="num">{formatNumber(signal.ks?.p_value ?? null, 6)}</td>
                        <td className="num text-small">
                          {signal.ks ? `${signal.ks.n_baseline} / ${signal.ks.n_candidate}` : NO_VALUE}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Hypotheses" subtitle="Automatically generated explanations. Treat them as hypotheses, not findings.">
            {report.data.hypotheses.length === 0 ? (
              <EmptyState title="No hypotheses" message="The backend did not produce any hypotheses for this comparison." />
            ) : (
              <ul className="hypothesis-list">
                {report.data.hypotheses.map((hypothesis, index) => (
                  <li key={index}>
                    <Badge tone="warning">Hypothesis</Badge>
                    <span>{hypothesis}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="grid grid-2">
            <Card title="Corpus difference" subtitle="Documents and chunks compared between the two runs.">
              {isRecord(structured.corpus) ? (
                <table className="kv-table">
                  <caption className="sr-only">Corpus difference</caption>
                  <tbody>
                    <tr>
                      <th scope="row">Documents</th>
                      <td>
                        {String(structured.corpus.docs_baseline ?? NO_VALUE)} → {String(structured.corpus.docs_candidate ?? NO_VALUE)}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Chunks</th>
                      <td>
                        {String(structured.corpus.chunks_baseline ?? NO_VALUE)} → {String(structured.corpus.chunks_candidate ?? NO_VALUE)}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Changed documents</th>
                      <td>{JSON.stringify(structured.corpus.changed_doc_ids ?? [])}</td>
                    </tr>
                    <tr>
                      <th scope="row">Added / removed</th>
                      <td>
                        {JSON.stringify(structured.corpus.added_docs ?? [])} / {JSON.stringify(structured.corpus.removed_docs ?? [])}
                      </td>
                    </tr>
                  </tbody>
                </table>
              ) : (
                <p className="text-muted text-small">The backend did not report a corpus comparison.</p>
              )}
            </Card>

            <Card title="Configuration difference" subtitle="Application settings that changed between the runs.">
              {isRecord(structured.config_diff) ? (
                <>
                  <p className="text-small">
                    Changed keys:{' '}
                    {Array.isArray(structured.config_diff.changed_keys) && structured.config_diff.changed_keys.length > 0 ? (
                      <span className="chip-list">
                        {structured.config_diff.changed_keys.map((key) => (
                          <span className="chip" key={String(key)}>
                            {String(key)}
                          </span>
                        ))}
                      </span>
                    ) : (
                      <span className="text-faint">none</span>
                    )}
                  </p>
                  <pre>{JSON.stringify(structured.config_diff, null, 2)}</pre>
                </>
              ) : (
                <p className="text-muted text-small">The backend did not report a configuration comparison.</p>
              )}
            </Card>
          </div>

          <Card title="Dataset identity" subtitle="Both runs must use the same frozen benchmark to be meaningful.">
            {isRecord(structured.dataset) ? (
              <table className="kv-table">
                <caption className="sr-only">Dataset identity</caption>
                <tbody>
                  <tr>
                    <th scope="row">Baseline checksum</th>
                    <td>{String(structured.dataset.baseline_checksum ?? NO_VALUE)}</td>
                  </tr>
                  <tr>
                    <th scope="row">Candidate checksum</th>
                    <td>{String(structured.dataset.candidate_checksum ?? NO_VALUE)}</td>
                  </tr>
                  <tr>
                    <th scope="row">Same dataset</th>
                    <td>{structured.dataset.same_dataset ? 'yes' : 'no'}</td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p className="text-muted text-small">The backend did not report a dataset comparison.</p>
            )}
          </Card>
        </>
      )}
    </>
  )
}

function SignalCard({ name, signal }: { name: string; signal: DriftSignal }) {
  const interpretation = psiInterpretation(signal.psi)
  const band = psiBand(signal.psi)
  return (
    <div className={`stat stat-${interpretation.tone === 'success' ? 'success' : interpretation.tone === 'warning' ? 'warning' : 'danger'}`}>
      <span className="stat-label">{metricLabel(name)}</span>
      <span className="stat-value">{formatNumber(signal.psi, 4)}</span>
      <span className="stat-hint">PSI</span>
      <span className="stat-footer">
        <Badge tone={interpretation.tone}>{interpretation.label}</Badge>
      </span>
      {band !== 'unknown' && (
        <span className="stat-footer">
          KS {formatNumber(signal.ks?.statistic ?? null, 3)} · p {formatNumber(signal.ks?.p_value ?? null, 5)}
        </span>
      )}
    </div>
  )
}
