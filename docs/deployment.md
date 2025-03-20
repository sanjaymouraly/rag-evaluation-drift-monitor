# Deployment

## Local development (default)

The default configuration is a **loopback-bound** single process with a SQLite
database:

```bash
./scripts/setup.sh      # or .\scripts\setup.ps1 on Windows
./scripts/start.sh
```

* API — <http://127.0.0.1:8000> (docs at `/docs`)
* Dashboard — <http://127.0.0.1:5173>

This configuration has **no authentication**. That is deliberate for a
loopback-bound development server and it is documented as such. Do not expose
it to a network without setting `RQM_API_KEY`.

## Docker Compose

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

* Dashboard — <http://127.0.0.1:8080> (nginx proxies `/api` to the backend)
* API — <http://127.0.0.1:8000>

The SQLite database lives in the named volume `rqm-data` (mounted at `/data`).

### PostgreSQL profile

```bash
docker compose --profile postgres up -d
```

Then point the backend at it:

```yaml
environment:
  RQM_DATABASE_URL: postgresql+psycopg://rqm:rqm@postgres:5432/rqm
```

Install the driver in the image (add to `backend/requirements.txt`):

```
psycopg[binary]>=3.1
```

Apply the migrations:

```bash
cd backend
RQM_DATABASE_URL="postgresql+psycopg://rqm:rqm@localhost:5432/rqm" alembic upgrade head
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `RQM_DATABASE_URL` | `sqlite:///./rag_monitor.db` | SQLAlchemy URL |
| `RQM_ENVIRONMENT` | `development` | free-form environment label |
| `RQM_API_KEY` | *(empty)* | when set, `X-API-Key` is required everywhere except the probes |
| `RQM_CORS_ORIGINS` | `http://localhost:5173,…` | comma-separated allowed origins |
| `RQM_TRUSTED_HOSTS` | *(empty)* | comma-separated allowed host headers |
| `RQM_MAX_UPLOAD_BYTES` | `10485760` | upload size limit |
| `RQM_RATE_LIMIT_PER_MINUTE` | `600` | per-IP request budget |
| `RQM_MAX_WORKERS` | `4` | background evaluation workers |
| `RQM_RUN_TIMEOUT_S` | `3600` | run timeout |
| `RQM_SCHEDULER_ENABLED` | `false` | start the scheduler with the app |
| `RQM_SCHEDULER_TICK_S` | `60` | scheduler interval |
| `RQM_DEFAULT_BUDGET_USD` | `1.0` | default judge budget |
| `RQM_HARD_COST_LIMIT_USD` | `25.0` | global spend ceiling |
| `RQM_MAX_RUN_COST_USD` | `5.0` | per-run spend ceiling |
| `RQM_ALERT_WEBHOOK_URL` | *(empty)* | webhook for drift / gate alerts |
| `RQM_LOG_LEVEL` | `INFO` | log level |
| `RQM_DEMO_MODE` | `false` | demo flag |

## Production checklist

1. **Set `RQM_API_KEY`.** Every request except `/health` and `/ready` must
   carry `X-API-Key`. Terminate TLS in front of the service.
2. **Restrict CORS** to the origins that actually serve the dashboard.
3. **Use PostgreSQL** and run `alembic upgrade head` on every deploy.
4. **Back up the database** (`./scripts/backup.sh` or `pg_dump`).
5. **Keep the server bound to a private interface** and put a reverse proxy in
   front of it.
6. **Review the retention policy** for documents, traces and runs — the
   platform stores the full text of your corpus and (optionally) production
   traces.
7. **Do not enable the scheduler in more than one replica** unless you accept
   duplicated evaluations.

## Migrations

```bash
cd backend
alembic upgrade head          # apply
alembic downgrade -1          # roll back one revision
alembic history               # list the revisions
alembic current               # show the applied revision
```

The schema is created automatically (`Base.metadata.create_all`) on a fresh
SQLite database, which is convenient for local development. Use alembic for
anything you care about.

## Backups

```bash
./scripts/backup.sh                                  # SQLite copy
RQM_DATABASE_URL=postgresql+psycopg://… ./scripts/backup.sh   # pg_dump
```

For SQLite, back up with the `sqlite3 .backup` command (or stop the service
first) — copying the file while it is being written can produce a torn
database.

## Monitoring the service

* `GET /health` — liveness (never authenticated).
* `GET /ready` — readiness, verifies that the database answers.
* `GET /api/system` — configuration and the log of failed / cancelled runs.
* Structured logs go to stdout; set `RQM_LOG_LEVEL=DEBUG` for more detail.

## Scaling notes

* The workload is I/O bound (HTTP calls to the RAG system under test), so
  threads are a good fit; `RQM_MAX_WORKERS` controls the pool.
* Long evaluations are CPU-light but can run for minutes. Run them in the
  background (`wait: false`) and poll the run status, or use the CLI.
* The database is the shared state. With several replicas, use PostgreSQL and
  disable the built-in scheduler on all but one replica.

## Security summary

* API key authentication (optional but recommended).
* Rate limiting per client IP.
* Upload size limits and safe file-name sanitisation.
* Path-traversal protection for every file operation.
* Secret redaction in logs, reports and API responses.
* Retrieved document content is treated as untrusted data: it is never
  executed, and prompts explicitly delimit it as data.
* No document is ever rendered as HTML by the backend.
