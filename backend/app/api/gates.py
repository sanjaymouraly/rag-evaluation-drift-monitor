"""Release gate policies, evaluations and their audit history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..gates import DEFAULT_POLICY_RULES, RULE_TYPES, RunView, evaluate_gate
from ..models import Dataset, EvaluationRun, GateEvaluation, GatePolicy, Project, RagApp, RunResult
from .deps import get_or_404, policy_out
from .schemas import GateEvalIn, PolicyIn

router = APIRouter(prefix="/api", tags=["gates"])


def build_run_view(db: Session, run: EvaluationRun) -> RunView:
    rows = db.query(RunResult).filter_by(run_id=run.id).all()
    return RunView(
        run_id=run.id,
        metrics=(run.metrics or {}).get("metrics", {}) or {},
        results=[
            {
                "item_id": r.item_id,
                "question": r.question,
                "category": r.category,
                "cohorts": r.cohorts or [],
                "metrics": r.metrics or {},
            }
            for r in rows
        ],
        label=f"run-{run.id}",
    )


@router.get("/gate-policies")
def list_policies(project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(GatePolicy)
    if project_id:
        query = query.filter_by(project_id=project_id)
    return [policy_out(p) for p in query.order_by(GatePolicy.id).all()]


@router.get("/gate-policies/defaults")
def default_rules():
    return {
        "rules": DEFAULT_POLICY_RULES,
        "rule_types": list(RULE_TYPES),
        "note": "Example thresholds for demonstration — tune them to your own benchmark.",
    }


@router.post("/gate-policies", status_code=201)
def create_policy(body: PolicyIn, db: Session = Depends(get_db)):
    get_or_404(db, Project, body.project_id, "project")
    for rule in body.rules:
        if rule.get("type") not in RULE_TYPES:
            raise HTTPException(422, f"unknown rule type '{rule.get('type')}'; allowed: {', '.join(RULE_TYPES)}")
    rules = body.rules or DEFAULT_POLICY_RULES
    policy = GatePolicy(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        baseline_run_id=body.baseline_run_id,
        rules=rules,
        min_samples=body.min_samples,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy_out(policy)


@router.put("/gate-policies/{policy_id}")
def update_policy(policy_id: int, body: PolicyIn, db: Session = Depends(get_db)):
    policy = get_or_404(db, GatePolicy, policy_id, "policy")
    for rule in body.rules:
        if rule.get("type") not in RULE_TYPES:
            raise HTTPException(422, f"unknown rule type '{rule.get('type')}'; allowed: {', '.join(RULE_TYPES)}")
    policy.name = body.name
    policy.description = body.description
    policy.baseline_run_id = body.baseline_run_id
    policy.rules = body.rules or policy.rules
    policy.min_samples = body.min_samples
    policy.version += 1
    db.commit()
    db.refresh(policy)
    return policy_out(policy)


@router.delete("/gate-policies/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = get_or_404(db, GatePolicy, policy_id, "policy")
    db.delete(policy)
    db.commit()
    return {"deleted": policy_id}


@router.post("/gate-policies/{policy_id}/evaluate")
def evaluate_policy(policy_id: int, body: GateEvalIn, db: Session = Depends(get_db)):
    """Evaluate a candidate run against the policy and store the audit record."""
    policy = get_or_404(db, GatePolicy, policy_id, "policy")
    candidate = get_or_404(db, EvaluationRun, body.candidate_run_id, "run")
    if candidate.status != "completed":
        raise HTTPException(422, f"candidate run status is '{candidate.status}', not completed")
    baseline_id = body.baseline_run_id or policy.baseline_run_id
    baseline = db.get(EvaluationRun, baseline_id) if baseline_id else None
    if baseline is not None and baseline.status != "completed":
        raise HTTPException(422, f"baseline run status is '{baseline.status}', not completed")
    result = evaluate_gate(
        policy.rules,
        policy.min_samples,
        build_run_view(db, candidate),
        build_run_view(db, baseline) if baseline is not None else None,
    )
    evaluation = GateEvaluation(
        policy_id=policy.id,
        candidate_run_id=candidate.id,
        baseline_run_id=baseline_id,
        verdict=result["verdict"],
        checks=result["checks"],
        summary=result["summary"],
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return {
        "id": evaluation.id,
        "policy_id": evaluation.policy_id,
        "candidate_run_id": evaluation.candidate_run_id,
        "baseline_run_id": evaluation.baseline_run_id,
        "verdict": evaluation.verdict,
        "checks": evaluation.checks,
        "summary": evaluation.summary,
        "candidate_app": (db.get(RagApp, candidate.app_id).version_label if db.get(RagApp, candidate.app_id) else None),
        "baseline_app": (
            db.get(RagApp, baseline.app_id).version_label
            if baseline is not None and db.get(RagApp, baseline.app_id)
            else None
        ),
    }


@router.get("/gate-evaluations")
def list_gate_evaluations(
    policy_id: int | None = None, candidate_run_id: int | None = None, db: Session = Depends(get_db)
):
    query = db.query(GateEvaluation)
    if policy_id:
        query = query.filter_by(policy_id=policy_id)
    if candidate_run_id:
        query = query.filter_by(candidate_run_id=candidate_run_id)
    evaluations = query.order_by(GateEvaluation.id.desc()).all()
    return [
        {
            "id": e.id,
            "policy_id": e.policy_id,
            "candidate_run_id": e.candidate_run_id,
            "baseline_run_id": e.baseline_run_id,
            "verdict": e.verdict,
            "checks": e.checks,
            "summary": e.summary,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in evaluations
    ]


@router.get("/gate-evaluations/{evaluation_id}")
def get_gate_evaluation(evaluation_id: int, db: Session = Depends(get_db)):
    evaluation = get_or_404(db, GateEvaluation, evaluation_id, "gate evaluation")
    candidate = db.get(EvaluationRun, evaluation.candidate_run_id)
    baseline = db.get(EvaluationRun, evaluation.baseline_run_id) if evaluation.baseline_run_id else None
    return {
        "id": evaluation.id,
        "policy_id": evaluation.policy_id,
        "candidate_run_id": evaluation.candidate_run_id,
        "baseline_run_id": evaluation.baseline_run_id,
        "verdict": evaluation.verdict,
        "checks": evaluation.checks,
        "summary": evaluation.summary,
        "candidate": (
            {
                "app": db.get(RagApp, candidate.app_id).name,
                "version": db.get(RagApp, candidate.app_id).version_label,
                "dataset": db.get(Dataset, candidate.dataset_id).name,
            }
            if candidate
            else None
        ),
        "baseline": (
            {
                "app": db.get(RagApp, baseline.app_id).name,
                "version": db.get(RagApp, baseline.app_id).version_label,
                "dataset": db.get(Dataset, baseline.dataset_id).name,
            }
            if baseline
            else None
        ),
        "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
    }
