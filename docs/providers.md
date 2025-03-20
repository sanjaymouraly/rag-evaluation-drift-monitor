# AI provider setup

Every AI integration is **optional**. The platform's default offline mode is
free, needs no key, makes no network call and produces deterministic metrics.

---

## 1. Offline deterministic mode (free, no key)

*Kind:* `offline` · *Model:* `offline-deterministic` · *Cost:* 0

The offline provider is what makes the "no API key" demo real. The built-in RAG
answers extractively from the retrieved context, so ingestion, retrieval,
answering, citation verification and scoring all run for real — only the
language model is replaced by a deterministic algorithm.

Use it for: CI gates, regression monitoring, and getting a baseline before you
spend anything.

## 2. Provider presets

`GET /api/providers/presets` returns the table below. The dashboard renders it
as cards with a **Use this preset** button that pre-fills the form.

| Preset | Protocol | Default base URL | Key required | Notes |
|---|---|---|---|---|
| `offline` | offline | — | no | free, deterministic, no network |
| `openai` | OpenAI-compatible | `https://api.openai.com/v1` | yes | the OpenAI API |
| `anthropic` | Anthropic Messages | `https://api.anthropic.com` | yes | Claude |
| `openrouter` | OpenAI-compatible | `https://openrouter.ai/api/v1` | yes | many models, one key |
| `ollama` | Ollama | `http://localhost:11434` | no | local, free |
| `custom` | OpenAI-compatible | *(your URL)* | depends | any `/chat/completions` service |
| `azure_openai` | OpenAI-compatible | *(your resource URL)* | yes | Azure deployments |
| `together` | OpenAI-compatible | `https://api.together.xyz/v1` | yes | |
| `groq` | OpenAI-compatible | `https://api.groq.com/openai/v1` | yes | |
| `deepseek` | OpenAI-compatible | `https://api.deepseek.com/v1` | yes | |
| `mistral` | OpenAI-compatible | `https://api.mistral.ai/v1` | yes | |
| `lmstudio` | OpenAI-compatible | `http://localhost:1234/v1` | no | local desktop server |
| `vllm` | OpenAI-compatible | `http://localhost:8000/v1` | no | local serving |

> **A ChatGPT Plus or Pro subscription does not include OpenAI API credits.**
> The OpenAI API is a separate, billed service that requires its own API key
> with billing enabled. The platform never assumes otherwise and never asks
> for a ChatGPT login.

## 3. Creating a provider profile

Through the dashboard: **AI providers → New profile**.

Through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/providers \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "OpenAI — judging",
        "kind": "openai",
        "role": "judge",
        "model": "gpt-6-luna",
        "api_key": "sk-…",
        "price_per_1k_input": 0.0001,
        "price_per_1k_output": 0.0005
      }'
```

Through the SDK:

```python
from rag_monitor_sdk import RAGMonitorClient

client = RAGMonitorClient("http://127.0.0.1:8000")
client.create_provider("OpenAI — judging", kind="openai", role="judge",
                       model="gpt-6-luna", api_key="sk-…")
```

### Configuration fields

| Field | Meaning |
|---|---|
| `kind` | the preset / wire protocol |
| `role` | `generation`, `embedding` or `judge` — the three roles are independent |
| `base_url` | the API root; pre-filled from the preset |
| `api_key` | stored server-side, never returned by the API (only a mask) |
| `model` | the model id — discover it with **Test connection** / **Discover models** |
| `timeout_s` | per-request timeout |
| `retries` | retry count with exponential backoff |
| `price_per_1k_input` / `price_per_1k_output` | USD per 1 000 tokens; used for the cost estimate |
| `max_concurrency` | concurrency cap for the profile |

## 4. Testing the connection

```bash
curl -X POST http://127.0.0.1:8000/api/providers/1/test
```

```json
{ "ok": true, "detail": "Connected. 12 model(s) visible.", "models": ["gpt-6-luna", "…"] }
```

A failure is reported honestly:

```json
{ "ok": false, "detail": "connection failed: HTTP 401: {\"error\":…}", "models": [] }
```

**Model discovery** uses the provider's own documented endpoint:

| Provider | Endpoint |
|---|---|
| OpenAI / OpenRouter / custom | `GET {base_url}/models` |
| Anthropic | `GET {base_url}/v1/models` |
| Ollama | `GET {base_url}/api/tags` |

If discovery is not available, pick a model id from the provider's own
documentation — the platform never invents model identifiers.

## 5. Roles

Three independent roles, each with its own profile:

| Role | Used for |
|---|---|
| `generation` | answering the questions in the RAG under test |
| `embedding` | the `semantic_similarity` metric |
| `judge` | optional LLM-as-a-judge evaluation |

## 6. Local models with Ollama

Ollama runs entirely on your machine — free, private, no key.

```bash
# install: https://ollama.com/download
ollama serve
ollama pull gemma3:270m
ollama list
```

Then create a profile:

```json
{ "name": "Ollama local", "kind": "ollama", "role": "judge",
  "base_url": "http://localhost:11434", "model": "gemma3:270m" }
```

`POST /api/providers/{id}/test` verifies the connection and lists the pulled
models. If Ollama is not running, the test fails with a clear
`cannot reach Ollama at …` message.

> A small local model such as `gemma3:270m` is useful for smoke tests and for
> privacy-sensitive workloads, but it is far weaker than a hosted model. Judge
> scores from a small model are noisier — always read them as opinion signals.

## 7. Anthropic Claude

```json
{ "name": "Anthropic — judging", "kind": "anthropic", "role": "judge",
  "base_url": "https://api.anthropic.com", "model": "claude-haiku-5-5",
  "api_key": "sk-ant-…" }
```

The adapter calls `POST /v1/messages` with the standard `x-api-key` and
`anthropic-version` headers and reads the `usage` block, so token counts are
exact.

## 8. OpenRouter

```json
{ "name": "OpenRouter", "kind": "openrouter", "role": "judge",
  "base_url": "https://openrouter.ai/api/v1", "model": "<id from /models>",
  "api_key": "sk-or-…" }
```

OpenRouter speaks the OpenAI protocol, so the same adapter is used. Prices
differ per model — set `price_per_1k_input` / `price_per_1k_output` explicitly
for the model you pick, or the platform reports the cost as unknown.

## 9. Custom OpenAI-compatible endpoints

Any service that exposes `POST {base_url}/chat/completions` with the OpenAI
request/response shape works: vLLM, LM Studio, llama.cpp's server, LiteLLM,
Text Generation Inference, TGI, and the hosted services above.

```json
{ "name": "Internal gateway", "kind": "custom", "role": "generation",
  "base_url": "https://llm.internal.example/v1", "model": "our-model",
  "api_key": "…", "api_style": "chat_completions" }
```

`api_style` may be `auto` (default — the Responses API is tried first and the
adapter falls back to Chat Completions), `responses` or `chat_completions`.

## 10. Cost control

| Control | Where |
|---|---|
| Per-run hard spend limit | `RQM_MAX_RUN_COST_USD` or the app config `max_run_cost_usd` |
| Per-judge budget | `POST /api/judge` → `budget_usd` (the judge stops when it is reached) |
| Global ceiling | `RQM_HARD_COST_LIMIT_USD` |
| Default judge budget | `RQM_DEFAULT_BUDGET_USD` |
| Reference prices | `GET /api/providers/pricing?model=…` |

The budget guard is *hard*: when the limit is reached the run stops and is
marked `failed` with a `Budget stop: …` message. It never silently overshoots.

The built-in reference price table (per 1M tokens) is:

| Model | Input | Output |
|---|---|---|
| `gpt-6-astra` | 10.00 | 50.00 |
| `gpt-6.1-sol` | 2.00 | 10.00 |
| `gpt-6-luna` | 0.10 | 0.50 |
| `claude-opus-5-5` | 4.00 | 20.00 |
| `claude-sonnet-5-5` | 2.00 | 10.00 |
| `claude-haiku-5-5` | 0.10 | 0.50 |
| `claude-fable-5-1` | 10.00 | 50.00 |

These are **reference prices for estimation only**. Always check the
provider's own pricing page, and override the prices on the profile when you
need an accurate figure. Costs are always labelled as estimates.

## 11. Failover

`FailoverProvider` tries a list of providers in order and moves to the next one
when a provider call fails. A budget violation is a hard stop — failing over
would only spend more money.

## 12. Secret handling

* API keys are stored in the database and **never** returned by the API — only
  a mask (`••••1234`) and a `has_key` flag.
* Secrets are redacted from logs, error messages, exports and reports.
* Never commit credentials: `.env` is git-ignored and the example file only
  contains placeholders.
* Rotate a key by updating the profile; the old key is never echoed back.

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `HTTP 401` on test | wrong or missing key | check the key and the base URL |
| `HTTP 404` on the OpenAI endpoint | the account has no access to that model | use **Discover models** and pick a listed id |
| `cannot reach Ollama` | Ollama is not running | `ollama serve` |
| `model discovery failed` | the provider does not expose `/models` | set the model id manually from the provider's docs |
| judge returns `null` scores | the model did not answer with a number | the raw output is stored for inspection; consider a stricter rubric |
| cost shows 0 | no price configured | set the price on the profile, or the price is genuinely unknown — the report says so |
