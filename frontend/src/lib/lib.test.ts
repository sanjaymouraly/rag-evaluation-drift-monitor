import { describe, expect, it } from 'vitest'
import {
  NO_VALUE,
  formatCost,
  formatDuration,
  formatMetricValue,
  formatNumber,
  formatPercent,
  isNoEvidence,
  metricLabel,
} from './format'
import {
  checkStatusBadge,
  citationOutcomeBadge,
  deltaTone,
  deltaToneClass,
  isHigherBetter,
  metricKindTone,
  psiBand,
  psiInterpretation,
  runStatusBadge,
  severityBadge,
  verdictBadge,
} from './status'
import { ApiError, errorMessage, extractErrorDetail, formatValidationIssue } from './errors'
import { downloadBlob, exportFileName } from './download'
import { flattenConfig, parseJson, parseJsonObject, stringifyJson } from './json'
import { buildQuery } from '../api'
import { pickComparablePair } from './runs'
import type { Run } from '../types'

describe('metric formatting', () => {
  it('renders an em dash for a null metric value', () => {
    const result = formatMetricValue({ value: null, n: 3, kind: 'deterministic' })
    expect(result.text).toBe(NO_VALUE)
    expect(result.hasEvidence).toBe(false)
    expect(result.hint).toBe('not computed')
  })

  it('flags a metric computed over zero samples as no evidence', () => {
    const aggregate = { value: 0, n: 0, kind: 'reference_based' as const }
    expect(isNoEvidence(aggregate)).toBe(true)
    const result = formatMetricValue(aggregate)
    expect(result.text).toBe(NO_VALUE)
    expect(result.hint).toBe('no evidence')
    expect(result.hasEvidence).toBe(false)
  })

  it('formats a real value with the requested precision', () => {
    const result = formatMetricValue({ value: 0.87654, n: 12, kind: 'heuristic' }, 2)
    expect(result.text).toBe('0.88')
    expect(result.hasEvidence).toBe(true)
    expect(result.hint).toBeUndefined()
  })

  it('formats numbers, percentages, costs and durations', () => {
    expect(formatNumber(1.23456, 2)).toBe('1.23')
    expect(formatNumber(null)).toBe(NO_VALUE)
    expect(formatPercent(0.5)).toBe('50.0%')
    expect(formatCost(0)).toBe('$0.00')
    expect(formatCost(1.5)).toBe('$1.50')
    expect(formatCost(0.0004)).toBe('$0.0004')
    expect(formatDuration(250)).toBe('250 ms')
    expect(formatDuration(2500)).toBe('2.50 s')
  })

  it('builds readable metric labels', () => {
    expect(metricLabel('recall_at_5')).toBe('Recall@5')
    expect(metricLabel('token_f1')).toBe('Token F1')
    expect(metricLabel('faithfulness')).toBe('Faithfulness')
  })
})

describe('delta colouring', () => {
  it('marks a positive delta as an improvement for higher-is-better metrics', () => {
    expect(deltaTone(0.12)).toBe('up')
    expect(deltaToneClass(deltaTone(0.12))).toBe('delta-up')
  })

  it('inverts the meaning for lower-is-better metrics', () => {
    expect(deltaTone(-0.4, isHigherBetter('estimated_cost_usd'))).toBe('up')
    expect(deltaTone(0.4, isHigherBetter('estimated_cost_usd'))).toBe('down')
    expect(isHigherBetter('estimated_cost_usd')).toBe(false)
    expect(isHigherBetter('recall_at_5')).toBe(true)
  })

  it('treats tiny and missing deltas as flat or unknown', () => {
    expect(deltaTone(0)).toBe('flat')
    expect(deltaTone(1e-12)).toBe('flat')
    expect(deltaTone(null)).toBe('unknown')
    expect(deltaToneClass('unknown')).toBe('delta-unknown')
  })
})

describe('PSI interpretation', () => {
  it('bands population stability index values', () => {
    expect(psiBand(0.05)).toBe('none')
    expect(psiBand(0.15)).toBe('moderate')
    expect(psiBand(0.9)).toBe('large')
    expect(psiBand(null)).toBe('unknown')
  })

  it('maps a PSI value to an interpretation label and tone', () => {
    expect(psiInterpretation(0.02).label).toBe('No significant shift')
    expect(psiInterpretation(0.02).tone).toBe('success')
    expect(psiInterpretation(0.2).tone).toBe('warning')
    expect(psiInterpretation(2.9).tone).toBe('danger')
    expect(psiInterpretation(null).label).toBe('Not computed')
  })
})

describe('status badge mapping', () => {
  it('maps run statuses to badges', () => {
    expect(runStatusBadge('completed')).toEqual({ label: 'Completed', tone: 'success' })
    expect(runStatusBadge('failed').tone).toBe('danger')
    expect(runStatusBadge('cancelled').tone).toBe('warning')
    expect(runStatusBadge('running').tone).toBe('info')
    expect(runStatusBadge('weird').tone).toBe('muted')
  })

  it('maps gate verdicts and check statuses', () => {
    expect(verdictBadge('PASS').tone).toBe('success')
    expect(verdictBadge('FAIL').tone).toBe('danger')
    expect(verdictBadge('INCONCLUSIVE').tone).toBe('warning')
    expect(checkStatusBadge('PASS').label).toBe('Pass')
    expect(checkStatusBadge('INCONCLUSIVE').tone).toBe('warning')
  })

  it('maps citation outcomes and severities', () => {
    expect(citationOutcomeBadge('supported').tone).toBe('success')
    expect(citationOutcomeBadge('unsupported').tone).toBe('danger')
    expect(citationOutcomeBadge('irrelevant').tone).toBe('warning')
    expect(citationOutcomeBadge('structural_invalid').tone).toBe('danger')
    expect(severityBadge('hard').tone).toBe('danger')
    expect(severityBadge('warn').tone).toBe('warning')
    expect(metricKindTone('deterministic')).toBe('success')
    expect(metricKindTone('heuristic')).toBe('warning')
  })
})

describe('api error extraction', () => {
  it('reads the FastAPI detail string', () => {
    expect(extractErrorDetail({ detail: 'Dataset not found' })).toBe('Dataset not found')
  })

  it('joins validation issue lists into one message', () => {
    const payload = {
      detail: [
        { loc: ['body', 'name'], msg: 'Field required' },
        { loc: ['body', 'config'], msg: 'not a valid object' },
      ],
    }
    expect(extractErrorDetail(payload)).toBe('name: Field required; config: not a valid object')
    expect(formatValidationIssue({ loc: ['body', 'name'], msg: 'Field required' })).toBe('name: Field required')
  })

  it('returns null when there is no usable detail', () => {
    expect(extractErrorDetail(null)).toBeNull()
    expect(extractErrorDetail({})).toBeNull()
    expect(extractErrorDetail({ detail: '   ' })).toBeNull()
  })

  it('produces a readable message for ApiError and plain errors', () => {
    const error = new ApiError(404, 'Run not found')
    expect(errorMessage(error)).toBe('Run not found')
    expect(errorMessage(new Error('boom'))).toBe('boom')
    expect(errorMessage('nope')).toBe('nope')
    expect(errorMessage(null, 'fallback')).toBe('fallback')
  })
})

describe('file download helper', () => {
  it('builds a safe export file name', () => {
    expect(exportFileName('run 12/report', 'md')).toBe('run-12-report.md')
    expect(exportFileName('run-1', 'jsonl')).toBe('run-1.jsonl')
    expect(exportFileName('run-1', 'ci')).toBe('run-1.json')
  })

  it('returns false when the environment cannot create object URLs', () => {
    const original = URL.createObjectURL
    // @ts-expect-error deliberately removing the API for this assertion
    URL.createObjectURL = undefined
    try {
      expect(downloadBlob(new Blob(['x']), { fileName: 'a.txt' })).toBe(false)
    } finally {
      URL.createObjectURL = original
    }
  })
})

describe('json helpers', () => {
  it('parses a valid object and rejects invalid JSON', () => {
    const ok = parseJsonObject('{"a": 1}')
    expect(ok.ok).toBe(true)
    expect(ok.object).toEqual({ a: 1 })

    const bad = parseJsonObject('{a: 1}')
    expect(bad.ok).toBe(false)
    expect(bad.error).toContain('Invalid JSON')

    const notObject = parseJsonObject('[1,2]')
    expect(notObject.ok).toBe(false)
    expect(notObject.error).toContain('must be a JSON object')
  })

  it('rejects an empty document', () => {
    const result = parseJson('   ')
    expect(result.ok).toBe(false)
    expect(result.error).toBe('The value is empty.')
  })

  it('flattens nested configuration into dotted keys', () => {
    const rows = flattenConfig({ retriever: 'bm25', adapter: { type: 'builtin' }, prices: [1, 2] })
    expect(rows).toEqual([
      { key: 'retriever', value: 'bm25' },
      { key: 'adapter.type', value: 'builtin' },
      { key: 'prices[0]', value: '1' },
      { key: 'prices[1]', value: '2' },
    ])
  })

  it('stringifies config safely', () => {
    expect(stringifyJson({ a: 1 })).toContain('"a": 1')
    expect(stringifyJson(undefined)).toBe('{}')
  })
})

describe('query string building', () => {
  it('skips empty values and encodes the rest', () => {
    expect(buildQuery({ a: 1, b: '', c: undefined, d: 'x' })).toBe('?a=1&d=x')
    expect(buildQuery()).toBe('')
  })
})

describe('run pair selection', () => {
  const makeRun = (id: number, datasetId: number) => ({ id, dataset_id: datasetId }) as Run

  it('prefers two runs that share the same dataset', () => {
    const pair = pickComparablePair([makeRun(1, 7), makeRun(2, 9), makeRun(3, 7)])
    expect(pair).toEqual({ a: 1, b: 3 })
  })

  it('falls back to the first two runs when no dataset is shared', () => {
    const pair = pickComparablePair([makeRun(4, 1), makeRun(5, 2)])
    expect(pair).toEqual({ a: 4, b: 5 })
  })

  it('handles an empty or single-run list', () => {
    expect(pickComparablePair([])).toEqual({ a: null, b: null })
    expect(pickComparablePair([makeRun(6, 1)])).toEqual({ a: 6, b: null })
  })
})
