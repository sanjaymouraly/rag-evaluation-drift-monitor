import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAsync, useMutation } from '../lib/hooks'
import { Badge, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Skeleton, Toolbar } from '../components/ui'
import ProviderEditor, { emptyProviderDraft, providerToDraft } from '../components/ProviderEditor'
import type { ProviderDraft } from '../components/ProviderEditor'
import { formatDateTime, formatNumber } from '../lib/format'
import type { Provider } from '../types'

export default function ProvidersPage() {
  const presets = useAsync(() => api.providers.presets(), [])
  const providers = useAsync(() => api.providers.list(), [])
  const runs = useAsync(() => api.runs.list(), [])
  const catalogue = useAsync(() => api.metrics.catalogue(), [])
  const rubrics = useAsync(() => api.judge.rubrics(), [])

  const [editing, setEditing] = useState<Provider | null>(null)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<ProviderDraft | null>(null)
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger' | 'warning'; text: string } | null>(null)
  const [testResults, setTestResults] = useState<Record<number, { ok: boolean; detail: string }>>({})
  const [discoveredModels, setDiscoveredModels] = useState<Record<number, string[]>>({})
  const [modelOptions, setModelOptions] = useState<string[]>([])

  const [judgeProviderId, setJudgeProviderId] = useState('')
  const [judgeRunId, setJudgeRunId] = useState('')
  const [judgeBudget, setJudgeBudget] = useState('1.0')
  const [judgeDimensions, setJudgeDimensions] = useState<string[]>([])
  const [judgeBusy, setJudgeBusy] = useState(false)

  const kinds = useMemo(() => (presets.data?.presets ?? []).map((preset) => preset.key), [presets.data])
  const roles = useMemo(() => Object.keys(presets.data?.roles ?? {}), [presets.data])

  const save = useMutation(async (id: number | null, payload: ProviderDraft) => {
    if (!payload.name.trim()) throw new Error('The provider name is required.')
    const body = {
      name: payload.name.trim(),
      kind: payload.kind,
      role: payload.role,
      base_url: payload.base_url,
      api_key: payload.api_key ? payload.api_key : undefined,
      model: payload.model,
      timeout_s: payload.timeout_s,
      retries: payload.retries,
      price_per_1k_input: payload.price_per_1k_input,
      price_per_1k_output: payload.price_per_1k_output,
      is_default: payload.is_default,
      enabled: payload.enabled,
      max_concurrency: payload.max_concurrency,
    }
    if (id === null) return api.providers.create(body)
    return api.providers.update(id, body)
  })

  const remove = useMutation((id: number) => api.providers.remove(id))

  async function handleTest(provider: Provider) {
    try {
      const result = await api.providers.test(provider.id)
      setTestResults((current) => ({ ...current, [provider.id]: { ok: result.ok, detail: result.detail } }))
    } catch (cause) {
      setTestResults((current) => ({
        ...current,
        [provider.id]: { ok: false, detail: cause instanceof Error ? cause.message : 'The test failed.' },
      }))
    }
  }

  async function handleDiscover(provider: Provider) {
    try {
      const result = await api.providers.models(provider.id)
      const ids = result.models.map((model) => model.id)
      setDiscoveredModels((current) => ({ ...current, [provider.id]: ids }))
      setModelOptions((current) => Array.from(new Set([...current, ...ids])))
    } catch (cause) {
      setNotice({
        tone: 'danger',
        text: cause instanceof Error ? cause.message : 'The model list could not be loaded.',
      })
    }
  }

  function applyPreset(key: string) {
    const preset = (presets.data?.presets ?? []).find((item) => item.key === key)
    if (!preset) return
    setCreating(true)
    setEditing(null)
    setNotice(null)
    setDraft({
      ...emptyProviderDraft(),
      name: preset.label,
      kind: preset.key,
      base_url: preset.base_url,
      model: preset.default_model,
    })
  }

  async function handleSave() {
    if (!draft) return
    setNotice(null)
    const result = await save.run(editing?.id ?? null, draft)
    if (result) {
      setNotice({ tone: 'success', text: `Provider “${result.name}” was saved.` })
      setCreating(false)
      setEditing(null)
      setDraft(null)
      providers.reload()
    } else {
      setNotice({ tone: 'danger', text: save.error ?? 'The provider could not be saved.' })
    }
  }

  async function handleJudge() {
    setJudgeBusy(true)
    setNotice(null)
    try {
      await api.judge.run({
        provider_id: Number(judgeProviderId),
        run_id: Number(judgeRunId),
        budget_usd: Number(judgeBudget) || 0,
        dimensions: judgeDimensions,
      })
      setNotice({
        tone: 'success',
        text: 'The judge request was accepted. Scores appear in the run once the evaluation finishes.',
      })
    } catch (cause) {
      setNotice({ tone: 'danger', text: cause instanceof Error ? cause.message : 'The judge request failed.' })
    } finally {
      setJudgeBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Providers"
        description="Model providers used for generation and LLM judging, plus the offline deterministic provider."
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setCreating(true)
              setEditing(null)
              setDraft(emptyProviderDraft())
              setNotice(null)
            }}
          >
            New provider
          </button>
        }
      />

      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}

      <Card
        title="Presets"
        subtitle="Start from a known provider. Presets only pre-fill the form — nothing is created until you save."
      >
        {presets.loading ? (
          <Skeleton rows={4} />
        ) : presets.error ? (
          <ErrorState message={presets.error} onRetry={presets.reload} />
        ) : (
          <div className="grid grid-3">
            {(presets.data?.presets ?? []).map((preset) => (
              <article className="preset-card" key={preset.key}>
                <header>
                  <h3>{preset.label}</h3>
                  {preset.requires_key ? (
                    <Badge tone="warning">API key required</Badge>
                  ) : (
                    <Badge tone="success">No API key</Badge>
                  )}
                </header>
                <dl className="preset-meta">
                  <dt>Protocol</dt>
                  <dd>{preset.protocol}</dd>
                  <dt>Base URL</dt>
                  <dd>{preset.base_url || '—'}</dd>
                  <dt>Default model</dt>
                  <dd>{preset.default_model || '—'}</dd>
                </dl>
                <p className="text-small text-muted">{preset.notes}</p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => applyPreset(preset.key)}
                >
                  Use this preset
                </button>
              </article>
            ))}
          </div>
        )}
        {presets.data?.note && <p className="text-faint text-small">{presets.data.note}</p>}
      </Card>

      {(creating || editing) && draft && (
        <Card
          title={editing ? `Edit ${editing.name}` : 'New provider'}
          actions={
            <button
              type="button"
              className="btn btn-icon"
              onClick={() => {
                setCreating(false)
                setEditing(null)
                setDraft(null)
              }}
              aria-label="Close the provider editor"
            >
              ✕
            </button>
          }
        >
          <ProviderEditor
            draft={draft}
            onChange={setDraft}
            kinds={kinds.length > 0 ? kinds : ['offline']}
            roles={roles.length > 0 ? roles : ['judge']}
            idPrefix={editing ? `edit-provider-${editing.id}` : 'new-provider'}
            modelOptions={modelOptions}
          />
          {save.error && <Notice tone="danger">{save.error}</Notice>}
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={save.busy}>
              {save.busy ? 'Saving…' : 'Save provider'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setCreating(false)
                setEditing(null)
                setDraft(null)
              }}
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      <Card title="Configured providers" subtitle={`${(providers.data ?? []).length} provider(s)`}>
        {providers.loading ? (
          <Skeleton rows={5} />
        ) : providers.error ? (
          <ErrorState message={providers.error} onRetry={providers.reload} />
        ) : (providers.data ?? []).length === 0 ? (
          <EmptyState
            title="No providers configured"
            message="Add a provider so runs can generate answers or so a judge can score them."
          />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">Configured providers</caption>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Role</th>
                  <th scope="col">Model</th>
                  <th scope="col">API key</th>
                  <th scope="col">Price in / out</th>
                  <th scope="col">Enabled</th>
                  <th scope="col">Default</th>
                  <th scope="col">Created</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(providers.data ?? []).map((provider) => (
                  <tr key={provider.id}>
                    <th scope="row">{provider.name}</th>
                    <td className="text-small">{provider.kind}</td>
                    <td className="text-small">{provider.role}</td>
                    <td className="text-small">{provider.model || '—'}</td>
                    <td className="text-small">
                      {provider.has_key ? <Badge tone="success">set</Badge> : <Badge tone="muted">not set</Badge>}
                      {provider.api_key_masked ? (
                        <span className="text-faint text-small"> {provider.api_key_masked}</span>
                      ) : null}
                    </td>
                    <td className="num text-small">
                      {formatNumber(provider.price_per_1k_input, 4)} / {formatNumber(provider.price_per_1k_output, 4)}
                    </td>
                    <td>{provider.enabled ? <Badge tone="success">yes</Badge> : <Badge tone="muted">no</Badge>}</td>
                    <td>{provider.is_default ? <Badge tone="info">default</Badge> : '—'}</td>
                    <td className="text-small">{formatDateTime(provider.created_at)}</td>
                    <td>
                      <div className="row">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            setCreating(false)
                            setEditing(provider)
                            setDraft(providerToDraft(provider))
                            setNotice(null)
                          }}
                          aria-label={`Edit ${provider.name}`}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleTest(provider)}
                          aria-label={`Test the connection to ${provider.name}`}
                        >
                          Test connection
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleDiscover(provider)}
                          aria-label={`Discover models for ${provider.name}`}
                        >
                          Discover models
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={async () => {
                            if (!window.confirm(`Delete provider “${provider.name}”?`)) return
                            const result = await remove.run(provider.id)
                            if (result !== null) providers.reload()
                          }}
                          aria-label={`Delete ${provider.name}`}
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
        )}
        {remove.error && <Notice tone="danger">{remove.error}</Notice>}

        {Object.keys(testResults).length > 0 && (
          <div className="stack">
            {Object.entries(testResults).map(([id, result]) => (
              <Notice key={id} tone={result.ok ? 'success' : 'danger'} title={result.ok ? 'Connection OK' : 'Connection failed'}>
                {result.detail}
              </Notice>
            ))}
          </div>
        )}

        {Object.keys(discoveredModels).length > 0 && (
          <div className="stack">
            {Object.entries(discoveredModels).map(([id, models]) => (
              <div key={id}>
                <h4>Models discovered for provider #{id}</h4>
                {models.length === 0 ? (
                  <p className="text-muted text-small">The provider did not report any models.</p>
                ) : (
                  <span className="chip-list">
                    {models.map((model) => (
                      <span className="chip" key={model}>
                        {model}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="LLM judge" subtitle="Score an existing run with a judge provider.">
        <Toolbar>
          <Field label="Judge provider" htmlFor="judge-panel-provider" required>
            <select id="judge-panel-provider" value={judgeProviderId} onChange={(event) => setJudgeProviderId(event.target.value)}>
              <option value="">Select a provider…</option>
              {(providers.data ?? [])
                .filter((provider) => provider.enabled)
                .map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name} ({provider.model})
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Run" htmlFor="judge-panel-run" required>
            <select id="judge-panel-run" value={judgeRunId} onChange={(event) => setJudgeRunId(event.target.value)}>
              <option value="">Select a run…</option>
              {(runs.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  #{run.id} · {run.app_name} {run.app_version}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Budget (USD)" htmlFor="judge-panel-budget">
            <input
              id="judge-panel-budget"
              type="number"
              min="0"
              step="0.1"
              value={judgeBudget}
              onChange={(event) => setJudgeBudget(event.target.value)}
            />
          </Field>
        </Toolbar>

        <fieldset>
          <legend>Dimensions</legend>
          {(catalogue.data?.judge_dimensions ?? rubrics.data?.rubrics?.map((rubric) => rubric.dimension) ?? []).map(
            (dimension) => (
              <label key={dimension} className="row" style={{ marginBottom: 6 }}>
                <input
                  type="checkbox"
                  checked={judgeDimensions.includes(dimension)}
                  onChange={(event) =>
                    setJudgeDimensions((current) =>
                      event.target.checked
                        ? [...current, dimension]
                        : current.filter((item) => item !== dimension),
                    )
                  }
                />
                <span>{dimension}</span>
              </label>
            ),
          )}
        </fieldset>

        <div className="row">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleJudge}
            disabled={judgeBusy || !judgeProviderId || !judgeRunId}
          >
            {judgeBusy ? 'Requesting…' : 'Request judge scores'}
          </button>
        </div>

        <Notice tone="warning" title="Limitation">
          {rubrics.data?.limitation ?? 'LLM-judge scores are opinion signals, not proof of correctness.'}
        </Notice>
      </Card>
    </>
  )
}
