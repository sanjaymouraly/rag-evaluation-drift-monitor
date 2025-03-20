import { Field, Notice } from './ui'
import type { GatePolicy, GateRule, GateRuleType } from '../types'

export interface RuleDraft extends Omit<GateRule, 'scope'> {
  scopeCategory: string
  scopeCohort: string
}

export interface PolicyDraft {
  project_id: number
  name: string
  description: string
  baseline_run_id: number | null
  min_samples: number
  rules: RuleDraft[]
}

export const RULE_TYPES: Array<{ value: GateRuleType; label: string; hint: string }> = [
  { value: 'min', label: 'min', hint: 'The value must be at least the threshold.' },
  { value: 'max', label: 'max', hint: 'The value must be at most the threshold.' },
  { value: 'max_drop', label: 'max_drop', hint: 'The value must not drop more than the threshold vs the baseline.' },
  { value: 'max_increase', label: 'max_increase', hint: 'The value must not increase more than the threshold vs the baseline.' },
  { value: 'min_delta', label: 'min_delta', hint: 'The value must improve by at least the threshold vs the baseline.' },
]

export function ruleToDraft(rule: GateRule): RuleDraft {
  return {
    metric: rule.metric,
    type: rule.type,
    threshold: rule.threshold,
    severity: rule.severity,
    tolerance: rule.tolerance ?? null,
    label: rule.label ?? '',
    scopeCategory: rule.scope?.category ?? '',
    scopeCohort: rule.scope?.cohort ?? '',
  }
}

export function policyToDraft(policy: GatePolicy): PolicyDraft {
  return {
    project_id: policy.project_id,
    name: policy.name,
    description: policy.description,
    baseline_run_id: policy.baseline_run_id,
    min_samples: policy.min_samples,
    rules: (policy.rules ?? []).map(ruleToDraft),
  }
}

export function draftToPolicy(draft: PolicyDraft) {
  return {
    project_id: draft.project_id,
    name: draft.name.trim(),
    description: draft.description,
    baseline_run_id: draft.baseline_run_id,
    min_samples: draft.min_samples,
    rules: draft.rules.map((rule) => ({
      metric: rule.metric,
      type: rule.type,
      threshold: Number(rule.threshold),
      severity: rule.severity,
      tolerance: rule.tolerance === null || rule.tolerance === undefined ? null : Number(rule.tolerance),
      label: rule.label || undefined,
      scope: {
        ...(rule.scopeCategory ? { category: rule.scopeCategory } : {}),
        ...(rule.scopeCohort ? { cohort: rule.scopeCohort } : {}),
      },
    })),
  }
}

export default function PolicyEditor({
  draft,
  onChange,
  metricOptions,
  projectOptions,
  runOptions,
  idPrefix,
}: {
  draft: PolicyDraft
  onChange: (next: PolicyDraft) => void
  metricOptions: string[]
  projectOptions: Array<{ id: number; name: string }>
  runOptions: Array<{ id: number; label: string }>
  idPrefix: string
}) {
  function updateRule(index: number, patch: Partial<RuleDraft>) {
    const rules = draft.rules.map((rule, position) => (position === index ? { ...rule, ...patch } : rule))
    onChange({ ...draft, rules })
  }

  function removeRule(index: number) {
    onChange({ ...draft, rules: draft.rules.filter((_, position) => position !== index) })
  }

  function addRule() {
    onChange({
      ...draft,
      rules: [
        ...draft.rules,
        {
          metric: metricOptions[0] ?? 'recall_at_5',
          type: 'min',
          threshold: 0.8,
          severity: 'hard',
          tolerance: null,
          label: '',
          scopeCategory: '',
          scopeCohort: '',
        },
      ],
    })
  }

  return (
    <div>
      <div className="grid grid-2">
        <Field label="Project" htmlFor={`${idPrefix}-project`} required>
          <select
            id={`${idPrefix}-project`}
            value={draft.project_id}
            onChange={(event) => onChange({ ...draft, project_id: Number(event.target.value) })}
          >
            {projectOptions.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Policy name" htmlFor={`${idPrefix}-name`} required>
          <input
            id={`${idPrefix}-name`}
            value={draft.name}
            onChange={(event) => onChange({ ...draft, name: event.target.value })}
          />
        </Field>
        <Field label="Baseline run" htmlFor={`${idPrefix}-baseline`} hint="The approved baseline used for relative rules.">
          <select
            id={`${idPrefix}-baseline`}
            value={draft.baseline_run_id ?? ''}
            onChange={(event) =>
              onChange({ ...draft, baseline_run_id: event.target.value ? Number(event.target.value) : null })
            }
          >
            <option value="">No baseline</option>
            {runOptions.map((run) => (
              <option key={run.id} value={run.id}>
                {run.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Minimum samples" htmlFor={`${idPrefix}-min-samples`} required hint="Below this the verdict is INCONCLUSIVE.">
          <input
            id={`${idPrefix}-min-samples`}
            type="number"
            min="1"
            value={draft.min_samples}
            onChange={(event) => onChange({ ...draft, min_samples: Number(event.target.value) })}
          />
        </Field>
      </div>

      <Field label="Description" htmlFor={`${idPrefix}-description`}>
        <textarea
          id={`${idPrefix}-description`}
          value={draft.description}
          onChange={(event) => onChange({ ...draft, description: event.target.value })}
          style={{ minHeight: 70, fontFamily: 'var(--font-sans)' }}
        />
      </Field>

      <fieldset>
        <legend>Rules</legend>
        {draft.rules.length === 0 && (
          <Notice tone="info">A policy without rules cannot produce a verdict. Add at least one rule.</Notice>
        )}
        {draft.rules.map((rule, index) => (
          <div className="rule-row" key={`rule-${index}`}>
            <div className="grid grid-3">
              <Field label={`Metric ${index + 1}`} htmlFor={`${idPrefix}-rule-metric-${index}`}>
                <select
                  id={`${idPrefix}-rule-metric-${index}`}
                  value={rule.metric}
                  onChange={(event) => updateRule(index, { metric: event.target.value })}
                >
                  {metricOptions.map((metric) => (
                    <option key={metric} value={metric}>
                      {metric}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Rule type" htmlFor={`${idPrefix}-rule-type-${index}`}>
                <select
                  id={`${idPrefix}-rule-type-${index}`}
                  value={rule.type}
                  onChange={(event) => updateRule(index, { type: event.target.value })}
                >
                  {RULE_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Threshold" htmlFor={`${idPrefix}-rule-threshold-${index}`}>
                <input
                  id={`${idPrefix}-rule-threshold-${index}`}
                  type="number"
                  step="0.01"
                  value={rule.threshold}
                  onChange={(event) => updateRule(index, { threshold: Number(event.target.value) })}
                />
              </Field>
              <Field label="Severity" htmlFor={`${idPrefix}-rule-severity-${index}`}>
                <select
                  id={`${idPrefix}-rule-severity-${index}`}
                  value={rule.severity}
                  onChange={(event) => updateRule(index, { severity: event.target.value })}
                >
                  <option value="hard">hard</option>
                  <option value="warn">warn</option>
                </select>
              </Field>
              <Field label="Tolerance" htmlFor={`${idPrefix}-rule-tolerance-${index}`} hint="Optional slack around the threshold.">
                <input
                  id={`${idPrefix}-rule-tolerance-${index}`}
                  type="number"
                  step="0.01"
                  value={rule.tolerance ?? ''}
                  onChange={(event) =>
                    updateRule(index, { tolerance: event.target.value === '' ? null : Number(event.target.value) })
                  }
                />
              </Field>
              <Field label="Scope category" htmlFor={`${idPrefix}-rule-category-${index}`} hint="Optional: only this category.">
                <input
                  id={`${idPrefix}-rule-category-${index}`}
                  value={rule.scopeCategory}
                  onChange={(event) => updateRule(index, { scopeCategory: event.target.value })}
                />
              </Field>
              <Field label="Scope cohort" htmlFor={`${idPrefix}-rule-cohort-${index}`} hint="Optional: only this cohort.">
                <input
                  id={`${idPrefix}-rule-cohort-${index}`}
                  value={rule.scopeCohort}
                  onChange={(event) => updateRule(index, { scopeCohort: event.target.value })}
                />
              </Field>
              <Field label="Label" htmlFor={`${idPrefix}-rule-label-${index}`} hint="Shown in the verdict summary.">
                <input
                  id={`${idPrefix}-rule-label-${index}`}
                  value={rule.label ?? ''}
                  onChange={(event) => updateRule(index, { label: event.target.value })}
                />
              </Field>
            </div>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => removeRule(index)}
              aria-label={`Remove rule ${index + 1}`}
            >
              Remove rule
            </button>
          </div>
        ))}
        <button type="button" className="btn btn-secondary" onClick={addRule}>
          Add rule
        </button>
      </fieldset>
    </div>
  )
}
