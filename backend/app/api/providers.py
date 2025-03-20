"""AI provider configuration, connection testing, model discovery and judging."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..evaluation import RUBRICS, judge_metric_summary, run_judge
from ..models import EvaluationRun, JudgeResult, ProviderProfile
from ..providers import PRESETS, ProviderConfig, build_provider
from ..providers.presets import ROLES, preset_list
from ..providers.pricing import price_per_1k
from .deps import get_or_404, provider_out
from .schemas import JudgeIn, ProviderIn, ReviewIn

router = APIRouter(prefix="/api", tags=["providers"])


@router.get("/providers/presets")
def list_presets():
    """Ready-made provider presets so a user does not have to copy URLs."""
    return {
        "presets": preset_list(),
        "roles": ROLES,
        "note": "A ChatGPT Plus/Pro subscription does not include OpenAI API credits.",
    }


@router.get("/providers/pricing")
def list_pricing(model: str = ""):
    """Reference prices (USD per 1M tokens) and the per-1k conversion."""
    if model:
        price_in, price_out, source = price_per_1k(model)
        return {
            "model": model,
            "price_per_1k_input": price_in,
            "price_per_1k_output": price_out,
            "price_source": source,
            "note": "Reference prices are estimates; always verify against the provider's own pricing page.",
        }
    return {"note": "Pass ?model=<id> to look up the reference price of one model."}


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    return [provider_out(p) for p in db.query(ProviderProfile).order_by(ProviderProfile.id).all()]


@router.post("/providers", status_code=201)
def create_provider(body: ProviderIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["api_key"] = data.get("api_key") or ""
    preset = PRESETS.get((body.kind or "").lower())
    if not data.get("base_url") and preset:
        data["base_url"] = preset.base_url
    if not data.get("model") and preset:
        data["model"] = preset.default_model
    if body.price_per_1k_input or body.price_per_1k_output:
        data["price_source"] = "user-supplied"
    else:
        ref_in, ref_out, source = price_per_1k(data.get("model", ""))
        data["price_per_1k_input"] = ref_in
        data["price_per_1k_output"] = ref_out
        data["price_source"] = source
    profile = ProviderProfile(**data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return provider_out(profile)


@router.put("/providers/{provider_id}")
def update_provider(provider_id: int, body: ProviderIn, db: Session = Depends(get_db)):
    profile = get_or_404(db, ProviderProfile, provider_id, "provider")
    data = body.model_dump()
    if data.get("api_key") is None:
        data.pop("api_key", None)
    for key, value in data.items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return provider_out(profile)


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int, db: Session = Depends(get_db)):
    profile = get_or_404(db, ProviderProfile, provider_id, "provider")
    db.delete(profile)
    db.commit()
    return {"deleted": provider_id}


@router.post("/providers/{provider_id}/test")
def test_provider(provider_id: int, db: Session = Depends(get_db)):
    """Test the connection. Failures are reported honestly — never faked."""
    profile = get_or_404(db, ProviderProfile, provider_id, "provider")
    provider = build_provider(ProviderConfig.from_profile(profile))
    result = provider.test_connection()
    result["provider"] = profile.name
    result["kind"] = profile.kind
    result["model"] = profile.model
    return result


@router.get("/providers/{provider_id}/models")
def provider_models(provider_id: int, db: Session = Depends(get_db)):
    """Discover the models the provider exposes (documented endpoint)."""
    profile = get_or_404(db, ProviderProfile, provider_id, "provider")
    if (profile.kind or "").lower() == "offline":
        return {
            "models": ["offline-deterministic"],
            "note": "Offline mode uses deterministic metrics; there is no model to discover.",
        }
    provider = build_provider(ProviderConfig.from_profile(profile))
    try:
        models = provider.list_models()
    except Exception as exc:
        raise HTTPException(502, f"model discovery failed: {exc}") from exc
    enriched = []
    for model in models[:200]:
        price_in, price_out, source = price_per_1k(model)
        enriched.append(
            {"id": model, "price_per_1k_input": price_in, "price_per_1k_output": price_out, "price_source": source}
        )
    return {"models": enriched, "count": len(models)}


# ------------------------------------------------------------------- judging


@router.get("/judge/rubrics")
def list_rubrics():
    return {
        "rubrics": [{"dimension": key, **value} for key, value in RUBRICS.items()],
        "limitation": "LLM-judge scores are opinion signals, not proof of correctness.",
    }


@router.post("/judge")
def judge(body: JudgeIn, db: Session = Depends(get_db)):
    """Run the optional LLM judge over a completed run."""
    get_or_404(db, EvaluationRun, body.run_id, "run")
    try:
        summary = run_judge(db, body.run_id, body.provider_id, body.budget_usd, body.dimensions)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    run = db.get(EvaluationRun, body.run_id)
    if run is not None:
        judge_metrics = judge_metric_summary(db, body.run_id)
        if judge_metrics:
            metrics = dict(run.metrics or {})
            metrics.setdefault("metrics", {})
            metrics["metrics"].update(judge_metrics)
            metrics.setdefault("metric_kinds", {}).update(dict.fromkeys(judge_metrics, "judge"))
            run.metrics = metrics
            db.commit()
    return summary


@router.get("/runs/{run_id}/judge-results")
def judge_results(run_id: int, db: Session = Depends(get_db)):
    get_or_404(db, EvaluationRun, run_id, "run")
    records = db.query(JudgeResult).filter_by(run_id=run_id).order_by(JudgeResult.id).all()
    return [
        {
            "id": j.id,
            "result_id": j.result_id,
            "provider": j.provider_name,
            "model": j.model,
            "rubric_version": j.rubric_version,
            "dimension": j.dimension,
            "score": j.score,
            "rationale": j.rationale,
            "raw_output": j.raw_output,
            "usage_exact": j.usage_exact,
            "estimated_cost_usd": j.estimated_cost_usd,
            "human_verdict": j.human_verdict,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in records
    ]


@router.post("/judge-results/{judge_id}/review")
def review_judge(judge_id: int, body: ReviewIn, db: Session = Depends(get_db)):
    """Record a human review of a judge verdict."""
    record = get_or_404(db, JudgeResult, judge_id, "judge result")
    record.human_verdict = body.verdict
    db.commit()
    return {
        "id": record.id,
        "human_verdict": record.human_verdict,
        "note": "Human review recorded. Judge scores remain opinion signals, not ground truth.",
    }
