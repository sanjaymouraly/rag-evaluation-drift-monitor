import { useMemo, useState } from 'react'
import { Field } from './ui'
import { parseJson, stringifyJson } from '../lib/json'
import type { DatasetItem } from '../types'

export interface ItemDraft {
  question: string
  reference_answer: string
  aliases: string
  relevant_doc_ids: string
  expected_citations: string
  category: string
  difficulty: string
  answerable: boolean
  language: string
  topic: string
  cohorts: string
  notes: string
}

export function emptyItemDraft(): ItemDraft {
  return {
    question: '',
    reference_answer: '',
    aliases: '',
    relevant_doc_ids: '',
    expected_citations: '[]',
    category: 'factual',
    difficulty: 'medium',
    answerable: true,
    language: 'en',
    topic: '',
    cohorts: '',
    notes: '',
  }
}

export function draftFromItem(item: DatasetItem): ItemDraft {
  return {
    question: item.question,
    reference_answer: item.reference_answer,
    aliases: (item.aliases ?? []).join(', '),
    relevant_doc_ids: (item.relevant_doc_ids ?? []).join(', '),
    expected_citations: stringifyJson(item.expected_citations ?? []),
    category: item.category,
    difficulty: item.difficulty,
    answerable: item.answerable,
    language: item.language,
    topic: item.topic,
    cohorts: (item.cohorts ?? []).join(', '),
    notes: item.notes,
  }
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
}

export interface ItemPayload {
  [key: string]: unknown
  question: string
  reference_answer: string
  aliases: string[]
  relevant_doc_ids: string[]
  expected_citations: Array<Record<string, unknown>>
  category: string
  difficulty: string
  answerable: boolean
  language: string
  topic: string
  cohorts: string[]
  notes: string
}

export function itemPayloadFromDraft(draft: ItemDraft): { payload: ItemPayload; error: string | null } {
  if (!draft.question.trim()) return { payload: {} as ItemPayload, error: 'The question is required.' }
  const parsed = parseJson(draft.expected_citations)
  if (!parsed.ok) return { payload: {} as ItemPayload, error: parsed.error }
  if (!Array.isArray(parsed.value)) {
    return { payload: {} as ItemPayload, error: 'Expected citations must be a JSON array.' }
  }
  return {
    payload: {
      question: draft.question.trim(),
      reference_answer: draft.reference_answer,
      aliases: splitList(draft.aliases),
      relevant_doc_ids: splitList(draft.relevant_doc_ids),
      expected_citations: parsed.value as Array<Record<string, unknown>>,
      category: draft.category || 'factual',
      difficulty: draft.difficulty || 'medium',
      answerable: draft.answerable,
      language: draft.language || 'en',
      topic: draft.topic,
      cohorts: splitList(draft.cohorts),
      notes: draft.notes,
    },
    error: null,
  }
}

export default function DatasetItemEditor({
  draft,
  onChange,
  idPrefix,
}: {
  draft: ItemDraft
  onChange: (next: ItemDraft) => void
  idPrefix: string
}) {
  const [jsonError, setJsonError] = useState<string | null>(null)
  const categories = ['factual', 'multi_hop', 'unanswerable', 'missing_context', 'adversarial', 'ambiguous', 'other']
  const difficulties = ['easy', 'medium', 'hard']
  const parsedCitations = useMemo(() => parseJson(draft.expected_citations), [draft.expected_citations])

  function update<K extends keyof ItemDraft>(key: K, value: ItemDraft[K]) {
    onChange({ ...draft, [key]: value })
  }

  function handleCitations(value: string) {
    update('expected_citations', value)
    setJsonError(parseJson(value).ok ? null : parseJson(value).error)
  }

  return (
    <div>
      <Field label="Question" htmlFor={`${idPrefix}-question`} required>
        <textarea
          id={`${idPrefix}-question`}
          value={draft.question}
          onChange={(event) => update('question', event.target.value)}
          style={{ minHeight: 70, fontFamily: 'var(--font-sans)' }}
        />
      </Field>

      <Field label="Reference answer" htmlFor={`${idPrefix}-answer`}>
        <textarea
          id={`${idPrefix}-answer`}
          value={draft.reference_answer}
          onChange={(event) => update('reference_answer', event.target.value)}
          style={{ minHeight: 70, fontFamily: 'var(--font-sans)' }}
        />
      </Field>

      <div className="grid grid-2">
        <Field label="Aliases" htmlFor={`${idPrefix}-aliases`} hint="Comma separated alternative answers.">
          <input
            id={`${idPrefix}-aliases`}
            value={draft.aliases}
            onChange={(event) => update('aliases', event.target.value)}
          />
        </Field>
        <Field label="Relevant document ids" htmlFor={`${idPrefix}-relevant`} hint="Comma separated doc ids.">
          <input
            id={`${idPrefix}-relevant`}
            value={draft.relevant_doc_ids}
            onChange={(event) => update('relevant_doc_ids', event.target.value)}
          />
        </Field>
        <Field label="Category" htmlFor={`${idPrefix}-category`}>
          <select
            id={`${idPrefix}-category`}
            value={draft.category}
            onChange={(event) => update('category', event.target.value)}
          >
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Difficulty" htmlFor={`${idPrefix}-difficulty`}>
          <select
            id={`${idPrefix}-difficulty`}
            value={draft.difficulty}
            onChange={(event) => update('difficulty', event.target.value)}
          >
            {difficulties.map((difficulty) => (
              <option key={difficulty} value={difficulty}>
                {difficulty}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Language" htmlFor={`${idPrefix}-language`}>
          <input
            id={`${idPrefix}-language`}
            value={draft.language}
            onChange={(event) => update('language', event.target.value)}
          />
        </Field>
        <Field label="Topic" htmlFor={`${idPrefix}-topic`}>
          <input id={`${idPrefix}-topic`} value={draft.topic} onChange={(event) => update('topic', event.target.value)} />
        </Field>
      </div>

      <Field label="Cohorts" htmlFor={`${idPrefix}-cohorts`} hint="Comma separated cohort names, e.g. core, biology.">
        <input
          id={`${idPrefix}-cohorts`}
          value={draft.cohorts}
          onChange={(event) => update('cohorts', event.target.value)}
        />
      </Field>

      <Field
        label="Expected citations (JSON array)"
        htmlFor={`${idPrefix}-citations`}
        error={jsonError}
        hint='For example [{"doc_id": "doc_bees"}]'
      >
        <textarea
          id={`${idPrefix}-citations`}
          value={draft.expected_citations}
          onChange={(event) => handleCitations(event.target.value)}
          rows={4}
          spellCheck={false}
        />
      </Field>
      {parsedCitations.ok && Array.isArray(parsedCitations.value) && (
        <p className="text-faint text-small">{parsedCitations.value.length} expected citation(s) parsed.</p>
      )}

      <Field label="Answerable" htmlFor={`${idPrefix}-answerable`}>
        <input
          id={`${idPrefix}-answerable`}
          type="checkbox"
          checked={draft.answerable}
          onChange={(event) => update('answerable', event.target.checked)}
        />
      </Field>

      <Field label="Notes" htmlFor={`${idPrefix}-notes`}>
        <textarea
          id={`${idPrefix}-notes`}
          value={draft.notes}
          onChange={(event) => update('notes', event.target.value)}
          style={{ minHeight: 60, fontFamily: 'var(--font-sans)' }}
        />
      </Field>
    </div>
  )
}
