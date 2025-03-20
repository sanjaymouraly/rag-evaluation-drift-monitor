# Security

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Use GitHub's
private vulnerability reporting ("Security" → "Report a vulnerability") or
contact the maintainers directly.

Include the affected version, a reproduction and the impact. We aim to
acknowledge a report within a few working days.

## Deployment guidance

* The documented local commands bind to `127.0.0.1` and are intended for
  development. **A development deployment has no authentication.**
* Before exposing the service to a network:
  * set `RQM_API_KEY` — every endpoint except `/health` and `/ready` then
    requires the `X-API-Key` header (compared in constant time),
  * restrict `RQM_CORS_ORIGINS` to the origins that actually serve the
    dashboard,
  * terminate TLS in front of the service,
  * use PostgreSQL rather than SQLite for concurrent workloads.
* Run the API as an unprivileged user (the Docker image already does) and keep
  the database file outside the web root.
* Back up the database regularly (`scripts/backup.sh`).

## How the platform handles sensitive data

| Area | Behaviour |
|---|---|
| Provider API keys | Stored server-side in the database. The API returns only a mask (`••••1234`) and a `has_key` flag — never the key. Keys are redacted from logs, error messages, exports and reports. |
| Environment files | `.env` is git-ignored; `.env.example` contains placeholders only. |
| Documents | Stored as plain text in the project corpus. They are part of the evaluation data — treat the database as sensitive. |
| Production traces | Opt-in. Only the question, the answer, the retrieved document ids and the latency are kept. Import them only with the consent of your privacy/legal process. |
| Evaluation runs | The full answer, the retrieved passages, the citations and the metric evidence are persisted, so runs can contain sensitive content. |
| Reports | Exports contain the same content as the run. Store them accordingly. |

## Untrusted input

* **Retrieved documents are data, never instructions.** The built-in prompts
  delimit the context, state explicitly that it must not be followed, and the
  LLM-judge prompt does the same. Document content is never executed, never
  interpolated into a system prompt and never rendered as HTML by the backend.
* **Uploads** are size-limited (`RQM_MAX_UPLOAD_BYTES`), parsed as text only,
  and their file names are sanitised.
* **Path traversal** is blocked for every file operation: names are reduced to
  a single safe path component and every resolved path is checked to stay
  inside the allowed root.
* **`doc_id` values** may not contain path separators.
* **The API** applies a per-IP rate limit (`RQM_RATE_LIMIT_PER_MINUTE`) and
  returns `X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy` on
  every response.
* **SQL** is always parameterised through the ORM; no string-built SQL.
* **Errors** from providers are redacted before they are stored or shown, so a
  credential echoed back by an upstream service does not leak into a log.

## Retention and deletion

* Deleting a project deletes its applications, runs, results, datasets,
  documents, policies, alerts and traces.
* Deleting a dataset that is referenced by a run is refused (`409`) so the
  evidence of a past evaluation stays auditable.
* Retention of runs, traces and documents is a deployment decision: export
  what you need and delete the rest with the API.

## Known limitations

* Authentication is a single shared API key — there is no per-user identity,
  no role model and no audit log of *who* made a change. For team use, put
  the service behind an authenticating proxy.
* The rate limiter is in-process and per-instance; it does not coordinate
  across replicas.
* The built-in extractive answerer is deterministic and simple; it is not a
  security boundary. When you plug in an LLM, keep the prompt-injection
  guidance in place and review the retrieved content yourself.
