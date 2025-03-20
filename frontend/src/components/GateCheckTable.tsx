import { Badge } from './ui'
import { checkStatusBadge, severityBadge } from '../lib/status'
import { formatNumber, metricLabel, NO_VALUE } from '../lib/format'
import type { GateCheck } from '../types'

function ruleTypeLabel(type: string): string {
  switch (type) {
    case 'min':
      return 'at least'
    case 'max':
      return 'at most'
    case 'max_drop':
      return 'max drop vs baseline'
    case 'max_increase':
      return 'max increase vs baseline'
    case 'min_delta':
      return 'min delta vs baseline'
    default:
      return type
  }
}

export default function GateCheckTable({ checks, caption }: { checks: GateCheck[]; caption: string }) {
  if (checks.length === 0) {
    return <p className="text-muted text-small">This evaluation did not produce any checks.</p>
  }

  return (
    <div className="table-wrap">
      <table className="data">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Check</th>
            <th scope="col">Severity</th>
            <th scope="col">Rule</th>
            <th scope="col">Observed</th>
            <th scope="col">Threshold</th>
            <th scope="col">Baseline</th>
            <th scope="col">Change</th>
            <th scope="col">n</th>
            <th scope="col">95% CI</th>
            <th scope="col">p-value</th>
            <th scope="col">Effect size</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check, index) => {
            const status = checkStatusBadge(check.status)
            const severity = severityBadge(check.severity)
            return (
              <tr
                key={`${check.metric}-${check.type}-${index}`}
                className={status.tone === 'danger' ? 'row-danger' : status.tone === 'warning' ? 'row-warning' : ''}
              >
                <th scope="row">
                  {metricLabel(check.metric)}
                  {check.label ? <div className="text-faint text-small">{check.label}</div> : null}
                </th>
                <td>
                  <Badge tone={severity.tone}>{severity.label}</Badge>
                </td>
                <td className="text-small">
                  {ruleTypeLabel(check.type)}
                  {check.tolerance !== null && check.tolerance !== undefined ? ` ±${check.tolerance}` : ''}
                  {Object.keys(check.scope ?? {}).length > 0 && (
                    <div className="text-faint text-small">
                      {Object.entries(check.scope ?? {})
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(', ')}
                    </div>
                  )}
                </td>
                <td className="num">{check.observed === null ? NO_VALUE : formatNumber(check.observed, 4)}</td>
                <td className="num">{formatNumber(check.threshold, 4)}</td>
                <td className="num">
                  {check.baseline_value === null || check.baseline_value === undefined
                    ? NO_VALUE
                    : formatNumber(check.baseline_value, 4)}
                </td>
                <td className="num">
                  {check.observed_change === null || check.observed_change === undefined
                    ? NO_VALUE
                    : formatNumber(check.observed_change, 4)}
                </td>
                <td className="num">{check.n}</td>
                <td className="num text-small">
                  {check.ci ? `[${formatNumber(check.ci[0], 4)}, ${formatNumber(check.ci[1], 4)}]` : NO_VALUE}
                </td>
                <td className="num text-small">
                  {check.p_value === null || check.p_value === undefined ? NO_VALUE : formatNumber(check.p_value, 4)}
                </td>
                <td className="num text-small">
                  {check.effect_size === null || check.effect_size === undefined
                    ? NO_VALUE
                    : formatNumber(check.effect_size, 3)}
                  {check.effect_magnitude ? ` (${check.effect_magnitude})` : ''}
                </td>
                <td>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <ul className="bullet-list evidence-list">
        {checks.map((check, index) => (
          <li key={`evidence-${index}`}>
            <strong>{metricLabel(check.metric)}</strong> — {check.evidence}
          </li>
        ))}
      </ul>
    </div>
  )
}
