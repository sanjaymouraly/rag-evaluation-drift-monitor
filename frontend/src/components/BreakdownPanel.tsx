import { useMemo, useState } from 'react'
import { Card, EmptyState, Field } from './ui'
import RunMetricTable from './RunMetricTable'
import type { GroupMetrics, MetricAggregate } from '../types'

/** Per-category / per-cohort metric breakdown of a run. */
export default function BreakdownPanel({
  title,
  groups,
  captionPrefix,
  emptyMessage,
}: {
  title: string
  groups: Record<string, GroupMetrics> | undefined
  captionPrefix: string
  emptyMessage: string
}) {
  const names = useMemo(() => Object.keys(groups ?? {}).sort(), [groups])
  const [selected, setSelected] = useState<string>('')

  const active = selected && names.includes(selected) ? selected : names[0] ?? ''
  const group = groups?.[active]

  const rows = useMemo(
    () =>
      Object.entries(group?.metrics ?? {}).map(([key, aggregate]) => ({
        key,
        aggregate: aggregate as MetricAggregate,
      })),
    [group],
  )

  if (names.length === 0) {
    return (
      <Card title={title}>
        <EmptyState title="No breakdown" message={emptyMessage} />
      </Card>
    )
  }

  return (
    <Card
      title={title}
      subtitle={group ? `${active} — ${group.n} question(s)` : undefined}
      actions={
        <Field label="Group" htmlFor={`breakdown-${captionPrefix}`}>
          <select
            id={`breakdown-${captionPrefix}`}
            value={active}
            onChange={(event) => setSelected(event.target.value)}
            style={{ minWidth: 160 }}
          >
            {names.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </Field>
      }
    >
      {rows.length === 0 ? (
        <p className="text-muted text-small">No metrics were computed for this group.</p>
      ) : (
        <RunMetricTable rows={rows} caption={`${captionPrefix} breakdown for ${active}`} />
      )}
    </Card>
  )
}
