"""Report exports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Dataset, EvaluationRun, GateEvaluation, RagApp, RunResult
from ..reports import run_to_dict, to_ci_summary, to_csv, to_html, to_markdown
from .deps import get_or_404

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/runs/{run_id}/export")
def export_run(run_id: int, format: str = "json", gate_policy: int | None = None, db: Session = Depends(get_db)):
    """Export a run report as JSON, CSV, Markdown, HTML or a CI summary."""
    run = get_or_404(db, EvaluationRun, run_id, "run")
    results = db.query(RunResult).filter_by(run_id=run_id).order_by(RunResult.id).all()
    report = run_to_dict(run, db.get(RagApp, run.app_id), db.get(Dataset, run.dataset_id), results)
    gate = None
    if gate_policy:
        evaluation = (
            db.query(GateEvaluation)
            .filter_by(policy_id=gate_policy, candidate_run_id=run_id)
            .order_by(GateEvaluation.id.desc())
            .first()
        )
        if evaluation is not None:
            gate = {"verdict": evaluation.verdict, "summary": evaluation.summary, "checks": evaluation.checks}
            report["gate"] = gate
    if format == "json":
        return report
    if format == "csv":
        return PlainTextResponse(
            to_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=run-{run_id}.csv"},
        )
    if format in ("md", "markdown"):
        return PlainTextResponse(
            to_markdown(report, gate),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=run-{run_id}.md"},
        )
    if format == "html":
        return Response(
            to_html(report, gate),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=run-{run_id}.html"},
        )
    if format in ("ci", "summary"):
        return to_ci_summary(report, gate)
    raise HTTPException(422, "format must be json|csv|md|html|ci")
