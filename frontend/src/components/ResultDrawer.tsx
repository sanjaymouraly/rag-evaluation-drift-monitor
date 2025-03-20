import { Drawer, Badge } from './ui'
import { MetricKindBadge, MetricValue } from './common'
import { citationOutcomeBadge } from '../lib/status'
import { formatDuration, formatNumber, metricLabel, NO_VALUE } from '../lib/format'
import type { CitationRecord, RunResult } from '../types'

function evidenceText(value: unknown): string {
  if (value === null || value === undefined) return NO_VALUE
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function citationRecords(result: RunResult): CitationRecord[] {
  const support = result.evidence?.citation_support
  const records = support?.evidence?.records
  if (Array.isArray(records)) return records as CitationRecord[]
  const structural = result.evidence?.citation_structural_valid?.evidence?.records
  if (Array.isArray(structural)) return structural as CitationRecord[]
  return []
}

export default function ResultDrawer({
  result,
  onClose,
}: {
  result: RunResult | null
  onClose: () => void
}) {
  if (!result) return null

  const records = citationRecords(result)
  const unsupportedClaims = result.evidence?.faithfulness?.unsupported_claims ?? []
  const missingEntries = Object.entries(result.evidence ?? {}).filter(([, entry]) => Boolean(entry?.missing_reason))

  return (
    <Drawer open title={`Question #${result.item_id}`} onClose={onClose} wide>
      <section>
        <h3 className="drawer-section-title">Question</h3>
        <p>{result.question}</p>
        <div className="chip-list" style={{ marginTop: 8 }}>
          <span className="chip">{result.category}</span>
          {result.cohorts.map((cohort) => (
            <span className="chip" key={cohort}>
              {cohort}
            </span>
          ))}
          <span className="chip">{result.answerable ? 'answerable' : 'unanswerable'}</span>
          {result.abstained && <span className="chip">abstained</span>}
        </div>
      </section>

      <section>
        <h3 className="drawer-section-title">Answer</h3>
        <p>{result.answer || <span className="text-faint">no answer produced</span>}</p>
      </section>

      {missingEntries.length > 0 && (
        <section>
          <h3 className="drawer-section-title">Missing evidence</h3>
          <ul className="bullet-list">
            {missingEntries.map(([name, entry]) => (
              <li key={name}>
                <strong>{metricLabel(name)}</strong> — {entry?.missing_reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="drawer-section-title">Metric values</h3>
        <div className="table-wrap">
          <table className="data">
            <caption className="sr-only">Per-question metric values</caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Value</th>
                <th scope="col">Kind</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.metrics ?? {}).map(([name, value]) => {
                const entry = result.evidence?.[name]
                return (
                  <tr key={name}>
                    <th scope="row">{metricLabel(name)}</th>
                    <td className="num">
                      {value === null || value === undefined ? (
                        <span className="text-faint">—</span>
                      ) : (
                        formatNumber(value, 3)
                      )}
                    </td>
                    <td>
                      <MetricKindBadge kind={entry?.kind} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="drawer-section-title">
          Citations ({result.citations?.length ?? 0})
        </h3>
        {(result.citations ?? []).length === 0 ? (
          <p className="text-muted text-small">The run returned no citations for this question.</p>
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
                  {citation.quote ? <p className="quote">“{citation.quote}”</p> : <p className="text-faint text-small">no quote supplied</p>}
                  {record?.reason && <p className="text-small text-muted">{record.reason}</p>}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {unsupportedClaims.length > 0 && (
        <section>
          <h3 className="drawer-section-title">Unsupported claims</h3>
          <ul className="bullet-list">
            {unsupportedClaims.map((claim) => (
              <li key={claim}>{claim}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="drawer-section-title">Retrieved passages ({result.retrieved?.length ?? 0})</h3>
        {(result.retrieved ?? []).length === 0 ? (
          <p className="text-muted text-small">Nothing was retrieved for this question.</p>
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
      </section>

      <section>
        <h3 className="drawer-section-title">Timing &amp; tokens</h3>
        <ul className="bullet-list">
          <li>Total latency: {formatDuration(result.latency_ms)}</li>
          <li>Retrieval latency: {formatDuration(result.retrieval_latency_ms)}</li>
          <li>Generation latency: {formatDuration(result.generation_latency_ms)}</li>
          <li>
            Tokens: {formatNumber(result.input_tokens, 0)} in / {formatNumber(result.output_tokens, 0)} out
          </li>
          {result.error && <li className="delta-down">Error: {result.error}</li>}
        </ul>
      </section>

      <section>
        <h3 className="drawer-section-title">Raw evidence</h3>
        <pre>{evidenceText(result.evidence)}</pre>
      </section>
    </Drawer>
  )
}

export function AggregateHint({ aggregate }: { aggregate: { value: number | null; n: number } | undefined }) {
  if (!aggregate) return null
  return (
    <span className="text-faint text-small">
      <MetricValue aggregate={{ ...aggregate, kind: 'deterministic' }} />
    </span>
  )
}
