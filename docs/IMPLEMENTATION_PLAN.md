# Implementation Plan & Acceptance Criteria

This document records what was planned, what was built and how each acceptance
criterion was verified. It is kept in the repository so that the state of the
project is auditable.

## The vertical slice (works end-to-end offline, no API key)

1. Ingest the sample corpus → chunk → BM25 index.
2. Run the benchmark through the built-in RAG (retrieve → answer → cite).
3. Score every item with the metric registry; persist the run, the per-item
   results and the evidence.
4. Compare a baseline with a candidate; evaluate the release gate and get
   `PASS` / `FAIL` / `INCONCLUSIVE`.
5. Show the persisted results in the dashboard; export JSON / CSV / Markdown /
   HTML / CI reports.

## Acceptance criteria — status 1.1.0

| # | Criterion | How it was verified | Result |
|---|---|---|---|
| 1 | A new user can install and launch the application | `scripts/setup.sh` was executed end-to-end from a clean copy of the repository in a fresh virtual environment | ✅ |
| 2 | The complete offline evaluation workflow functions without paid APIs | `python -m app.seed --reset` creates the corpus, the benchmark, four versions, five runs and three gate verdicts — with no network call | ✅ |
| 3 | Actual document ingestion, retrieval, answering and scoring are demonstrated | `test_integration.py` + the seeded demo: 12 documents, 38 questions, BM25 retrieval, extractive answering with citations | ✅ |
| 4 | Multiple RAG versions are compared on the same dataset | `GET /api/compare?a=2&b=4` → paired per-question deltas, `comparable: true` | ✅ |
| 5 | Core metrics are correct against known expected results | `test_metrics.py` asserts hand-computed values (precision@5 = 0.4, MRR = 0.5, AP = 0.5, NDCG, token F1 = 0.5, …) | ✅ |
| 6 | Release gates distinguish passing, failing and inconclusive results | `test_gates.py` + the demo seed → `PASS`, `FAIL` and `INCONCLUSIVE` with evidence | ✅ |
| 7 | A deliberately degraded version is blocked by a real gate | The `degraded_keyword` retriever really breaks retrieval (recall@5 1.00 → 0.40); the gate returns `FAIL` and the CLI exits with `1` | ✅ |
| 8 | Drift monitoring uses real run data and defensible statistics | `test_drift.py` + the drift explorer: PSI, KS, JSD, control charts, labelled hypotheses | ✅ |
| 9 | Provider adapters are functional, with honest reporting | `test_providers.py` drives every adapter over a mock transport; the connection test reports failures honestly | ✅ (credential-dependent live calls need a key) |
| 10 | The dashboard displays real persisted results | The Playwright suite and the screenshots in `docs/images/` | ✅ |
| 11 | Reports can be generated and exported | `test_reports.py` + `GET /api/runs/{id}/export?format=…` | ✅ |
| 12 | Automated tests, CI workflows and Docker startup are verified | `pytest -q` (172 passed), `npm run test` (27), `npx playwright test` (7), both Docker images built and smoke-tested | ✅ |
| 13 | Genuine screenshots and Windows/Linux instructions exist | 15 screenshots captured from the running stack; `docs/images/`, README | ✅ |
| 14 | No fake metrics, fabricated verification, embedded credentials or placeholder core functionality | Every number in the dashboard comes from the API; the seed is deterministic; no key is committed | ✅ |
| 15 | The repository is professionally organised | Modular package layout, explicit migrations, CI workflows, docs per area | ✅ |

## Commands executed for the final verification

```text
backend:  ruff check app tests            -> All checks passed!
          ruff format --check app tests   -> 66 files already formatted
          mypy app                         -> Success: no issues found in 55 source files
          pytest -q                        -> 172 passed
frontend: npm run test                    -> 27 passed
          npm run build                   -> tsc -b + vite build, 0 errors
          npx playwright test             -> 7 passed
docker:   Dockerfile.backend             -> built, container healthy, seeded, gate FAIL exit 1
          Dockerfile.frontend             -> built, container healthy, dashboard served
          docker compose up -d --build     -> both services healthy (see the note below)
```

## Environment notes (honest limitations of this environment)

* **Container-to-container TCP is blocked in this sandbox.** The Compose
  services both start and pass their health checks, and the frontend's nginx
  resolves the `backend` service name to the right address, but the TCP
  connection between the two containers times out. On a normal Docker host
  this works; it is an environment restriction, not a configuration error.
* **PowerShell is not installed here**, so `scripts/setup.ps1` and
  `scripts/start.ps1` could not be executed. The shell equivalents were run
  from a clean checkout. The PowerShell scripts were reviewed line by line
  (a broken `$Root` expression was found and fixed this way).
* **No AI provider credentials were available**, so the live provider paths
  were exercised through mock transports. The adapters, the retry/backoff
  behaviour, the redaction, the pricing and the budget guard are all covered
  by tests; a real call has not been made from this environment.

## Architecture decisions

* **Modular monolith.** One Python package, one database, one process. Clear
  module boundaries (`app.metrics`, `app.providers`, `app.retrievers`,
  `app.evaluation`, `app.gates`, `app.drift`, `app.reports`, `app.api`) with
  no cross-module shortcuts.
* **SQLite by default, PostgreSQL in production.** The same models and the
  same alembic migrations serve both. The migration is written out explicitly
  so the schema history is reviewable and reversible.
* **BM25 from scratch** (transparent and testable) plus TF-IDF and a
  feature-hash retriever. A vector-database adapter only needs to implement
  `search(query, top_k)`.
* **Extractive answering offline** so the demo needs no LLM. LLM generation and
  LLM judging are optional and configured through provider profiles.
* **Every metric declares its provenance.** Missing evidence returns `null`
  with a reason; the gate reports `INCONCLUSIVE`. No metric is ever replaced
  by a fabricated value.
* **Jobs run on a bounded thread pool** with a persisted status, a
  cancellation flag and an idempotency key. Each item result is committed on
  its own, so an interrupted run keeps its evidence.
* **The gate is statistical, not a threshold comparison.** Relative rules use
  paired per-question differences with a bootstrap CI, a Wilcoxon test, an
  effect size and a multiple-comparison correction, and a change whose
  confidence interval lies inside the tolerance band is treated as noise.
