"""System endpoints: health, overview, metrics catalogue, alerts, scheduler, traces."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..evaluation import RUBRICS
from ..metrics import metric_catalogue
from ..models import (
    Alert,
    Dataset,
    DatasetItem,
    Document,
    EvaluationRun,
    GateEvaluation,
    JudgeResult,
    ProductionTrace,
    Project,
    ProviderProfile,
    RagApp,
    ScheduledJob,
)
from ..retrievers import RETRIEVER_KINDS
from .deps import get_or_404, run_out
from .schemas import ScheduledJobIn, TraceIn

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """Aggregated project health — every number comes from persisted runs."""
    runs = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).all()
    apps = {a.id: a for a in db.query(RagApp).all()}
    datasets = {d.id: d for d in db.query(Dataset).all()}
    completed = [r for r in runs if r.status == "completed"]
    failed = [r for r in runs if r.status == "failed"]
    verdicts = db.query(GateEvaluation).order_by(GateEvaluation.id.desc()).all()
    latest_metrics = (completed[0].metrics or {}).get("metrics", {}) if completed else {}
    history = []
    for run in reversed(completed):
        metrics = (run.metrics or {}).get("metrics", {}) or {}
        app = apps.get(run.app_id)
        history.append(
            {
                "run_id": run.id,
                "app_id": run.app_id,
                "app_version": app.version_label if app else "?",
                "app_name": app.name if app else "?",
                "recall_at_5": (metrics.get("recall_at_5") or {}).get("value"),
                "token_f1": (metrics.get("token_f1") or {}).get("value"),
                "faithfulness": (metrics.get("faithfulness") or {}).get("value"),
                "citation_support": (metrics.get("citation_support") or {}).get("value"),
                "latency_p95_ms": (metrics.get("latency_p95_ms") or {}).get("value"),
                "estimated_cost_usd": (metrics.get("estimated_cost_usd") or {}).get("value"),
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
        )
    return {
        "counts": {
            "projects": db.query(Project).count(),
            "apps": db.query(RagApp).count(),
            "datasets": db.query(Dataset).count(),
            "documents": db.query(Document).count(),
            "runs": db.query(EvaluationRun).count(),
            "runs_completed": len(completed),
            "runs_failed": len(failed),
            "gate_evaluations": db.query(GateEvaluation).count(),
            "alerts_open": db.query(Alert).filter_by(status="open").count(),
            "scheduled_jobs": db.query(ScheduledJob).filter_by(enabled=True).count(),
        },
        "recent_runs": [run_out(r, apps.get(r.app_id), datasets.get(r.dataset_id)) for r in runs[:15]],
        "latest_metrics": latest_metrics,
        "history": history,
        "gate_verdicts": [
            {
                "id": v.id,
                "verdict": v.verdict,
                "summary": v.summary,
                "candidate_run_id": v.candidate_run_id,
                "baseline_run_id": v.baseline_run_id,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in verdicts[:10]
        ],
        "demo_project_ids": [p.id for p in db.query(Project).filter_by(is_demo=True).all()],
    }


@router.get("/metrics/catalogue")
def metrics_catalogue():
    """Every metric the platform can compute, with its provenance and requirements."""
    return {"metrics": metric_catalogue(), "judge_dimensions": list(RUBRICS), "retrievers": RETRIEVER_KINDS}


@router.get("/system")
def system_info(db: Session = Depends(get_db)):
    """System configuration with secrets redacted, plus a run execution log."""
    failed = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.status.in_(["failed", "cancelled"]))
        .order_by(EvaluationRun.id.desc())
        .limit(50)
        .all()
    )
    return {
        "version": "1.1.0",
        "environment": settings.environment,
        "database": settings.database_url.split("://")[0] + "://…(redacted)",
        "api_key_auth_enabled": bool(settings.api_key),
        "cors_origins": settings.cors_origin_list,
        "trusted_hosts": settings.trusted_host_list,
        "max_upload_bytes": settings.max_upload_bytes,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "max_workers": settings.max_workers,
        "default_budget_usd": settings.default_budget_usd,
        "hard_cost_limit_usd": settings.hard_cost_limit_usd,
        "max_run_cost_usd": settings.max_run_cost_usd,
        "alert_webhook_configured": bool(settings.alert_webhook_url),
        "scheduler_enabled": settings.scheduler_enabled,
        "demo_mode": settings.demo_mode,
        "counts": {
            "runs_completed": db.query(EvaluationRun).filter_by(status="completed").count(),
            "runs_failed": db.query(EvaluationRun).filter_by(status="failed").count(),
            "judge_results": db.query(JudgeResult).count(),
            "alerts_open": db.query(Alert).filter_by(status="open").count(),
            "providers": db.query(ProviderProfile).count(),
        },
        "execution_log": [
            {
                "run_id": r.id,
                "status": r.status,
                "error": r.error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in failed
        ],
    }


@router.get("/alerts")
def list_alerts(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Alert)
    if status:
        query = query.filter_by(status=status)
    return [
        {
            "id": a.id,
            "project_id": a.project_id,
            "kind": a.kind,
            "severity": a.severity,
            "message": a.message,
            "status": a.status,
            "fingerprint": a.fingerprint,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in query.order_by(Alert.id.desc()).all()
    ]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = get_or_404(db, Alert, alert_id, "alert")
    alert.status = "acknowledged"
    db.commit()
    return {"id": alert.id, "status": alert.status}


# ------------------------------------------------------------- scheduled jobs


@router.get("/scheduled-jobs")
def list_jobs(db: Session = Depends(get_db)):
    return [
        {
            "id": j.id,
            "project_id": j.project_id,
            "name": j.name,
            "app_id": j.app_id,
            "dataset_id": j.dataset_id,
            "policy_id": j.policy_id,
            "interval_minutes": j.interval_minutes,
            "mode": j.mode,
            "enabled": j.enabled,
            "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            "last_run_id": j.last_run_id,
            "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
        }
        for j in db.query(ScheduledJob).order_by(ScheduledJob.id).all()
    ]


@router.post("/scheduled-jobs", status_code=201)
def create_job(body: ScheduledJobIn, db: Session = Depends(get_db)):
    get_or_404(db, Project, body.project_id, "project")
    get_or_404(db, RagApp, body.app_id, "app")
    get_or_404(db, Dataset, body.dataset_id, "dataset")
    job = ScheduledJob(
        project_id=body.project_id,
        name=body.name,
        app_id=body.app_id,
        dataset_id=body.dataset_id,
        policy_id=body.policy_id,
        interval_minutes=body.interval_minutes,
        mode=body.mode,
        enabled=body.enabled,
        next_run_at=dt.datetime.now(dt.UTC),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "name": job.name, "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None}


@router.delete("/scheduled-jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, ScheduledJob, job_id, "scheduled job")
    db.delete(job)
    db.commit()
    return {"deleted": job_id}


# ---------------------------------------------------------- production traces


@router.post("/traces", status_code=201)
def import_trace(body: TraceIn, db: Session = Depends(get_db)):
    """Import a sampled production trace (opt-in, privacy-conscious)."""
    get_or_404(db, Project, body.project_id, "project")
    trace = ProductionTrace(
        project_id=body.project_id,
        question=body.question,
        answer=body.answer,
        retrieved_doc_ids=body.retrieved_doc_ids,
        category=body.category,
        latency_ms=body.latency_ms,
        source=body.source,
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return {"id": trace.id, "stored": True, "note": "Only the fields needed for offline evaluation are kept."}


@router.get("/traces")
def list_traces(project_id: int, limit: int = 100, db: Session = Depends(get_db)):
    traces = (
        db.query(ProductionTrace)
        .filter_by(project_id=project_id)
        .order_by(ProductionTrace.id.desc())
        .limit(min(limit, 1000))
        .all()
    )
    return [
        {
            "id": t.id,
            "question": t.question,
            "answer": t.answer,
            "retrieved_doc_ids": t.retrieved_doc_ids,
            "category": t.category,
            "latency_ms": t.latency_ms,
            "source": t.source,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in traces
    ]


@router.post("/traces/import-to-dataset", status_code=201)
def traces_to_dataset(project_id: int, dataset_id: int, limit: int = 100, db: Session = Depends(get_db)):
    """Turn sampled production traces into unreviewed dataset items."""
    get_or_404(db, Project, project_id, "project")
    get_or_404(db, Dataset, dataset_id, "dataset")
    traces = (
        db.query(ProductionTrace)
        .filter_by(project_id=project_id)
        .order_by(ProductionTrace.id.desc())
        .limit(min(limit, 1000))
        .all()
    )
    existing = {i.question.strip().lower() for i in db.query(DatasetItem).filter_by(dataset_id=dataset_id).all()}
    created = 0
    for trace in traces:
        key = trace.question.strip().lower()
        if not key or key in existing:
            continue
        existing.add(key)
        db.add(
            DatasetItem(
                dataset_id=dataset_id,
                question=trace.question,
                relevant_doc_ids=list(trace.retrieved_doc_ids or []),
                category="production-unreviewed",
                answerable=True,
                notes="Imported from a production trace. Requires human review.",
            )
        )
        created += 1
    db.commit()
    return {
        "created": created,
        "warning": "Imported items are labelled production-unreviewed and are not trusted as ground truth.",
    }
