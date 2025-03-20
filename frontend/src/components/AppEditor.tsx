import { useMemo } from 'react'
import { Field, Notice } from './ui'
import { flattenConfig, parseJsonObject, stringifyJson } from '../lib/json'
import type { RAGApp } from '../types'

export interface AppDraft {
  project_id: number
  name: string
  version_label: string
  environment: string
  description: string
  config: string
}

export function emptyDraft(projectId: number): AppDraft {
  return {
    project_id: projectId,
    name: '',
    version_label: 'v1',
    environment: 'dev',
    description: '',
    config: '{\n  "retriever": "bm25",\n  "top_k": 5\n}',
  }
}

export function draftFromApp(app: RAGApp): AppDraft {
  return {
    project_id: app.project_id,
    name: app.name,
    version_label: app.version_label,
    environment: app.environment,
    description: app.description,
    config: stringifyJson(app.config),
  }
}

export default function AppEditor({
  draft,
  onChange,
  projectOptions,
  configError,
  idPrefix,
}: {
  draft: AppDraft
  onChange: (next: AppDraft) => void
  projectOptions: Array<{ id: number; name: string }>
  configError: string | null
  idPrefix: string
}) {
  const parsed = useMemo(() => parseJsonObject(draft.config), [draft.config])
  const rows = useMemo(() => flattenConfig(parsed.object), [parsed.object])

  function update<K extends keyof AppDraft>(key: K, value: AppDraft[K]) {
    onChange({ ...draft, [key]: value })
  }

  return (
    <div>
      <Field label="Project" htmlFor={`${idPrefix}-project`} required>
        <select
          id={`${idPrefix}-project`}
          value={draft.project_id}
          onChange={(event) => update('project_id', Number(event.target.value))}
        >
          {projectOptions.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Name" htmlFor={`${idPrefix}-name`} required>
        <input
          id={`${idPrefix}-name`}
          value={draft.name}
          onChange={(event) => update('name', event.target.value)}
          placeholder="library-rag-candidate"
        />
      </Field>

      <Field label="Version label" htmlFor={`${idPrefix}-version`} required>
        <input
          id={`${idPrefix}-version`}
          value={draft.version_label}
          onChange={(event) => update('version_label', event.target.value)}
          placeholder="v1.1-bm25-rechunked"
        />
      </Field>

      <Field label="Environment" htmlFor={`${idPrefix}-env`} required>
        <select
          id={`${idPrefix}-env`}
          value={draft.environment}
          onChange={(event) => update('environment', event.target.value)}
        >
          {['dev', 'staging', 'production', 'shadow'].map((environment) => (
            <option key={environment} value={environment}>
              {environment}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Description" htmlFor={`${idPrefix}-description`}>
        <textarea
          id={`${idPrefix}-description`}
          value={draft.description}
          onChange={(event) => update('description', event.target.value)}
          style={{ minHeight: 70, fontFamily: 'var(--font-sans)' }}
        />
      </Field>

      <Field
        label="Configuration (JSON)"
        htmlFor={`${idPrefix}-config`}
        required
        error={configError}
        hint="Must be a JSON object. The retriever, chunking and generator settings live here."
      >
        <textarea
          id={`${idPrefix}-config`}
          value={draft.config}
          onChange={(event) => update('config', event.target.value)}
          spellCheck={false}
          rows={12}
        />
      </Field>

      {parsed.ok ? (
        <div className="config-preview">
          <h4>Configuration preview</h4>
          <div className="table-wrap">
            <table className="kv-table">
              <caption className="sr-only">Readable configuration key/value table</caption>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{row.key}</th>
                    <td>{row.value}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td className="text-muted">The configuration object is empty.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <Notice tone="warning" title="Configuration preview unavailable">
          {parsed.error}
        </Notice>
      )}
    </div>
  )
}
