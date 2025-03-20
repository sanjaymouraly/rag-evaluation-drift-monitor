import { Field } from './ui'
import type { Provider } from '../types'

export interface ProviderDraft {
  name: string
  kind: string
  role: string
  base_url: string
  api_key: string
  model: string
  timeout_s: number
  retries: number
  price_per_1k_input: number
  price_per_1k_output: number
  is_default: boolean
  enabled: boolean
  max_concurrency: number
}

export function emptyProviderDraft(): ProviderDraft {
  return {
    name: '',
    kind: 'openai',
    role: 'judge',
    base_url: '',
    api_key: '',
    model: '',
    timeout_s: 30,
    retries: 2,
    price_per_1k_input: 0,
    price_per_1k_output: 0,
    is_default: false,
    enabled: true,
    max_concurrency: 4,
  }
}

export function providerToDraft(provider: Provider): ProviderDraft {
  return {
    name: provider.name,
    kind: provider.kind,
    role: provider.role,
    base_url: provider.base_url,
    api_key: '',
    model: provider.model,
    timeout_s: provider.timeout_s,
    retries: provider.retries,
    price_per_1k_input: provider.price_per_1k_input,
    price_per_1k_output: provider.price_per_1k_output,
    is_default: provider.is_default,
    enabled: provider.enabled,
    max_concurrency: provider.max_concurrency,
  }
}

export default function ProviderEditor({
  draft,
  onChange,
  kinds,
  roles,
  idPrefix,
  modelOptions,
}: {
  draft: ProviderDraft
  onChange: (next: ProviderDraft) => void
  kinds: string[]
  roles: string[]
  idPrefix: string
  modelOptions: string[]
}) {
  function update<K extends keyof ProviderDraft>(key: K, value: ProviderDraft[K]) {
    onChange({ ...draft, [key]: value })
  }

  return (
    <div>
      <div className="grid grid-2">
        <Field label="Name" htmlFor={`${idPrefix}-name`} required>
          <input id={`${idPrefix}-name`} value={draft.name} onChange={(event) => update('name', event.target.value)} />
        </Field>
        <Field label="Kind" htmlFor={`${idPrefix}-kind`} required hint="Pick a provider protocol.">
          <select id={`${idPrefix}-kind`} value={draft.kind} onChange={(event) => update('kind', event.target.value)}>
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Role" htmlFor={`${idPrefix}-role`} required>
          <select id={`${idPrefix}-role`} value={draft.role} onChange={(event) => update('role', event.target.value)}>
            {roles.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Base URL" htmlFor={`${idPrefix}-base-url`}>
          <input
            id={`${idPrefix}-base-url`}
            value={draft.base_url}
            placeholder="https://api.openai.com/v1"
            onChange={(event) => update('base_url', event.target.value)}
          />
        </Field>
        <Field
          label="API key"
          htmlFor={`${idPrefix}-api-key`}
          hint="Stored server side and never returned in plain text. Leave blank to keep the existing key."
        >
          <input
            id={`${idPrefix}-api-key`}
            type="password"
            autoComplete="new-password"
            value={draft.api_key}
            onChange={(event) => update('api_key', event.target.value)}
          />
        </Field>
        <Field label="Model" htmlFor={`${idPrefix}-model`}>
          <input
            id={`${idPrefix}-model`}
            list={`${idPrefix}-model-list`}
            value={draft.model}
            onChange={(event) => update('model', event.target.value)}
          />
          <datalist id={`${idPrefix}-model-list`}>
            {modelOptions.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </Field>
        <Field label="Timeout (seconds)" htmlFor={`${idPrefix}-timeout`}>
          <input
            id={`${idPrefix}-timeout`}
            type="number"
            min="1"
            step="1"
            value={draft.timeout_s}
            onChange={(event) => update('timeout_s', Number(event.target.value))}
          />
        </Field>
        <Field label="Retries" htmlFor={`${idPrefix}-retries`}>
          <input
            id={`${idPrefix}-retries`}
            type="number"
            min="0"
            step="1"
            value={draft.retries}
            onChange={(event) => update('retries', Number(event.target.value))}
          />
        </Field>
        <Field label="Price per 1k input tokens" htmlFor={`${idPrefix}-price-in`}>
          <input
            id={`${idPrefix}-price-in`}
            type="number"
            min="0"
            step="0.0001"
            value={draft.price_per_1k_input}
            onChange={(event) => update('price_per_1k_input', Number(event.target.value))}
          />
        </Field>
        <Field label="Price per 1k output tokens" htmlFor={`${idPrefix}-price-out`}>
          <input
            id={`${idPrefix}-price-out`}
            type="number"
            min="0"
            step="0.0001"
            value={draft.price_per_1k_output}
            onChange={(event) => update('price_per_1k_output', Number(event.target.value))}
          />
        </Field>
        <Field label="Max concurrency" htmlFor={`${idPrefix}-concurrency`}>
          <input
            id={`${idPrefix}-concurrency`}
            type="number"
            min="1"
            step="1"
            value={draft.max_concurrency}
            onChange={(event) => update('max_concurrency', Number(event.target.value))}
          />
        </Field>
      </div>

      <div className="row">
        <label htmlFor={`${idPrefix}-enabled`}>
          <input
            id={`${idPrefix}-enabled`}
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => update('enabled', event.target.checked)}
          />{' '}
          Enabled
        </label>
        <label htmlFor={`${idPrefix}-default`}>
          <input
            id={`${idPrefix}-default`}
            type="checkbox"
            checked={draft.is_default}
            onChange={(event) => update('is_default', event.target.checked)}
          />{' '}
          Default provider
        </label>
      </div>
    </div>
  )
}
