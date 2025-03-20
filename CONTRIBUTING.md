# Contributing

Thanks for taking the time to improve RAG Quality Monitor. This document
describes the workflow and the rules that keep the project honest.

## Getting set up

```bash
git clone https://github.com/your-org/rag-quality-monitor.git
cd rag-quality-monitor
./scripts/setup.sh          # Linux / macOS
.\scripts\setup.ps1         # Windows PowerShell
```

## The rules that matter

1. **Never fabricate a metric value.** When a metric lacks the evidence it
   requires, return `None` and a reason. The release gate must be able to
   distinguish "measured 0.0" from "not measured".
2. **Always label the provenance.** Every metric declares a kind
   (`deterministic`, `reference_based`, `heuristic`, `embedding_based`,
   `judge`, `operational`) and the reports and the dashboard show it.
3. **A heuristic is not ground truth.** Faithfulness, hallucination rate and
   answer relevancy are surface-overlap estimates. Do not describe them as
   verified correctness anywhere in the code, the UI or the docs.
4. **Metric changes need hand-computed expected values.** Add the new metric
   to `backend/tests/test_metrics.py` with a value you worked out by hand,
   including the edge cases: empty retrieval, missing labels, abstention and
   unsupported citations.
5. **Provider changes are tested with mocked transports.** CI must never need
   a live API key. Use `httpx.MockTransport`.
6. **Never commit credentials.** `.env` is git-ignored; `.env.example` only
   contains placeholders. Provider keys live in the database and are only ever
   returned masked.
7. **Do not fake screenshots.** The images in `docs/images/` are captured from
   a running stack with `scripts/capture_screenshots.py`. Re-capture them
   whenever the UI changes and commit the new files.

## Before you open a pull request

```bash
# backend
cd backend
pip install -r requirements-dev.txt
ruff check app tests
ruff format --check app tests
pytest -q

# frontend
cd ../frontend
npm install
npm run test
npm run build
npx playwright install chromium
npx playwright test
```

## Commit messages

Use a short imperative subject line, e.g.

```
Add per-cohort release gate scopes
Fix citation support when the chunk map is empty
Document the Ollama provider setup
```

## Adding a metric

```python
from app.metrics import MetricContext, MetricResult, register_metric

class MyMetric:
    name = "answer_length"
    kind = "operational"
    requires = ()
    description = "Average answer length in words."

    def compute(self, ctx: MetricContext) -> MetricResult:
        if not ctx.answer:
            return MetricResult.missing("no answer")
        return MetricResult(value=float(len(ctx.answer.split())), kind="operational")

register_metric(MyMetric())
```

Then add it to `METRIC_KINDS` in `backend/app/metrics/__init__.py` (the test
suite fails if a metric has no declared kind) and write the hand-computed
tests.

## Adding a provider

Subclass `app.providers.base.BaseProvider`, implement `_call_once` and
optionally `list_models` / `embed`, then map the new kind in
`app/providers/__init__.py` and add a preset in
`app/providers/presets.py`. Document the authentication and billing model
honestly — including the fact that a consumer subscription is not API credit.

## Documentation

Update the relevant file in `docs/` and the README when behaviour, commands or
screenshots change. Every command in the README must work as written.

## Reporting a bug

Include the output of `GET /api/system` (it is redacted), the run id, the
run's `error` field, the backend log excerpt, and your Python/Node versions
and operating system.
