import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Badge } from './ui'
import { formatDateTime } from '../lib/format'
import type { DatasetItem } from '../types'

const PAGE_SIZE = 10

function chips(values: string[] | undefined): ReactNode {
  if (!values || values.length === 0) return <span className="text-faint">—</span>
  return (
    <span className="chip-list">
      {values.map((value) => (
        <span className="chip" key={value}>
          {value}
        </span>
      ))}
    </span>
  )
}

export default function DatasetItemTable({
  items,
  onEdit,
  onDelete,
}: {
  items: DatasetItem[]
  onEdit: (item: DatasetItem) => void
  onDelete: (item: DatasetItem) => void
}) {
  const [page, setPage] = useState(0)
  const [expanded, setExpanded] = useState<number | null>(null)

  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount - 1)
  const visible = useMemo(
    () => items.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE),
    [items, currentPage],
  )

  if (items.length === 0) {
    return <p className="text-muted text-small">This dataset has no items yet.</p>
  }

  return (
    <div className="stack">
      <div className="table-wrap">
        <table className="data">
          <caption className="sr-only">Dataset items</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Question</th>
              <th scope="col">Category</th>
              <th scope="col">Difficulty</th>
              <th scope="col">Answerable</th>
              <th scope="col">Cohorts</th>
              <th scope="col">Reviewed</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => {
              const isOpen = expanded === item.id
              return (
                <tr key={item.id}>
                  <td className="num">
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      aria-expanded={isOpen}
                      aria-label={`${isOpen ? 'Hide' : 'Show'} details for item ${item.id}`}
                      onClick={() => setExpanded(isOpen ? null : item.id)}
                    >
                      {isOpen ? '▾' : '▸'} {item.id}
                    </button>
                  </td>
                  <th scope="row">
                    <span className="truncate" title={item.question}>
                      {item.question}
                    </span>
                  </th>
                  <td className="text-small">{item.category}</td>
                  <td className="text-small">{item.difficulty}</td>
                  <td>
                    {item.answerable ? (
                      <Badge tone="success">Yes</Badge>
                    ) : (
                      <Badge tone="warning">No</Badge>
                    )}
                  </td>
                  <td>{chips(item.cohorts)}</td>
                  <td>
                    {item.human_reviewed ? (
                      <Badge tone="info">Reviewed</Badge>
                    ) : (
                      <Badge tone="muted">Unreviewed</Badge>
                    )}
                  </td>
                  <td>
                    <div className="row">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => onEdit(item)}
                        aria-label={`Edit item ${item.id}`}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => onDelete(item)}
                        aria-label={`Delete item ${item.id}`}
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

      {visible.map((item) =>
        expanded === item.id ? (
          <div className="item-detail" key={`detail-${item.id}`}>
            <div className="grid grid-3">
              <div>
                <h4>Reference answer</h4>
                <p className="text-small">{item.reference_answer || <span className="text-faint">—</span>}</p>
              </div>
              <div>
                <h4>Aliases</h4>
                {chips(item.aliases)}
              </div>
              <div>
                <h4>Relevant document ids</h4>
                {chips(item.relevant_doc_ids)}
              </div>
              <div>
                <h4>Expected citations</h4>
                {item.expected_citations?.length ? (
                  <ul className="bullet-list">
                    {item.expected_citations.map((citation, index) => (
                      <li key={index} className="text-small">
                        {String(citation.doc_id ?? citation.chunk_id ?? JSON.stringify(citation))}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-faint">—</span>
                )}
              </div>
              <div>
                <h4>Relevance grades</h4>
                {Object.keys(item.relevance_grades ?? {}).length ? (
                  <ul className="bullet-list">
                    {Object.entries(item.relevance_grades).map(([docId, grade]) => (
                      <li key={docId} className="text-small">
                        {docId}: {grade}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-faint">—</span>
                )}
              </div>
              <div>
                <h4>Topic / language / notes</h4>
                <p className="text-small">
                  {item.topic || '—'} · {item.language || '—'}
                </p>
                <p className="text-small text-muted">{item.notes || 'No notes.'}</p>
                <p className="text-faint text-small">
                  {item.is_synthetic ? 'Synthetic item' : 'Curated item'}
                </p>
              </div>
            </div>
          </div>
        ) : null,
      )}

      <div className="row">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setPage((value) => Math.max(0, value - 1))}
          disabled={currentPage === 0}
        >
          Previous
        </button>
        <span className="text-small text-muted">
          Page {currentPage + 1} of {pageCount} · {items.length} item(s)
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}
          disabled={currentPage >= pageCount - 1}
        >
          Next
        </button>
      </div>
    </div>
  )
}

export function ItemCreatedAt({ value }: { value: string }) {
  return <span className="text-faint text-small">{formatDateTime(value)}</span>
}
