/**
 * Error helpers shared by the API client and the UI.
 *
 * FastAPI reports failures as `{"detail": "..."}`. `detail` may be a string or a
 * list of validation error objects, so the extraction has to handle both.
 */

export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly payload: unknown

  constructor(status: number, detail: string, payload?: unknown) {
    super(detail || `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.payload = payload
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Turn a FastAPI validation error object into a readable single line. */
export function formatValidationIssue(issue: unknown): string {
  if (!isRecord(issue)) return String(issue)
  const loc = Array.isArray(issue.loc) ? issue.loc.filter((p) => p !== 'body').join('.') : ''
  const msg = typeof issue.msg === 'string' ? issue.msg : JSON.stringify(issue)
  return loc ? `${loc}: ${msg}` : msg
}

/**
 * Extract a human readable message from a JSON error body.
 * Returns null when the body carries no usable detail.
 */
export function extractErrorDetail(payload: unknown): string | null {
  if (payload === null || payload === undefined) return null
  if (typeof payload === 'string') {
    const trimmed = payload.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (Array.isArray(payload)) {
    const parts = payload.map(formatValidationIssue).filter(Boolean)
    return parts.length > 0 ? parts.join('; ') : null
  }
  if (isRecord(payload)) {
    const detail = payload.detail
    if (typeof detail === 'string') return detail.trim() ? detail : null
    if (Array.isArray(detail)) {
      const parts = detail.map(formatValidationIssue).filter(Boolean)
      if (parts.length > 0) return parts.join('; ')
    }
    if (detail !== undefined && detail !== null) return JSON.stringify(detail)
    if (typeof payload.message === 'string' && payload.message.trim()) return payload.message
  }
  return null
}

/** Best-effort message for anything that was thrown (including network failures). */
export function errorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (error instanceof ApiError) return error.detail
  if (error instanceof Error) return error.message || fallback
  if (typeof error === 'string' && error.trim()) return error
  const detail = extractErrorDetail(error)
  return detail ?? fallback
}
