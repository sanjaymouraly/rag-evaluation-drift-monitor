/**
 * Client-side download helpers.
 */

/** Turn an export format into a file name that the browser can save. */
export function exportFileName(base: string, format: string, extension?: string): string {
  const safeBase = (base || 'export').replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/-+/g, '-')
  const ext = extension ?? (format === 'jsonl' ? 'jsonl' : format === 'md' ? 'md' : format === 'ci' ? 'json' : format)
  return `${safeBase}.${ext}`
}

export interface DownloadOptions {
  fileName: string
  mimeType?: string
}

/**
 * Trigger a browser download for a blob. Returns false when the environment
 * cannot create object URLs (e.g. jsdom) so callers can degrade gracefully.
 */
export function downloadBlob(blob: Blob, options: DownloadOptions): boolean {
  if (typeof document === 'undefined' || typeof URL === 'undefined' || !URL.createObjectURL) return false
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = options.fileName
  link.rel = 'noopener'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  // Revoke on the next tick so Safari has time to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return true
}

/** Download plain text content (e.g. a markdown report). */
export function downloadText(text: string, options: DownloadOptions): boolean {
  return downloadBlob(new Blob([text], { type: options.mimeType ?? 'text/plain;charset=utf-8' }), options)
}

/** Download a JSON payload with stable key ordering. */
export function downloadJson(data: unknown, options: DownloadOptions): boolean {
  return downloadText(JSON.stringify(data, null, 2), { ...options, mimeType: 'application/json' })
}
