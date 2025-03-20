import type { Run } from '../types'

/**
 * Pick a sensible default pair of runs to compare: two runs that share the
 * same dataset, so the comparison is paired and meaningful.
 */
export function pickComparablePair(runs: Run[]): { a: number | null; b: number | null } {
  if (runs.length === 0) return { a: null, b: null }
  if (runs.length === 1) return { a: runs[0].id, b: null }

  for (let i = 0; i < runs.length; i += 1) {
    for (let j = i + 1; j < runs.length; j += 1) {
      if (runs[i].dataset_id === runs[j].dataset_id) {
        return { a: runs[i].id, b: runs[j].id }
      }
    }
  }
  return { a: runs[0].id, b: runs[1].id }
}

/** Human label for a run used in dropdowns. */
export function runOptionLabel(run: Run): string {
  return `#${run.id} · ${run.app_name} ${run.app_version} · ${run.dataset_name}`
}
