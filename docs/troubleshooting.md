# Troubleshooting

## Installation

**`error: externally-managed-environment` when running `pip install`**

Use a virtual environment (the setup scripts create one for you):

```bash
python3 -m venv .venv && source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**`SyntaxError` / `TypeError` on `Mapped[str | None]`**

The `X | Y` annotation syntax needs Python 3.10+. Use Python 3.11 or newer.

**`pip install` fails to build `numpy` / `scipy`**

Those packages need a wheel for your platform and Python version. Use a
supported Python (3.11–3.14) and upgrade pip:

```bash
python -m pip install --upgrade pip wheel
```

**`npm install` fails in the frontend**

Node 20 or newer is required. Check with `node --version`. Delete
`frontend/node_modules` and `frontend/package-lock.json` and retry
`npm install` if the lock file is out of sync.

## Running the application

**`Address already in use` on port 8000**

```bash
PORT=9000 ./scripts/start.sh          # Linux / macOS
$env:PORT=9000; .\scripts\start.ps1   # Windows PowerShell
```

**The dashboard shows "Cannot reach the API"**

* Is the backend running? `curl http://127.0.0.1:8000/health`
* Does the API key match? When `RQM_API_KEY` is set the dashboard must send
  the `X-API-Key` header. For local development leave it empty.
* Is the API bound to `127.0.0.1` while the dashboard runs in a container? In
  Docker Compose the nginx proxy handles this; when running the frontend on
  the host, use `VITE_API_BASE=http://127.0.0.1:8000`.

**`sqlite3.OperationalError: database is locked`**

Two processes are writing to the same SQLite file. SQLite is a single-writer
database: for concurrent use switch to PostgreSQL. For local development, stop
the duplicate process.

**The database is empty after a restart**

The working directory matters: the default URL is relative
(`sqlite:///./rag_monitor.db`). Either start the server from the `backend/`
directory (as the scripts do) or set an absolute path:

```bash
export RQM_DATABASE_URL="sqlite:////absolute/path/rag_monitor.db"
```

## Evaluations

**A run finishes with `status: "failed"`**

Open the run in the dashboard — the error is stored in the run record and is
also visible in **System → execution log**. The usual causes are an
unreachable REST adapter, a malformed adapter response, or a budget stop.

**`empty_retrieval` is 1.0 for every question**

The retriever returned nothing. Check that the project has documents
(`GET /api/documents?project_id=…`) and that the `doc_id`s used in the
benchmark exist in the corpus — `GET /api/datasets/{id}/validate` reports
exactly this.

**Retrieval metrics are `null`**

The benchmark items have no `relevant_doc_ids`. Retrieval metrics need
relevance labels; without them the metric is *missing evidence*, not zero.
The dataset validation endpoint lists every unlabelled item.

**`citation_support` is 0.0 although the answer looks good**

The citation is not *supported* by the cited chunk. This is the metric doing
its job: a citation that names a real document is not automatically accurate.
Open the run's evidence viewer to see, per citation, whether the quote was
found, whether the chunk supports a claim, or whether the citation points at
a document that does not exist.

**The judge returns `null` scores**

The model did not answer with a single number between 0 and 1. The raw output
is stored (`/api/runs/{id}/judge-results`) so you can see what came back.
Make the rubric stricter, or use a model that follows the format.

**A provider call fails with `HTTP 401`**

The key is wrong, expired, or missing. Update the profile. Remember that a
ChatGPT subscription does not include OpenAI API credits.

**`cannot reach Ollama`**

Ollama is not running or the port is wrong:

```bash
ollama serve
curl http://localhost:11434/api/tags
```

**The judge costs more than expected**

The budget is per judge call and is a hard stop. Check
`GET /api/system` for the configured ceilings and use a cheaper model.

## Release gates

**The gate says INCONCLUSIVE but the metrics look fine**

Look at the `evidence` field of the failing checks. The usual reasons are:

* `n` is below the policy's `min_samples`,
* the metric was not computed for any item (missing evidence),
* a relative rule has no approved baseline.

This is intentional: missing evidence must never produce a PASS.

**The gate always passes**

Check that the policy actually contains rules and that the metric names match
the metric names in the run (`GET /api/metrics/catalogue`).

**The comparison says "not comparable"**

The two runs used different datasets. A paired comparison is only meaningful
on the same frozen benchmark — the platform refuses to pretend otherwise.

## Drift

**PSI is `null`**

PSI needs at least five samples per run. Small datasets cannot produce a
meaningful distribution comparison.

**The drift report lists many hypotheses**

They are hypotheses, not conclusions. Each one names a concrete difference
between the two run snapshots (retriever, chunk size, corpus change, …) that
you can confirm or dismiss in the comparison view.

## Frontend

**`tsc -b` fails after a dependency change**

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**The charts are empty**

The dashboard only shows persisted results. Seed the demo data
(`python -m app.seed --reset`) or run an evaluation first. The platform never
renders placeholder metrics.

**Playwright cannot launch Chromium**

```bash
cd frontend
npx playwright install --with-deps chromium
```

On Linux the system dependencies are required (`--with-deps` installs them with
sudo).

## Getting help

When reporting a problem, include:

* the output of `GET /api/system` (it is redacted),
* the run id and the run's `error` field,
* the relevant part of the backend log,
* your Python and Node versions and your operating system.
