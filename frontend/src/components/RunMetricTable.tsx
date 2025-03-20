import { MetricKindBadge, MetricValue } from './common'
import { metricLabel } from '../lib/format'
import type { MetricAggregate } from '../types'

export interface MetricTableRow {
  key: string
  aggregate: MetricAggregate
}

/** Aggregate metrics of a run, its category breakdown or its cohort breakdown. */
export default function RunMetricTable({
  rows,
  caption,
  showKind = true,
}: {
  rows: MetricTableRow[]
  caption: string
  showKind?: boolean
}) {
  if (rows.length === 0) {
    return <p className="text-muted text-small">No metrics were computed for this selection.</p>
  }
  return (
    <div className="table-wrap">
      <table className="data">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">Value</th>
            <th scope="col">Samples</th>
            {showKind && <th scope="col">Kind</th>}
            <th scope="col">Std. dev.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <th scope="row">{metricLabel(row.key)}</th>
              <td className="num">
                <MetricValue aggregate={row.aggregate} />
              </td>
              <td className="num">{row.aggregate.n}</td>
              {showKind && (
                <td>
                  <MetricKindBadge kind={row.aggregate.kind} />
                </td>
              )}
              <td className="num">
                {row.aggregate.std === null || row.aggregate.std === undefined ? (
                  <span className="text-faint">—</span>
                ) : (
                  row.aggregate.std.toFixed(3)
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
