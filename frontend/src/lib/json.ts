/**
 * JSON helpers for the config textarea and rule builder.
 */

export interface JsonParseResult {
  ok: boolean
  value: unknown
  error: string | null
}

/** Parse a JSON document, returning a friendly error message on failure. */
export function parseJson(text: string): JsonParseResult {
  const trimmed = text.trim()
  if (!trimmed) return { ok: false, value: null, error: 'The value is empty.' }
  try {
    return { ok: true, value: JSON.parse(trimmed), error: null }
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : String(cause)
    return { ok: false, value: null, error: `Invalid JSON: ${message}` }
  }
}

/** Parse JSON that must be a plain object (used for app configuration). */
export function parseJsonObject(text: string): JsonParseResult & { object: Record<string, unknown> | null } {
  const parsed = parseJson(text)
  if (!parsed.ok) return { ...parsed, object: null }
  if (typeof parsed.value !== 'object' || parsed.value === null || Array.isArray(parsed.value)) {
    return { ok: false, value: parsed.value, error: 'The configuration must be a JSON object.', object: null }
  }
  return { ok: true, value: parsed.value, error: null, object: parsed.value as Record<string, unknown> }
}

/** Pretty print a value for the config textarea. */
export function stringifyJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}

/** Flatten a nested object into dotted key/value rows for a readable table. */
export function flattenConfig(
  value: unknown,
  prefix = '',
): Array<{ key: string; value: string }> {
  if (value === null || value === undefined) return []
  if (typeof value !== 'object') return [{ key: prefix || 'value', value: String(value) }]
  if (Array.isArray(value)) {
    if (value.length === 0) return [{ key: prefix, value: '[]' }]
    return value.map((entry, index) => flattenConfig(entry, `${prefix}[${index}]`)).flat()
  }
  const entries = Object.entries(value as Record<string, unknown>)
  if (entries.length === 0) return [{ key: prefix || 'config', value: '{}' }]
  return entries.flatMap(([key, entry]) => flattenConfig(entry, prefix ? `${prefix}.${key}` : key))
}
