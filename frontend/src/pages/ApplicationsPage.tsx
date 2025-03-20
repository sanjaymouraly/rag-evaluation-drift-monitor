import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Card, EmptyState, ErrorState, Notice, PageHeader, Skeleton } from '../components/ui'
import { DemoBadge } from '../components/common'
import AppEditor, { draftFromApp, emptyDraft } from '../components/AppEditor'
import type { AppDraft } from '../components/AppEditor'
import { parseJsonObject } from '../lib/json'
import { formatDateTime } from '../lib/format'
import { flattenConfig } from '../lib/json'
import type { RAGApp } from '../types'

export default function ApplicationsPage() {
  const projects = useAsync(() => api.projects.list(), [])
  const apps = useAsync(() => api.apps.list(), [])
  const [editing, setEditing] = useState<RAGApp | null>(null)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<AppDraft | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const demoIds = useMemo(
    () => new Set((projects.data ?? []).filter((project) => project.is_demo).map((project) => project.id)),
    [projects.data],
  )

  const projectOptions = useMemo(
    () => (projects.data ?? []).map((project) => ({ id: project.id, name: project.name })),
    [projects.data],
  )

  const grouped = useMemo(() => {
    const map = new Map<number, { name: string; isDemo: boolean; apps: RAGApp[] }>()
    for (const app of apps.data ?? []) {
      const project = (projects.data ?? []).find((item) => item.id === app.project_id)
      const entry = map.get(app.project_id) ?? {
        name: project?.name ?? `Project #${app.project_id}`,
        isDemo: project?.is_demo ?? false,
        apps: [],
      }
      entry.apps.push(app)
      map.set(app.project_id, entry)
    }
    return Array.from(map.entries())
  }, [apps.data, projects.data])

  const save = useMutation(async (payload: { id: number | null; draft: AppDraft }) => {
    const parsed = parseJsonObject(payload.draft.config)
    if (!parsed.ok) throw new Error(parsed.error ?? 'The configuration is not valid JSON.')
    if (!payload.draft.name.trim()) throw new Error('The application name is required.')
    const body = {
      project_id: payload.draft.project_id,
      name: payload.draft.name.trim(),
      version_label: payload.draft.version_label.trim() || 'v1',
      environment: payload.draft.environment,
      description: payload.draft.description,
      config: parsed.object ?? {},
    }
    if (payload.id === null) return api.apps.create(body)
    return api.apps.update(payload.id, body)
  })

  const remove = useMutation((id: number) => api.apps.remove(id))

  function startCreate() {
    setEditing(null)
    setCreating(true)
    setFormError(null)
    setSaved(false)
    setDraft(emptyDraft(projectOptions[0]?.id ?? 0))
  }

  function startEdit(app: RAGApp) {
    setCreating(false)
    setEditing(app)
    setFormError(null)
    setSaved(false)
    setDraft(draftFromApp(app))
  }

  function cancelForm() {
    setCreating(false)
    setEditing(null)
    setDraft(null)
    setFormError(null)
  }

  async function handleSave() {
    if (!draft) return
    setFormError(null)
    setSaved(false)
    const result = await save.run({ id: editing?.id ?? null, draft })
    if (result) {
      setSaved(true)
      setCreating(false)
      setEditing(null)
      setDraft(null)
      apps.reload()
    }
  }

  async function handleDelete(app: RAGApp) {
    if (!window.confirm(`Delete application “${app.name} · ${app.version_label}”?`)) return
    const result = await remove.run(app.id)
    if (result !== null) apps.reload()
  }

  const configError = draft ? (parseJsonObject(draft.config).ok ? null : parseJsonObject(draft.config).error) : null

  return (
    <>
      <PageHeader
        title="Applications"
        description="RAG application versions. Each version carries the retrieval and generation configuration used by evaluation runs."
        actions={
          <button type="button" className="btn btn-primary" onClick={startCreate}>
            New application version
          </button>
        }
      />

      {(creating || editing) && draft && (
        <Card
          title={editing ? `Edit ${editing.name}` : 'New application version'}
          subtitle="The configuration is stored as JSON and is snapshotted into every run."
          actions={
            <button type="button" className="btn btn-icon" onClick={cancelForm} aria-label="Close the application editor">
              ✕
            </button>
          }
        >
          <AppEditor
            draft={draft}
            onChange={setDraft}
            projectOptions={projectOptions}
            configError={configError}
            idPrefix={editing ? `edit-app-${editing.id}` : 'new-app'}
          />
          {formError && <Notice tone="danger">{formError}</Notice>}
          {save.error && <Notice tone="danger">{save.error}</Notice>}
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={save.busy}>
              {save.busy ? 'Saving…' : editing ? 'Save changes' : 'Create application'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={cancelForm}>
              Cancel
            </button>
          </div>
        </Card>
      )}

      {saved && <Notice tone="success">The application was saved.</Notice>}
      {remove.error && <Notice tone="danger">{remove.error}</Notice>}

      {apps.loading ? (
        <Card>
          <Skeleton rows={6} />
        </Card>
      ) : apps.error ? (
        <ErrorState message={apps.error} onRetry={apps.reload} />
      ) : grouped.length === 0 ? (
        <Card>
          <EmptyState
            title="No applications yet"
            message="Create the first application version so you can evaluate it against a dataset."
            action={
              <button type="button" className="btn btn-primary" onClick={startCreate}>
                New application version
              </button>
            }
          />
        </Card>
      ) : (
        grouped.map(([projectId, group]) => (
          <Card
            key={projectId}
            title={group.name}
            subtitle={`${group.apps.length} application version(s)`}
            actions={group.isDemo ? <DemoBadge /> : undefined}
          >
            <div className="table-wrap">
              <table className="data">
                <caption className="sr-only">Application versions in {group.name}</caption>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Version</th>
                    <th scope="col">Environment</th>
                    <th scope="col">Description</th>
                    <th scope="col">Configuration</th>
                    <th scope="col">Created</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {group.apps.map((app) => (
                    <tr key={app.id}>
                      <th scope="row">{app.name}</th>
                      <td className="text-small">{app.version_label}</td>
                      <td className="text-small">{app.environment}</td>
                      <td className="text-small">{app.description || '—'}</td>
                      <td>
                        <details>
                          <summary className="text-small">Show {flattenConfig(app.config).length} setting(s)</summary>
                          <table className="kv-table">
                            <caption className="sr-only">Configuration for {app.name}</caption>
                            <tbody>
                              {flattenConfig(app.config).map((row) => (
                                <tr key={row.key}>
                                  <th scope="row">{row.key}</th>
                                  <td>{row.value}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </details>
                      </td>
                      <td className="text-small">{formatDateTime(app.created_at)}</td>
                      <td>
                        <div className="row">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => startEdit(app)}
                            aria-label={`Edit ${app.name} ${app.version_label}`}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => handleDelete(app)}
                            aria-label={`Delete ${app.name} ${app.version_label}`}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))
      )}
    </>
  )
}
