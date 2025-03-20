"""Drift analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..drift import DRIFT_DISCLAIMER, analyse, history_control_chart
from ..models import Alert, DriftReport, EvaluationRun, RagApp, RunResult
from .deps import get_or_404

router = APIRouter(prefix="/api", tags=["drift"])


def _result_rows(db: Session, run_id: int) -> list[dict]:
    rows = db.query(RunResult).filter_by(run_id=run_id).order_by(RunResult.id).all()
    return [
        {
            "item_id": r.item_id,
            "question": r.question,
            "category": r.category,
            "cohorts": r.cohorts or [],
            "metrics": r.metrics or {},
            "retrieved": r.retrieved or [],
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        }
        for r in rows
    ]


@router.get("/drift")
def drift(baseline_run: int, candidate_run: int, db: Session = Depends(get_db)):
    """Compare two runs and persist a drift report."""
    baseline = get_or_404(db, EvaluationRun, baseline_run, "run")
    candidate = get_or_404(db, EvaluationRun, candidate_run, "run")
    app = db.get(RagApp, candidate.app_id)
    project_id = app.project_id if app else 0
    signals, hypotheses = analyse(baseline, candidate, _result_rows(db, baseline_run), _result_rows(db, candidate_run))
    report = DriftReport(
        project_id=project_id,
        baseline_run_id=baseline_run,
        candidate_run_id=candidate_run,
        signals=signals,
        hypotheses=hypotheses,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    drifted = [
        k
        for k, v in signals.items()
        if isinstance(v, dict) and isinstance(v.get("psi"), (int, float)) and v["psi"] >= 0.25
    ]
    if drifted:
        fingerprint = f"drift:{project_id}:{baseline_run}:{candidate_run}:{','.join(sorted(drifted))}"
        if not db.query(Alert).filter_by(fingerprint=fingerprint, status="open").first():
            message = f"Large drift vs run {baseline_run} in {', '.join(drifted)} (candidate run {candidate_run})."
            db.add(
                Alert(project_id=project_id, fingerprint=fingerprint, kind="drift", severity="warning", message=message)
            )
            db.commit()
            _send_webhook({"kind": "drift", "fingerprint": fingerprint, "message": message})
    return {
        "id": report.id,
        "baseline_run": baseline_run,
        "candidate_run": candidate_run,
        "signals": signals,
        "hypotheses": hypotheses,
        "disclaimer": DRIFT_DISCLAIMER,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def _send_webhook(payload: dict) -> None:
    from ..config import settings

    if not settings.alert_webhook_url:
        return
    try:
        import httpx

        httpx.post(settings.alert_webhook_url, json=payload, timeout=settings.alert_webhook_timeout_s)
    except Exception:  # noqa: BLE001 - the alert is persisted; the webhook is best effort
        pass


@router.get("/drift/reports")
def list_reports(project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(DriftReport)
    if project_id:
        query = query.filter_by(project_id=project_id)
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "baseline_run_id": r.baseline_run_id,
            "candidate_run_id": r.candidate_run_id,
            "hypotheses": r.hypotheses,
            "summary": {k: v.get("psi") for k, v in (r.signals or {}).items() if isinstance(v, dict) and "psi" in v},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in query.order_by(DriftReport.id.desc()).all()
    ]


@router.get("/drift/history")
def drift_history(
    metric: str = "recall_at_5", app_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)
):
    """Historical series of a metric plus a control chart over it."""
    query = db.query(EvaluationRun).filter_by(status="completed")
    if app_id:
        query = query.filter_by(app_id=app_id)
    runs = query.order_by(EvaluationRun.id).all()[-limit:]
    series = []
    for run in runs:
        value = ((run.metrics or {}).get("metrics", {}) or {}).get(metric, {}).get("value")
        if value is None:
            continue
        series.append((str(run.id), float(value)))
    return {"metric": metric, "chart": history_control_chart(series), "disclaimer": DRIFT_DISCLAIMER}
