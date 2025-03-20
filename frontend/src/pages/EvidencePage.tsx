import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { Badge, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import { citationOutcomeBadge } from '../lib/status'
import { formatNumber } from '../lib/format'
import type { CitationRecord, RunResult } from '../types'

function recordsFor(result: RunResult): CitationRecord[] {
  const candidates = [
    result.evidence?.citation_support?.evidence?.records,
    result.evidence?.citation_structural_valid?.evidence?.records,
    result.evidence?.citation_unsupported_rate?.evidence?.records,
  ]
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate as CitationRecord[]
  }
  return []
}

export default function EvidencePage() {
  const runs = useAsync(() => api.runs.list(), [])
  const [runId, setRunId] = useState('')
  const [outcomeFilter, setOutcomeFilter] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)

  const effectiveRunId = runId || String(runs.data?.[0]?.id ?? '')
  const results = useAsync(
    () => (effectiveRunId ? api.runs.results(Number(effectiveRunId)) : Promise.resolve(null)),
    [effectiveRunId],
  )

  const rows = useMemo(() => {
    const list = results.data ?? []
    if (!outcomeFilter) return list
    return list.filter((result) =>
      recordsFor(result).some((record) => record.outcome === outcomeFilter),
    )
  }, [results.data, outcomeFilter])

  const summary = useMemo(() => {
    const counts = { supported: 0, unsupported: 0, irrelevant: 0, structural_invalid: 0, other: 0 }
    for (const result of results.data ?? []) {
      for (const record of recordsFor(result)) {
        const outcome = record.outcome as keyof typeof counts
        if (outcome in counts) counts[outcome] += 1
        else counts.other += 1
      }
    }
    return counts
  }, [results.data])

  return (
    <>
      <PageHeader
        title="Citation &amp; retrieval evidence"
        description="Every citation of a run, classified against the corpus: supported, unsupported, irrelevant or structurally invalid."
      />

      <Card title="Run">
        <Toolbar>
          <Field label="Evaluation run" htmlFor="evidence-run">
            <select id="evidence-run" value={effectiveRunId} onChange={(event) => setRunId(event.target.value)}>
              {(runs.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} · {run.app_name} {run.app_version} · {run.dataset_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Citation outcome" htmlFor="evidence-outcome">
            <select id="evidence-outcome" value={outcomeFilter} onChange={(event) => setOutcomeFilter(event.target.value)}>
              <option value="">All outcomes</option>
              <option value="supported">Supported</option>
              <option value="unsupported">Unsupported</option>
              <option value="irrelevant">Irrelevant</option>
              <option value="structural_invalid">Structurally invalid</option>
            </select>
          </Field>
        </Toolbar>

        <div className="grid grid-kpi">
          <div className="stat stat-success">
            <span className="stat-label">Supported</span>
            <span className="stat-value">{summary.supported}</span>
          </div>
          <div className="stat stat-danger">
            <span className="stat-label">Unsupported</span>
            <span className="stat-value">{summary.unsupported}</span>
          </div>
          <div className="stat stat-warning">
            <span className="stat-label">Irrelevant</span>
            <span className="stat-value">{summary.irrelevant}</span>
          </div>
          <div className="stat stat-danger">
            <span className="stat-label">Structurally invalid</span>
            <span className="stat-value">{summary.structural_invalid}</span>
          </div>
        </div>
      </Card>

      <Card title="Evidence per question" subtitle={`${rows.length} question(s) match the filter`}>
        {results.loading ? (
          <Skeleton rows={8} />
        ) : results.error ? (
          <ErrorState message={results.error} onRetry={results.reload} />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No evidence to show"
            message="No question in this run matches the selected citation outcome."
          />
        ) : (
          <div className="stack">
            {rows.map((result) => {
              const records = recordsFor(result)
              const isOpen = expanded === result.id
              return (
                <article className="evidence-item" key={result.id}>
                  <header className="evidence-head">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      aria-expanded={isOpen}
                      aria-label={`${isOpen ? 'Hide' : 'Show'} evidence for question ${result.item_id}`}
                      onClick={() => setExpanded(isOpen ? null : result.id)}
                    >
                      {isOpen ? 'Hide' : 'Show'}
                    </button>
                    <div className="evidence-question">
                      <strong>{result.question}</strong>
                      <span className="text-faint text-small">
                        item #{result.item_id} · {result.category} · {result.citations?.length ?? 0} citation(s) ·{' '}
                        {result.retrieved?.length ?? 0} passage(s)
                      </span>
                    </div>
                    <div className="chip-list">
                      {records.length === 0 ? (
                        <Badge tone="muted">no citations</Badge>
                      ) : (
                        records.map((record) => {
                          const spec = citationOutcomeBadge(record.outcome)
                          return (
                            <Badge key={`${record.index}-${record.outcome}`} tone={spec.tone}>
                              {spec.label}
                            </Badge>
                          )
                        })
                      )}
                    </div>
                  </header>

                  {isOpen && (
                    <div className="evidence-body">
                      <div className="grid grid-2">
                        <div>
                          <h4>Citations</h4>
                          {(result.citations ?? []).length === 0 ? (
                            <p className="text-muted text-small">This answer produced no citations.</p>
                          ) : (
                            <div className="stack">
                              {result.citations.map((citation, index) => {
                                const record = records.find((item) => item.index === index)
                                const spec = citationOutcomeBadge(record?.outcome)
                                return (
                                  <div className="passage" key={`${citation.chunk_id}-${index}`}>
                                    <div className="passage-head">
                                      <Badge tone={spec.tone}>{spec.label}</Badge>
                                      <strong>{citation.doc_id}</strong>
                                      <span className="text-faint">{citation.chunk_id}</span>
                                    </div>
                                    {citation.quote ? (
                                      <p className="quote">“{citation.quote}”</p>
                                    ) : (
                                      <p className="text-faint text-small">no quote supplied</p>
                                    )}
                                    {record?.reason && <p className="text-small text-muted">{record.reason}</p>}
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                        <div>
                          <h4>Retrieved passages</h4>
                          {(result.retrieved ?? []).length === 0 ? (
                            <p className="text-muted text-small">Nothing was retrieved.</p>
                          ) : (
                            <div className="stack">
                              {result.retrieved.map((chunk) => (
                                <div className="passage" key={chunk.chunk_id}>
                                  <div className="passage-head">
                                    <strong>{chunk.doc_id}</strong>
                                    <span className="text-faint">{chunk.chunk_id}</span>
                                    <span className="chip">score {formatNumber(chunk.score, 3)}</span>
                                  </div>
                                  <p className="passage-text">{chunk.text}</p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {result.error && <Notice tone="danger">Run error: {result.error}</Notice>}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </Card>
    </>
  )
}
