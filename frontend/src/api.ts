/**
 * Typed API client for the RAG Quality Monitor backend.
 *
 * The base URL resolution keeps the dev and container proxies working:
 *  - `VITE_API_BASE` set to a non-empty value -> absolute base URL (verbatim).
 *  - otherwise -> same-origin relative `/api` paths.
 *
 * Same-origin is the right default for both setups we ship:
 *  - the Vite dev server proxies `/api` to the backend, and
 *  - the production image serves the SPA from nginx, which proxies `/api` to
 *    the backend container.
 * Set `VITE_API_BASE` only when the API lives on a different host.
 */
import type {
  Alert,
  CompareMultiResponse,
  CompareResponse,
  Dataset,
  DatasetItem,
  DatasetValidation,
  DocumentRecord,
  DriftReport,
  GateEvaluation,
  GatePolicy,
  GatePolicyDefaults,
  HealthInfo,
  ImportResult,
  JudgeRubrics,
  MetricCatalogue,
  MetricHistory,
  Overview,
  Project,
  Provider,
  ProviderModel,
  ProviderPresets,
  ProviderTestResult,
  RAGApp,
  Run,
  RunResult,
  ScheduledJob,
  SyntheticResult,
  SystemInfo,
} from './types'
import { ApiError, extractErrorDetail } from './lib/errors'

const envBase = (import.meta.env.VITE_API_BASE as string | undefined | null)?.trim()
/** Same origin: both the Vite dev server and the nginx image proxy `/api`. */
export const API_BASE = (envBase && envBase.length > 0 ? envBase : '').replace(/\/+$/, '')

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined | null>
  signal?: AbortSignal
}

export function buildQuery(query?: RequestOptions['query']): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, signal } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) {
    payload = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(apiUrl(path) + buildQuery(query), { method, headers, body: payload, signal })
  } catch (cause) {
    if ((cause as Error)?.name === 'AbortError') throw cause
    throw new ApiError(0, `Cannot reach the API at ${apiUrl(path)} — is the backend running?`, cause)
  }

  if (!response.ok) {
    let parsed: unknown = null
    const text = await response.text().catch(() => '')
    if (text) {
      try {
        parsed = JSON.parse(text)
      } catch {
        parsed = text
      }
    }
    const detail = extractErrorDetail(parsed) ?? `Request failed with status ${response.status}`
    throw new ApiError(response.status, detail, parsed)
  }

  if (response.status === 204) return undefined as T
  const text = await response.text()
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError(response.status, 'The API returned a response that is not valid JSON.', text)
  }
}

/** Fetch a binary/text artefact (exports) and hand it to the browser as a blob. */
export async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const { method = 'GET', body, query, signal } = options
  const headers: Record<string, string> = {}
  let payload: BodyInit | undefined
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const response = await fetch(apiUrl(path) + buildQuery(query), { method, headers, body: payload, signal })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    let parsed: unknown = text
    try {
      parsed = JSON.parse(text)
    } catch {
      /* keep raw text */
    }
    throw new ApiError(response.status, extractErrorDetail(parsed) ?? `Request failed with status ${response.status}`, parsed)
  }
  return response.blob()
}

export const api = {
  health: () => request<HealthInfo>('/health'),
  overview: () => request<Overview>('/api/overview'),

  projects: {
    list: () => request<Project[]>('/api/projects'),
    create: (body: { name: string; description?: string }) => request<Project>('/api/projects', { method: 'POST', body }),
    remove: (id: number) => request<void>(`/api/projects/${id}`, { method: 'DELETE' }),
  },

  apps: {
    list: (projectId?: number) => request<RAGApp[]>('/api/apps', { query: { project_id: projectId } }),
    create: (body: Partial<RAGApp> & { project_id: number; name: string }) =>
      request<RAGApp>('/api/apps', { method: 'POST', body }),
    update: (id: number, body: Partial<RAGApp>) => request<RAGApp>(`/api/apps/${id}`, { method: 'PUT', body }),
    remove: (id: number) => request<void>(`/api/apps/${id}`, { method: 'DELETE' }),
  },

  documents: {
    list: (projectId: number) => request<DocumentRecord[]>('/api/documents', { query: { project_id: projectId } }),
    create: (body: Record<string, unknown>) => request<DocumentRecord>('/api/documents', { method: 'POST', body }),
    upload: (projectId: number, file: File) => {
      const form = new FormData()
      form.append('file', file)
      return request<DocumentRecord>('/api/documents/upload', {
        method: 'POST',
        body: form,
        query: { project_id: projectId },
      })
    },
    remove: (id: number) => request<void>(`/api/documents/${id}`, { method: 'DELETE' }),
  },

  datasets: {
    list: () => request<Dataset[]>('/api/datasets'),
    get: (id: number) => request<Dataset>(`/api/datasets/${id}`),
    create: (body: { project_id: number; name: string; version?: string; description?: string }) =>
      request<Dataset>('/api/datasets', { method: 'POST', body }),
    remove: (id: number) => request<void>(`/api/datasets/${id}`, { method: 'DELETE' }),
    clone: (id: number) => request<Dataset>(`/api/datasets/${id}/clone`, { method: 'POST' }),
    items: (id: number) => request<DatasetItem[]>(`/api/datasets/${id}/items`),
    createItem: (id: number, body: Record<string, unknown>) =>
      request<DatasetItem>(`/api/datasets/${id}/items`, { method: 'POST', body }),
    updateItem: (id: number, itemId: number, body: Record<string, unknown>) =>
      request<DatasetItem>(`/api/datasets/${id}/items/${itemId}`, { method: 'PUT', body }),
    removeItem: (id: number, itemId: number) =>
      request<void>(`/api/datasets/${id}/items/${itemId}`, { method: 'DELETE' }),
    importFile: (id: number, file: File) => {
      const form = new FormData()
      form.append('file', file)
      return request<ImportResult>(`/api/datasets/${id}/import`, { method: 'POST', body: form })
    },
    exportUrl: (id: number, format: 'jsonl' | 'csv') => apiUrl(`/api/datasets/${id}/export`) + `?format=${format}`,
    validate: (id: number) => request<DatasetValidation>(`/api/datasets/${id}/validate`),
    generateSynthetic: (id: number, maxItems: number) =>
      request<SyntheticResult>(`/api/datasets/${id}/generate-synthetic`, {
        method: 'POST',
        body: { max_items: maxItems },
      }),
  },

  runs: {
    list: (query?: { app_id?: number; dataset_id?: number; status?: string }) =>
      request<Run[]>('/api/runs', { query }),
    get: (id: number) => request<Run>(`/api/runs/${id}`),
    create: (body: Record<string, unknown>) => request<Run>('/api/runs', { method: 'POST', body }),
    cancel: (id: number) => request<Run>(`/api/runs/${id}/cancel`, { method: 'POST' }),
    rerun: (id: number) => request<Run>(`/api/runs/${id}/rerun`, { method: 'POST' }),
    results: (id: number, query?: { category?: string; cohort?: string; failures_only?: boolean }) =>
      request<RunResult[]>(`/api/runs/${id}/results`, { query }),
    result: (id: number, resultId: number) => request<RunResult>(`/api/runs/${id}/results/${resultId}`),
    history: (id: number, metric: string, limit = 50) =>
      request<MetricHistory>(`/api/runs/${id}/history`, { query: { metric, limit } }),
    exportUrl: (id: number, format: string) => apiUrl(`/api/runs/${id}/export`) + `?format=${format}`,
    exportBlob: (id: number, format: string) => requestBlob(`/api/runs/${id}/export`, { query: { format } }),
  },

  compare: {
    two: (a: number, b: number) => request<CompareResponse>('/api/compare', { query: { a, b } }),
    multi: (runs: number[]) => request<CompareMultiResponse>('/api/compare/multi', { query: { runs: runs.join(',') } }),
  },

  gatePolicies: {
    list: () => request<GatePolicy[]>('/api/gate-policies'),
    defaults: () => request<GatePolicyDefaults>('/api/gate-policies/defaults'),
    create: (body: Record<string, unknown>) => request<GatePolicy>('/api/gate-policies', { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      request<GatePolicy>(`/api/gate-policies/${id}`, { method: 'PUT', body }),
    remove: (id: number) => request<void>(`/api/gate-policies/${id}`, { method: 'DELETE' }),
    evaluate: (id: number, body: { candidate_run_id: number; baseline_run_id?: number | null }) =>
      request<GateEvaluation>(`/api/gate-policies/${id}/evaluate`, { method: 'POST', body }),
  },

  gateEvaluations: {
    list: (query?: { policy_id?: number; candidate_run_id?: number }) =>
      request<GateEvaluation[]>('/api/gate-evaluations', { query }),
  },

  drift: {
    compare: (baseline: number, candidate: number) =>
      request<DriftReport>('/api/drift', { query: { baseline_run: baseline, candidate_run: candidate } }),
  },

  providers: {
    presets: () => request<ProviderPresets>('/api/providers/presets'),
    list: () => request<Provider[]>('/api/providers'),
    create: (body: Record<string, unknown>) => request<Provider>('/api/providers', { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      request<Provider>(`/api/providers/${id}`, { method: 'PUT', body }),
    remove: (id: number) => request<void>(`/api/providers/${id}`, { method: 'DELETE' }),
    test: (id: number) => request<ProviderTestResult>(`/api/providers/${id}/test`, { method: 'POST' }),
    models: (id: number) => request<{ models: ProviderModel[]; count: number }>(`/api/providers/${id}/models`),
  },

  judge: {
    rubrics: () => request<JudgeRubrics>('/api/judge/rubrics'),
    run: (body: { provider_id: number; run_id: number; budget_usd: number; dimensions: string[] }) =>
      request<unknown>('/api/judge', { method: 'POST', body }),
    results: (runId: number) => request<unknown[]>(`/api/runs/${runId}/judge-results`),
    review: (id: number, verdict: 'agree' | 'disagree') =>
      request<unknown>(`/api/judge-results/${id}/review`, { method: 'POST', body: { verdict } }),
  },

  metrics: {
    catalogue: () => request<MetricCatalogue>('/api/metrics/catalogue'),
  },

  system: {
    get: () => request<SystemInfo>('/api/system'),
  },

  alerts: {
    list: (status?: string) => request<Alert[]>('/api/alerts', { query: { status } }),
    acknowledge: (id: number) => request<Alert>(`/api/alerts/${id}/acknowledge`, { method: 'POST' }),
  },

  scheduledJobs: {
    list: () => request<ScheduledJob[]>('/api/scheduled-jobs'),
    create: (body: Record<string, unknown>) => request<ScheduledJob>('/api/scheduled-jobs', { method: 'POST', body }),
    remove: (id: number) => request<void>(`/api/scheduled-jobs/${id}`, { method: 'DELETE' }),
  },

  traces: {
    list: (projectId?: number) => request<unknown[]>('/api/traces', { query: { project_id: projectId } }),
  },
}

export type Api = typeof api
export { ApiError }
