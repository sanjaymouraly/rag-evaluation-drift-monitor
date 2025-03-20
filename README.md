# RAG Evaluation, Regression & Drift Monitor

Monitors RAG quality over time with regression tests, drift detection, and evaluation reports.

## Features

- Retrieval-only, generation-only and end-to-end evaluation modes.
- Retrieval metrics: precision@k, recall@k, hit rate, MRR, MAP, NDCG with graded relevance, context precision/recall, coverage, duplicate-chunk rate, missing-source rate.
- Answer metrics: exact match, normalised match, token F1, completeness, faithfulness, claim support, hallucination rate, answer relevancy, contradiction detection, correct abstention, over-abstention.
- Citation metrics: presence, structural validity, genuine support, unsupported rate, precision, document recall, claim attribution, coverage — with per-citation outcomes and source-offset verification.
- Operational metrics: stage and end-to-end latency (p50/p95/p99), tokens, cost per request and per successful answer, failure and error rates.
- A metric plugin interface: register your own metric in three lines.
- Versioned datasets with a content checksum, cloning, CSV/JSONL/JSON import and export, deduplication, and a validation endpoint that reports missing sources, unlabelled items and duplicates *before* you run.

## Stack

Python, Node.js, FastAPI, Uvicorn, SQLAlchemy, Pydantic, HTTPX, NumPy, SciPy, React

## Clone

```bash
git clone https://github.com/sanjaymouraly/rag-evaluation-drift-monitor.git
cd rag-evaluation-drift-monitor
```

## Setup

```bash
# The project ships a Docker Compose setup.
docker compose up --build
```

See `docs/` or the compose file for environment variables and ports.

## Run

```bash
docker compose up --build
```

## Tests

```bash
pytest -q
```

## Notes

- Sample data, when included, is synthetic.

## License

MIT © 2025 [Sanjay Mouraly](https://github.com/sanjaymouraly)
