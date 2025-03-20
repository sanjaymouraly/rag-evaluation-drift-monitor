"""Evaluation runs, per-item evidence and version comparison."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..evaluation import execute_run, run_judge, submit_run
from ..models import Dataset, EvaluationRun, RagApp, RunResult
from .deps import get_or_404, run_out
from .schemas import RunIn

router = APIRouter(prefix="/api", tags=["runs"])

COMPARE_METRICS = [
    "recall_at_5",
    "precision_at_5",
    "hit_at_5",
    "mrr",
    "map",
    "ndcg_at_5",
    "context_precision",
    "context_recall",
    "token_f1",
    "exact_match",
    "faithfulness",
    "claim_support_rate",
    "hallucination_rate",
    "correct_abstention",
    "citation_support",
    "citation_structural_valid",
    "citation_doc_recall",
    "latency_p95_ms",
    "estimated_cost_usd",
]


@router.post("/runs", status_code=201)
def create_run(body: RunIn, db: Session = Depends(get_db)):
    """Start an evaluation run.

    Supplying ``idempotency_key`` makes the call safe to retry: the existing
    run is returned instead of starting a duplicate.
    """
    if body.mode not in ("end_to_end", "retrieval_only", "generation_only"):
        raise HTTPException(422, "mode must be end_to_end|retrieval_only|generation_only")
    get_or_404(db, RagApp, body.app_id, "app")
    get_or_404(db, Dataset, body.dataset_id, "dataset")
    if body.idempotency_key:
        existing = db.query(EvaluationRun).filter_by(idempotency_key=body.idempotency_key).first()
        if existing is not None:
            return run_out(existing, db.get(RagApp, existing.app_id), db.get(Dataset, existing.dataset_id))
    run = EvaluationRun(
        app_id=body.app_id,
        dataset_id=body.dataset_id,
        mode=body.mode,
        status="queued",
        idempotency_key=body.idempotency_key,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    if body.wait:
        execute_run(db, run.id)
        db.refresh(run)
    else:
        submit_run(db, run.id)
    if body.judge_provider_id and run.status == "completed":
        try:
            run_judge(db, run.id, body.judge_provider_id, body.judge_budget_usd, body.judge_dimensions)
            db.refresh(run)
        except ValueError as exc:
            run.error = f"Judge skipped: {exc}"
            db.commit()
    return run_out(run, db.get(RagApp, run.app_id), db.get(Dataset, run.dataset_id))


@router.get("/runs")
def list_runs(
    app_id: int | None = None, dataset_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)
):
    query = db.query(EvaluationRun)
    if app_id:
        query = query.filter_by(app_id=app_id)
    if dataset_id:
        query = query.filter_by(dataset_id=dataset_id)
    if status:
        query = query.filter_by(status=status)
    runs = query.order_by(EvaluationRun.id.desc()).all()
    apps = {a.id: a for a in db.query(RagApp).all()}
    datasets = {d.id: d for d in db.query(Dataset).all()}
    return [run_out(r, apps.get(r.app_id), datasets.get(r.dataset_id)) for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = get_or_404(db, EvaluationRun, run_id, "run")
    return run_out(run, db.get(RagApp, run.app_id), db.get(Dataset, run.dataset_id))


@router.get("/runs/{run_id}/results")
def run_results(
    run_id: int,
    category: str | None = None,
    cohort: str | None = None,
    failures_only: bool = False,
    db: Session = Depends(get_db),
):
    """Per-item results with the full evidence trail."""
    get_or_404(db, EvaluationRun, run_id, "run")
    query = db.query(RunResult).filter_by(run_id=run_id)
    if category:
        query = query.filter_by(category=category)
    results = query.order_by(RunResult.id).all()
    out = []
    for result in results:
        if cohort and cohort not in (result.cohorts or []):
            continue
        metrics = result.metrics or {}
        failed = (
            (metrics.get("token_f1") is not None and float(metrics["token_f1"]) < 0.3)
            or metrics.get("recall_at_5") == 0.0
            or bool(result.error)
        )
        if failures_only and not failed:
            continue
        out.append(
            {
                "id": result.id,
                "item_id": result.item_id,
                "question": result.question,
                "category": result.category,
                "cohorts": result.cohorts or [],
                "answerable": result.answerable,
                "answer": result.answer,
                "abstained": result.abstained,
                "retrieved": result.retrieved,
                "citations": result.citations,
                "metrics": metrics,
                "evidence": result.evidence or {},
                "latency_ms": result.latency_ms,
                "retrieval_latency_ms": result.retrieval_latency_ms,
                "generation_latency_ms": result.generation_latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "error": result.error,
            }
        )
    return out


@router.get("/runs/{run_id}/results/{result_id}")
def run_result_detail(run_id: int, result_id: int, db: Session = Depends(get_db)):
    """Full evidence for one question: retrieved passages, citations, verdicts."""
    get_or_404(db, EvaluationRun, run_id, "run")
    result = get_or_404(db, RunResult, result_id, "run result")
    if result.run_id != run_id:
        raise HTTPException(404, "run result not found in this run")
    return {
        "id": result.id,
        "item_id": result.item_id,
        "question": result.question,
        "category": result.category,
        "cohorts": result.cohorts or [],
        "answerable": result.answerable,
        "answer": result.answer,
        "abstained": result.abstained,
        "retrieved": result.retrieved,
        "citations": result.citations,
        "metrics": result.metrics,
        "evidence": result.evidence or {},
        "latency_ms": result.latency_ms,
        "error": result.error,
    }


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    run = get_or_404(db, EvaluationRun, run_id, "run")
    run.cancel_requested = True
    db.commit()
    return {
        "run_id": run_id,
        "cancel_requested": True,
        "status": run.status,
        "note": "The run stops after the item that is currently in flight.",
    }


@router.post("/runs/{run_id}/rerun", status_code=201)
def rerun(run_id: int, db: Session = Depends(get_db)):
    """Re-execute a run with the *same* configuration (reproducibility check)."""
    source = get_or_404(db, EvaluationRun, run_id, "run")
    run = EvaluationRun(app_id=source.app_id, dataset_id=source.dataset_id, mode=source.mode, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    execute_run(db, run.id)
    db.refresh(run)
    return run_out(run, db.get(RagApp, run.app_id), db.get(Dataset, run.dataset_id))


@router.get("/compare")
def compare(a: int, b: int, db: Session = Depends(get_db)):
    """Compare two runs question-by-question (paired) and metric-by-metric."""
    run_a = get_or_404(db, EvaluationRun, a, "run")
    run_b = get_or_404(db, EvaluationRun, b, "run")
    metrics_a = (run_a.metrics or {}).get("metrics", {}) or {}
    metrics_b = (run_b.metrics or {}).get("metrics", {}) or {}
    table = []
    for key in sorted(set(metrics_a) | set(metrics_b)):
        value_a = (metrics_a.get(key) or {}).get("value")
        value_b = (metrics_b.get(key) or {}).get("value")
        table.append(
            {
                "metric": key,
                "a": value_a,
                "b": value_b,
                "delta_b_minus_a": (
                    round(value_b - value_a, 6) if value_a is not None and value_b is not None else None
                ),
                "kind": (metrics_a.get(key) or metrics_b.get(key) or {}).get("kind"),
                "n_a": (metrics_a.get(key) or {}).get("n"),
                "n_b": (metrics_b.get(key) or {}).get("n"),
            }
        )
    results_a = {str(r.item_id): r for r in db.query(RunResult).filter_by(run_id=a).all()}
    results_b = {str(r.item_id): r for r in db.query(RunResult).filter_by(run_id=b).all()}
    per_question = []
    for key in sorted(set(results_a) & set(results_b), key=lambda k: int(k)):
        ra, rb = results_a[key], results_b[key]
        metrics_ra, metrics_rb = ra.metrics or {}, rb.metrics or {}
        top_a = [x.get("doc_id") for x in (ra.retrieved or [])[:5]]
        top_b = [x.get("doc_id") for x in (rb.retrieved or [])[:5]]
        per_question.append(
            {
                "item_id": ra.item_id,
                "question": ra.question,
                "category": ra.category,
                "cohorts": ra.cohorts or [],
                "f1_a": metrics_ra.get("token_f1"),
                "f1_b": metrics_rb.get("token_f1"),
                "f1_delta": (
                    round(metrics_rb["token_f1"] - metrics_ra["token_f1"], 6)
                    if metrics_ra.get("token_f1") is not None and metrics_rb.get("token_f1") is not None
                    else None
                ),
                "recall_a": metrics_ra.get("recall_at_5"),
                "recall_b": metrics_rb.get("recall_at_5"),
                "faithfulness_a": metrics_ra.get("faithfulness"),
                "faithfulness_b": metrics_rb.get("faithfulness"),
                "citation_support_a": metrics_ra.get("citation_support"),
                "citation_support_b": metrics_rb.get("citation_support"),
                "answer_a": ra.answer,
                "answer_b": rb.answer,
                "top5_a": top_a,
                "top5_b": top_b,
                "top5_changed": top_a != top_b,
            }
        )
    same_dataset = run_a.dataset_id == run_b.dataset_id
    return {
        "run_a": run_out(run_a, db.get(RagApp, run_a.app_id), db.get(Dataset, run_a.dataset_id)),
        "run_b": run_out(run_b, db.get(RagApp, run_b.app_id), db.get(Dataset, run_b.dataset_id)),
        "metrics": table,
        "per_question": per_question,
        "comparable": same_dataset,
        "warning": None
        if same_dataset
        else "The two runs use different datasets — the deltas above are NOT a paired comparison.",
    }


@router.get("/compare/multi")
def compare_multi(runs: str, db: Session = Depends(get_db)):
    """Metric table across two or more runs (versions) of the same dataset."""
    ids = [int(x) for x in runs.split(",") if x.strip()]
    if len(ids) < 2:
        raise HTTPException(422, "provide at least two run ids: ?runs=1,2,3")
    out_runs: list[dict] = []
    table: dict[str, dict[str, float | None]] = {key: {} for key in COMPARE_METRICS}
    for run_id in ids:
        run = get_or_404(db, EvaluationRun, run_id, "run")
        out_runs.append(run_out(run, db.get(RagApp, run.app_id), db.get(Dataset, run.dataset_id)))
        metrics = (run.metrics or {}).get("metrics", {}) or {}
        for key in COMPARE_METRICS:
            table[key][str(run_id)] = (metrics.get(key) or {}).get("value")
    same_dataset = len({r["dataset_id"] for r in out_runs}) == 1
    return {
        "runs": out_runs,
        "metrics_by_run": table,
        "comparable": same_dataset,
        "warning": None if same_dataset else "Runs use different datasets — deltas are NOT paired comparisons.",
    }


@router.get("/runs/{run_id}/history")
def metric_history(run_id: int, metric: str = "recall_at_5", limit: int = 50, db: Session = Depends(get_db)):
    """Historical series of one metric for the app that produced this run."""
    run = get_or_404(db, EvaluationRun, run_id, "run")
    runs = db.query(EvaluationRun).filter_by(app_id=run.app_id).order_by(EvaluationRun.id).all()[-limit:]
    series = []
    for item in runs:
        if item.status != "completed":
            continue
        value = ((item.metrics or {}).get("metrics", {}) or {}).get(metric, {}).get("value")
        series.append(
            {
                "run_id": item.id,
                "value": value,
                "app_version": (db.get(RagApp, item.app_id).version_label if db.get(RagApp, item.app_id) else None),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    return {"metric": metric, "app_id": run.app_id, "series": series}
