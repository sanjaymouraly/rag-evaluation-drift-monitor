import { useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton } from '../components/ui'
import { DemoBadge } from '../components/common'
import { Badge } from '../components/ui'
import DatasetItemTable from '../components/DatasetItemTable'
import DatasetItemEditor, { draftFromItem, emptyItemDraft, itemPayloadFromDraft } from '../components/DatasetItemEditor'
import type { ItemDraft } from '../components/DatasetItemEditor'
import { formatDateTime } from '../lib/format'
import type { Dataset, DatasetItem, DatasetValidation } from '../types'

export default function DatasetsPage() {
  const projects = useAsync(() => api.projects.list(), [])
  const datasets = useAsync(() => api.datasets.list(), [])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [items, setItems] = useState<DatasetItem[]>([])
  const [itemsError, setItemsError] = useState<string | null>(null)
  const [itemsLoading, setItemsLoading] = useState(false)
  const [validation, setValidation] = useState<DatasetValidation | null>(null)
  const [synthetic, setSynthetic] = useState<{ created: number; warning: string } | null>(null)
  const [importResult, setImportResult] = useState<{ imported: number; skipped_duplicates: number; received: number } | null>(
    null,
  )
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<DatasetItem | null>(null)
  const [draft, setDraft] = useState<ItemDraft | null>(null)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [creatingDataset, setCreatingDataset] = useState(false)
  const [newDataset, setNewDataset] = useState({ project_id: 0, name: '', version: '1.0', description: '' })
  const fileInput = useRef<HTMLInputElement>(null)

  const demoIds = useMemo(
    () => new Set((projects.data ?? []).filter((project) => project.is_demo).map((project) => project.id)),
    [projects.data],
  )

  const selected: Dataset | null = useMemo(
    () => (datasets.data ?? []).find((dataset) => dataset.id === selectedId) ?? null,
    [datasets.data, selectedId],
  )

  async function loadItems(datasetId: number) {
    setItemsLoading(true)
    setItemsError(null)
    try {
      const data = await api.datasets.items(datasetId)
      setItems(data)
    } catch (cause) {
      setItemsError(cause instanceof Error ? cause.message : 'The items could not be loaded.')
    } finally {
      setItemsLoading(false)
    }
  }

  function selectDataset(dataset: Dataset) {
    setSelectedId(dataset.id)
    setValidation(null)
    setSynthetic(null)
    setImportResult(null)
    void loadItems(dataset.id)
  }

  const createDataset = useMutation(async () => {
    if (!newDataset.name.trim()) throw new Error('The dataset name is required.')
    if (!newDataset.project_id) throw new Error('Select the project that owns this dataset.')
    return api.datasets.create({
      project_id: newDataset.project_id,
      name: newDataset.name.trim(),
      version: newDataset.version.trim() || '1.0',
      description: newDataset.description,
    })
  })

  const saveItem = useMutation(async (itemId: number | null) => {
    if (!draft || !selected) return null
    const { payload, error } = itemPayloadFromDraft(draft)
    if (error) throw new Error(error)
    if (itemId === null) return api.datasets.createItem(selected.id, payload)
    return api.datasets.updateItem(selected.id, itemId, payload)
  })

  const deleteItem = useMutation(async (itemId: number) => {
    if (!selected) return null
    await api.datasets.removeItem(selected.id, itemId)
    return itemId
  })

  const importFile = useMutation(async (file: File) => {
    if (!selected) return null
    return api.datasets.importFile(selected.id, file)
  })

  const generateSynthetic = useMutation(async (maxItems: number) => {
    if (!selected) return null
    return api.datasets.generateSynthetic(selected.id, maxItems)
  })

  const validate = useMutation(async () => {
    if (!selected) return null
    return api.datasets.validate(selected.id)
  })

  async function handleCreateDataset() {
    const created = await createDataset.run()
    if (created) {
      setCreatingDataset(false)
      setNewDataset({ project_id: (projects.data ?? [])[0]?.id ?? 0, name: '', version: '1.0', description: '' })
      datasets.reload()
      selectDataset(created)
    }
  }

  async function handleSaveItem() {
    setEditorError(null)
    const result = await saveItem.run(editingItem?.id ?? null)
    if (result) {
      setEditorOpen(false)
      setEditingItem(null)
      setDraft(null)
      if (selected) await loadItems(selected.id)
    }
  }

  async function handleDeleteItem(item: DatasetItem) {
    if (!window.confirm(`Delete dataset item #${item.id}?`)) return
    const result = await deleteItem.run(item.id)
    if (result !== null && selected) await loadItems(selected.id)
  }

  async function handleImport(file: File | undefined) {
    if (!file) return
    const result = await importFile.run(file)
    if (result) {
      setImportResult(result)
      if (selected) await loadItems(selected.id)
    }
    if (fileInput.current) fileInput.current.value = ''
  }

  async function handleSynthetic() {
    const result = await generateSynthetic.run(10)
    if (result) {
      setSynthetic(result)
      if (selected) await loadItems(selected.id)
    }
  }

  async function handleValidate() {
    const result = await validate.run()
    if (result) setValidation(result)
  }

  return (
    <>
      <PageHeader
        title="Datasets"
        description="Frozen question sets used to evaluate applications. Keep them stable so deltas mean something."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setCreatingDataset((value) => !value)}>
            {creatingDataset ? 'Cancel' : 'New dataset'}
          </button>
        }
      />

      {creatingDataset && (
        <Card title="Create a dataset">
          <div className="grid grid-2">
            <Field label="Project" htmlFor="new-dataset-project" required>
              <select
                id="new-dataset-project"
                value={newDataset.project_id}
                onChange={(event) => setNewDataset({ ...newDataset, project_id: Number(event.target.value) })}
              >
                <option value={0}>Select a project…</option>
                {(projects.data ?? []).map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Name" htmlFor="new-dataset-name" required>
              <input
                id="new-dataset-name"
                value={newDataset.name}
                onChange={(event) => setNewDataset({ ...newDataset, name: event.target.value })}
              />
            </Field>
            <Field label="Version" htmlFor="new-dataset-version" required>
              <input
                id="new-dataset-version"
                value={newDataset.version}
                onChange={(event) => setNewDataset({ ...newDataset, version: event.target.value })}
              />
            </Field>
            <Field label="Description" htmlFor="new-dataset-description">
              <input
                id="new-dataset-description"
                value={newDataset.description}
                onChange={(event) => setNewDataset({ ...newDataset, description: event.target.value })}
              />
            </Field>
          </div>
          {createDataset.error && <Notice tone="danger">{createDataset.error}</Notice>}
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={handleCreateDataset} disabled={createDataset.busy}>
              {createDataset.busy ? 'Creating…' : 'Create dataset'}
            </button>
          </div>
        </Card>
      )}

      <Card title="All datasets" subtitle={`${(datasets.data ?? []).length} dataset(s)`}>
        {datasets.loading ? (
          <Skeleton rows={4} />
        ) : datasets.error ? (
          <ErrorState message={datasets.error} onRetry={datasets.reload} />
        ) : (datasets.data ?? []).length === 0 ? (
          <EmptyState title="No datasets" message="Create a dataset so applications can be evaluated against it." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Datasets</caption>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Project</th>
                  <th scope="col">Items</th>
                  <th scope="col">Flags</th>
                  <th scope="col">Checksum</th>
                  <th scope="col">Created</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(datasets.data ?? []).map((dataset) => {
                  const project = (projects.data ?? []).find((item) => item.id === dataset.project_id)
                  return (
                    <tr key={dataset.id} className={selectedId === dataset.id ? 'row-success' : ''}>
                      <th scope="row">
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => selectDataset(dataset)}>
                          {dataset.name}
                        </button>
                        <div className="text-faint text-small">v{dataset.version}</div>
                      </th>
                      <td className="text-small">
                        <span className="truncate-sm" title={project?.name}>
                          {project?.name ?? `#${dataset.project_id}`}
                        </span>{' '}
                        {project && demoIds.has(project.id) ? <DemoBadge /> : null}
                      </td>
                      <td className="num">{dataset.n_items}</td>
                      <td>
                        <div className="chip-list">
                          {dataset.is_synthetic ? (
                            <Badge tone="warning">Synthetic</Badge>
                          ) : (
                            <Badge tone="muted">Curated</Badge>
                          )}
                          {dataset.reviewed ? (
                            <Badge tone="success">Reviewed</Badge>
                          ) : (
                            <Badge tone="muted">Unreviewed</Badge>
                          )}
                        </div>
                      </td>
                      <td className="num text-small">{dataset.checksum || '—'}</td>
                      <td className="text-small">{formatDateTime(dataset.created_at)}</td>
                      <td>
                        <div className="row">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => selectDataset(dataset)}
                            aria-label={`Browse items of ${dataset.name}`}
                          >
                            Browse
                          </button>
                          <a
                            className="btn btn-secondary btn-sm"
                            href={api.datasets.exportUrl(dataset.id, 'jsonl')}
                            aria-label={`Export ${dataset.name} as JSONL`}
                          >
                            JSONL
                          </a>
                          <a
                            className="btn btn-secondary btn-sm"
                            href={api.datasets.exportUrl(dataset.id, 'csv')}
                            aria-label={`Export ${dataset.name} as CSV`}
                          >
                            CSV
                          </a>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selected && (
        <Card
          title={`${selected.name} · items`}
          subtitle={`${items.length} item(s) loaded${selected.description ? ` — ${selected.description}` : ''}`}
          actions={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingItem(null)
                  setDraft(emptyItemDraft())
                  setEditorOpen(true)
                }}
              >
                Add item
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleValidate} disabled={validate.busy}>
                {validate.busy ? 'Validating…' : 'Validate'}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleSynthetic}
                disabled={generateSynthetic.busy}
              >
                {generateSynthetic.busy ? 'Generating…' : 'Generate synthetic'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => fileInput.current?.click()}>
                Import file
              </button>
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.jsonl,.json,.txt"
                className="sr-only"
                aria-label="Import dataset items from a CSV or JSONL file"
                onChange={(event) => handleImport(event.target.files?.[0])}
              />
            </>
          }
        >
          {importResult && (
            <Notice tone="success" title="Import finished">
              Imported {importResult.imported} item(s), skipped {importResult.skipped_duplicates} duplicate(s) of{' '}
              {importResult.received} received.
            </Notice>
          )}
          {importFile.error && <Notice tone="danger">{importFile.error}</Notice>}

          {synthetic && (
            <Notice tone={synthetic.warning ? 'warning' : 'success'} title={`${synthetic.created} synthetic item(s) created`}>
              {synthetic.warning || 'No additional warning was returned by the backend.'}
            </Notice>
          )}
          {generateSynthetic.error && <Notice tone="danger">{generateSynthetic.error}</Notice>}

          {validation && (
            <div className="stack">
              <Notice tone={validation.ok ? 'success' : 'warning'} title={validation.summary}>
                {validation.n_items} item(s) checked against {validation.corpus_docs} corpus document(s);{' '}
                {validation.n_issues} issue(s) found.
              </Notice>
              {validation.issues.length > 0 && (
                <div className="table-wrap">
                  <table className="data">
                    <caption className="sr-only">Dataset validation issues</caption>
                    <thead>
                      <tr>
                        <th scope="col">Item</th>
                        <th scope="col">Kind</th>
                        <th scope="col">Severity</th>
                        <th scope="col">Detail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {validation.issues.map((issue, index) => (
                        <tr key={`${issue.item_id ?? 'n/a'}-${index}`}>
                          <td className="num">{issue.item_id ?? '—'}</td>
                          <td className="text-small">{issue.kind}</td>
                          <td>
                            <Badge
                              tone={
                                issue.severity === 'error'
                                  ? 'danger'
                                  : issue.severity === 'warning'
                                    ? 'warning'
                                    : 'muted'
                              }
                            >
                              {issue.severity}
                            </Badge>
                          </td>
                          <td className="text-small">{issue.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {editorOpen && draft && (
            <div className="editor-panel">
              <h3>{editingItem ? `Edit item #${editingItem.id}` : 'Add a dataset item'}</h3>
              <DatasetItemEditor draft={draft} onChange={setDraft} idPrefix="dataset-item" />
              {editorError && <Notice tone="danger">{editorError}</Notice>}
              {saveItem.error && <Notice tone="danger">{saveItem.error}</Notice>}
              <div className="row">
                <button type="button" className="btn btn-primary" onClick={handleSaveItem} disabled={saveItem.busy}>
                  {saveItem.busy ? 'Saving…' : 'Save item'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setEditorOpen(false)
                    setEditingItem(null)
                    setDraft(null)
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {itemsLoading ? (
            <Skeleton rows={6} />
          ) : itemsError ? (
            <ErrorState message={itemsError} />
          ) : (
            <DatasetItemTable
              items={items}
              onEdit={(item) => {
                setEditingItem(item)
                setDraft(draftFromItem(item))
                setEditorOpen(true)
              }}
              onDelete={handleDeleteItem}
            />
          )}
          {deleteItem.error && <Notice tone="danger">{deleteItem.error}</Notice>}
        </Card>
      )}
    </>
  )
}
