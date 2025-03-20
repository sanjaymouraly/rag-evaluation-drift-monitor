"""Evaluation orchestration.

An evaluation run walks a frozen benchmark dataset, executes the RAG under
test, scores every item with the metric registry and persists the evidence.

Guarantees
----------
* **Idempotency** — a run is identified by ``idempotency_key``; a duplicate
  submission returns the existing run instead of starting a second one.
* **Partial-write safety** — each item result is committed on its own, so an
  interrupted run keeps the evidence it already produced and is marked
  ``failed`` with the error, never silently lost.
* **Cancellation** — the run checks ``cancel_requested`` between items.
* **Budget** — a hard per-run spend limit aborts the run instead of overshooting.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import delete

from .. import EVAL_CODE_VERSION
from ..metrics import MetricContext, all_metrics
from ..models import DatasetItem, Document, EvaluationRun, RagApp, RunResult
from ..providers import BudgetGuard, ProviderBudgetExceeded
from ..rag import SampleRAG, run_rest_adapter
from ..retrievers import chunk_statistics
from .aggregate import aggregate_results

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rqm-eval")

logger = logging.getLogger("rqm.evaluation")


# ------------------------------------------------------------------ helpers


def dataset_checksum(items: list[DatasetItem]) -> str:
    """Stable checksum of the *content* of a dataset (ignores ids)."""
    payload = json.dumps(
        [
            {
                "q": i.question,
                "r": i.reference_answer,
                "a": list(i.aliases or []),
                "rel": sorted(i.relevant_doc_ids or []),
                "grades": i.relevance_grades or {},
                "cit": i.expected_citations or [],
                "cat": i.category,
                "ans": i.answerable,
            }
            for i in items
        ],
        sort_keys=True,
        default=str,
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def corpus_manifest(documents: list[Document]) -> list[dict]:
    return [
        {
            "doc_id": d.doc_id,
            "revision": d.revision,
            "fingerprint": d.fingerprint,
            "chars": len(d.text),
            "title": d.title,
        }
        for d in sorted(documents, key=lambda x: x.doc_id)
    ]


def _build_context(item: DatasetItem, chunks_by_id: dict[str, dict]) -> MetricContext:
    return MetricContext(
        question=item.question,
        reference_answer=item.reference_answer,
        aliases=list(item.aliases or []),
        relevant_doc_ids=list(item.relevant_doc_ids or []),
        relevance_grades=dict(item.relevance_grades or {}),
        expected_citations=list(item.expected_citations or []),
        category=item.category,
        cohorts=list(item.cohorts or []),
        answerable=bool(item.answerable),
        mode="end_to_end",
    )


def score_item(
    item: DatasetItem, output: dict, chunks_by_id: dict[str, dict], corpus_doc_ids: list[str], mode: str
) -> tuple[dict, dict]:
    """Score one item. Returns ``(metric_values, evidence)``.

    ``metric_values`` maps a metric name to a float or ``None``.
    ``evidence`` records *why* a metric is missing and keeps the detailed
    per-citation / per-claim diagnostics.
    """
    ctx = _build_context(item, chunks_by_id)
    ctx.chunks_by_id = dict(chunks_by_id)
    ctx.retrieved = list(output.get("retrieved") or [])
    ctx.citations = list(output.get("citations") or [])
    ctx.answer = output.get("answer", "")
    ctx.abstained = bool(output.get("abstained"))
    ctx.corpus_doc_ids = list(corpus_doc_ids)
    ctx.mode = mode
    ctx.latency_ms = float(output.get("latency_ms", 0.0) or 0.0)
    ctx.retrieval_latency_ms = float(output.get("retrieval_ms", 0.0) or 0.0)
    ctx.generation_latency_ms = float(output.get("generation_ms", 0.0) or 0.0)
    ctx.input_tokens = int(output.get("input_tokens", 0) or 0)
    ctx.output_tokens = int(output.get("output_tokens", 0) or 0)
    ctx.estimated_cost_usd = float(output.get("cost_usd", 0.0) or 0.0)
    ctx.cost_is_estimate = not bool(output.get("usage_exact"))
    ctx.error = output.get("error", "") or ""

    values: dict = {}
    evidence: dict = {}
    for name, spec in all_metrics().items():
        result = spec.compute(ctx)
        values[name] = result.value
        entry: dict = {"kind": result.kind}
        if result.reason:
            entry["missing_reason"] = result.reason
        if result.detail:
            entry.update(result.detail)
        if result.evidence:
            entry["evidence"] = result.evidence
        evidence[name] = entry
    return values, evidence


# ---------------------------------------------------------------- executors


def _execute_builtin(item: DatasetItem, rag: SampleRAG, mode: str) -> dict:
    if mode == "retrieval_only":
        retrieved, retrieval_ms = rag.retrieve(item.question)
        return {
            "answer": "",
            "abstained": False,
            "citations": [],
            "retrieved": retrieved,
            "retrieval_ms": retrieval_ms,
            "generation_ms": 0.0,
            "latency_ms": retrieval_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
    if mode == "generation_only":
        gold = [c for c in rag.chunks if c["doc_id"] in set(item.relevant_doc_ids or [])][:5]
        from ..rag import extractive_answer

        t0 = time.perf_counter()
        answer = extractive_answer(item.question, gold, float(rag.config.get("abstain_threshold", 0.18)))
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "answer": answer["answer"],
            "abstained": answer["abstained"],
            "citations": answer.get("citations", []),
            "retrieved": [
                {
                    "chunk_id": c["chunk_id"],
                    "doc_id": c["doc_id"],
                    "score": 1.0,
                    "text": c["text"][:800],
                    "char_start": c.get("char_start"),
                    "char_end": c.get("char_end"),
                }
                for c in gold
            ],
            "retrieval_ms": 0.0,
            "generation_ms": elapsed,
            "latency_ms": elapsed,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
    return rag.run(item.question)


def _execute_rest(item: DatasetItem, adapter: dict) -> dict:
    return run_rest_adapter(adapter, item.question)


# --------------------------------------------------------------------- run


def execute_run(db, run_id: int, progress_cb=None) -> None:
    """Execute a queued run. Safe to call from a worker thread or synchronously."""
    run = db.get(EvaluationRun, run_id)
    if run is None:
        return
    if run.status == "cancelled":
        return
    run.status = "running"
    run.started_at = dt.datetime.now(dt.UTC)
    run.progress = 0
    db.commit()

    try:
        app = db.get(RagApp, run.app_id)
        if app is None:
            raise RuntimeError("RAG application no longer exists")
        items = db.query(DatasetItem).filter_by(dataset_id=run.dataset_id).order_by(DatasetItem.id).all()
        documents = db.query(Document).filter_by(project_id=app.project_id).order_by(Document.doc_id).all()
        config = dict(app.config or {})
        mode = run.mode
        corpus_doc_ids = [d.doc_id for d in documents]

        generator = None
        provider_info = None
        gen_spec = config.get("generator") or {}
        if gen_spec.get("mode") == "llm" and gen_spec.get("provider_id"):
            generator, provider_info = _load_generator(db, gen_spec["provider_id"])

        rag = None
        chunks_by_id: dict[str, dict] = {}
        adapter = config.get("adapter") or {"type": "builtin"}
        if adapter.get("type") == "builtin":
            rag = SampleRAG(
                [{"doc_id": d.doc_id, "title": d.title, "text": d.text} for d in documents], config, generator=generator
            )
            chunks_by_id = rag.chunks_by_id

        budget = BudgetGuard(
            float(run.config_snapshot.get("budget_usd", 0) or 0) if isinstance(run.config_snapshot, dict) else 0.0,
            label=f"run {run_id}",
        )
        budget.limit_usd = float(config.get("max_run_cost_usd", 0) or 0) or budget.limit_usd

        # A re-run replaces the previous results of the same run id.
        db.execute(delete(RunResult).where(RunResult.run_id == run_id))
        db.commit()

        total_in = total_out = 0
        total_cost = 0.0
        usage_exact = True
        errors: list[str] = []

        for index, item in enumerate(items):
            fresh = db.get(EvaluationRun, run_id)
            if fresh is not None and fresh.cancel_requested:
                run = fresh
                run.status = "cancelled"
                run.finished_at = dt.datetime.now(dt.UTC)
                run.progress = int(100 * index / max(1, len(items)))
                db.commit()
                return

            try:
                if adapter.get("type") == "rest":
                    output = _execute_rest(item, adapter)
                    chunks_by_id = {
                        r["chunk_id"]: {
                            "doc_id": r["doc_id"],
                            "text": r.get("text", ""),
                            "char_start": r.get("char_start"),
                            "char_end": r.get("char_end"),
                        }
                        for r in output["retrieved"]
                    }
                else:
                    output = _execute_builtin(item, rag, mode)
            except Exception as exc:  # noqa: BLE001 - a single failing item must not kill the run
                message = f"{type(exc).__name__}: {exc}"[:400]
                errors.append(f"item {item.id}: {message}")
                output = {
                    "answer": "",
                    "abstained": False,
                    "citations": [],
                    "retrieved": [],
                    "retrieval_ms": 0.0,
                    "generation_ms": 0.0,
                    "latency_ms": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "error": message,
                }

            values, evidence = score_item(item, output, chunks_by_id, corpus_doc_ids, mode)
            total_in += int(output.get("input_tokens", 0) or 0)
            total_out += int(output.get("output_tokens", 0) or 0)
            total_cost += float(output.get("cost_usd", 0.0) or 0.0)
            usage_exact = usage_exact and bool(output.get("usage_exact", False))

            db.add(
                RunResult(
                    run_id=run_id,
                    item_id=item.id,
                    question=item.question,
                    category=item.category,
                    cohorts=list(item.cohorts or []),
                    answerable=item.answerable,
                    answer=output.get("answer", ""),
                    abstained=bool(output.get("abstained")),
                    retrieved=output.get("retrieved", []),
                    citations=output.get("citations", []),
                    metrics=values,
                    evidence=evidence,
                    latency_ms=float(output.get("latency_ms", 0.0) or 0.0),
                    retrieval_latency_ms=float(output.get("retrieval_ms", 0.0) or 0.0),
                    generation_latency_ms=float(output.get("generation_ms", 0.0) or 0.0),
                    input_tokens=int(output.get("input_tokens", 0) or 0),
                    output_tokens=int(output.get("output_tokens", 0) or 0),
                    error=output.get("error", "") or "",
                )
            )
            db.commit()  # each item is durable on its own

            run = db.get(EvaluationRun, run_id)
            if run is not None:
                run.progress = int(100 * (index + 1) / max(1, len(items)))
                db.commit()
            if progress_cb:
                progress_cb(index + 1, len(items))

            budget.charge(float(output.get("cost_usd", 0.0) or 0.0))
            if not budget.unlimited and budget.spent_usd > budget.limit_usd:
                raise ProviderBudgetExceeded(
                    f"run budget of ${budget.limit_usd:.2f} exhausted after {index + 1} item(s)"
                )

        stored = db.query(RunResult).filter_by(run_id=run_id).all()
        run = db.get(EvaluationRun, run_id)
        if run is None:
            return
        run.metrics = aggregate_results(stored, mode)
        run.config_snapshot = {
            "app_config": config,
            "dataset_checksum": dataset_checksum(items),
            "dataset_id": run.dataset_id,
            "corpus_manifest": corpus_manifest(documents),
            "eval_code_version": EVAL_CODE_VERSION,
            "seed": config.get("seed", 42),
            "n_documents": len(documents),
            "n_chunks": len(rag.chunks) if rag else 0,
            "chunk_stats": chunk_statistics(rag.chunks) if rag else {},
            "retriever": config.get("retriever", "bm25"),
            "top_k": config.get("top_k", 5),
            "chunk_chars": config.get("chunk_chars", 600),
            "overlap_chars": config.get("overlap_chars", 80),
            "generator": provider_info,
            "budget": budget.snapshot(),
            "errors": errors,
        }
        run.total_input_tokens, run.total_output_tokens = total_in, total_out
        run.estimated_cost_usd = round(total_cost, 8)
        run.cost_is_estimate = not usage_exact
        run.status = "failed" if errors and not stored else "completed"
        if errors and stored:
            run.error = f"{len(errors)} item(s) failed; first error: {errors[0][:300]}"
        run.progress = 100
        run.finished_at = dt.datetime.now(dt.UTC)
        db.commit()
    except ProviderBudgetExceeded as exc:
        db.rollback()
        run = db.get(EvaluationRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = f"Budget stop: {exc}"
            run.finished_at = dt.datetime.now(dt.UTC)
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("evaluation run %s failed", run_id)
        run = db.get(EvaluationRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"[:2000]
            run.finished_at = dt.datetime.now(dt.UTC)
            db.commit()


def _load_generator(db, provider_id: int):
    """Instantiate the configured generation provider (if it is usable)."""
    from ..models import ProviderProfile
    from ..providers import ProviderConfig, build_provider

    profile = db.get(ProviderProfile, provider_id)
    if profile is None or not profile.enabled:
        return None, {"error": "generation provider missing or disabled"}
    provider = build_provider(ProviderConfig.from_profile(profile))
    return provider, {"provider": profile.name, "kind": profile.kind, "model": profile.model}


def submit_run(db, run_id: int) -> None:
    """Schedule a run on the background worker pool."""
    from ..db import SessionLocal

    def _job() -> None:
        session = SessionLocal()
        try:
            execute_run(session, run_id)
        finally:
            session.close()

    _executor.submit(_job)
