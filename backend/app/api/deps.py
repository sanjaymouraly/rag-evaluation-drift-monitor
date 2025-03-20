"""Shared API helpers: authentication, rate limiting, serialisation."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from ..config import settings
from ..models import (
    Dataset,
    DatasetItem,
    Document,
    EvaluationRun,
    GatePolicy,
    Project,
    ProviderProfile,
    RagApp,
)
from ..security import constant_time_equals, mask_key

# In-memory sliding-window rate limiter (per client IP).
_rate: dict[str, list[float]] = defaultdict(list)


def check_api_key(request: Request) -> None:
    """Enforce the optional shared API key.

    The development default is an open loopback-bound service. When an API key
    is configured every endpoint except the health probes requires it.
    """
    if not settings.api_key:
        return
    if request.url.path in ("/health", "/ready", "/", "/docs", "/openapi.json"):
        return
    provided = request.headers.get("x-api-key", "")
    if not constant_time_equals(provided, settings.api_key):
        raise HTTPException(401, "missing or invalid X-API-Key header")


def check_rate_limit(request: Request) -> None:
    limit = int(settings.rate_limit_per_minute or 0)
    if limit <= 0:
        return
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = [t for t in _rate[ip] if now - t < 60]
    if len(bucket) >= limit:
        raise HTTPException(429, "rate limit exceeded")
    bucket.append(now)
    _rate[ip] = bucket


# ------------------------------------------------------------------ lookups


def get_or_404(db, model, object_id: int, label: str):
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(404, f"{label} {object_id} not found")
    return obj


# -------------------------------------------------------------- serialisers


def project_out(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "is_demo": project.is_demo,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


def app_out(app: RagApp) -> dict:
    return {
        "id": app.id,
        "project_id": app.project_id,
        "name": app.name,
        "version_label": app.version_label,
        "environment": app.environment,
        "description": app.description,
        "config": app.config,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


def document_out(document: Document) -> dict:
    return {
        "id": document.id,
        "project_id": document.project_id,
        "doc_id": document.doc_id,
        "title": document.title,
        "source": document.source,
        "revision": document.revision,
        "fingerprint": document.fingerprint,
        "chars": len(document.text),
        "preview": (document.text or "")[:200],
        "metadata": document.metadata_ or {},
    }


def dataset_out(dataset: Dataset, n_items: int) -> dict:
    return {
        "id": dataset.id,
        "project_id": dataset.project_id,
        "name": dataset.name,
        "version": dataset.version,
        "description": dataset.description,
        "checksum": dataset.checksum,
        "n_items": n_items,
        "is_synthetic": dataset.is_synthetic,
        "reviewed": dataset.reviewed,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }


def item_out(item: DatasetItem) -> dict:
    return {
        "id": item.id,
        "dataset_id": item.dataset_id,
        "question": item.question,
        "reference_answer": item.reference_answer,
        "aliases": item.aliases,
        "relevant_doc_ids": item.relevant_doc_ids,
        "relevance_grades": item.relevance_grades,
        "expected_citations": item.expected_citations,
        "category": item.category,
        "difficulty": item.difficulty,
        "answerable": item.answerable,
        "language": item.language,
        "topic": item.topic,
        "cohorts": item.cohorts,
        "is_synthetic": item.is_synthetic,
        "human_reviewed": item.human_reviewed,
        "notes": item.notes,
    }


def run_out(run: EvaluationRun, app: RagApp | None = None, dataset: Dataset | None = None) -> dict:
    return {
        "id": run.id,
        "app_id": run.app_id,
        "dataset_id": run.dataset_id,
        "mode": run.mode,
        "status": run.status,
        "progress": run.progress,
        "metrics": run.metrics,
        "config_snapshot": run.config_snapshot,
        "error": run.error,
        "total_input_tokens": run.total_input_tokens,
        "total_output_tokens": run.total_output_tokens,
        "estimated_cost_usd": run.estimated_cost_usd,
        "cost_is_estimate": getattr(run, "cost_is_estimate", True),
        "judge_config": run.judge_config,
        "app_name": app.name if app else None,
        "app_version": app.version_label if app else None,
        "dataset_name": dataset.name if dataset else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def policy_out(policy: GatePolicy) -> dict:
    return {
        "id": policy.id,
        "project_id": policy.project_id,
        "name": policy.name,
        "version": policy.version,
        "description": policy.description,
        "baseline_run_id": policy.baseline_run_id,
        "rules": policy.rules,
        "min_samples": policy.min_samples,
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
    }


def provider_out(profile: ProviderProfile) -> dict:
    """Never leak the API key — only a mask and a presence flag."""
    return {
        "id": profile.id,
        "name": profile.name,
        "kind": profile.kind,
        "role": profile.role,
        "base_url": profile.base_url,
        "api_key_masked": mask_key(profile.api_key),
        "has_key": bool(profile.api_key),
        "model": profile.model,
        "timeout_s": profile.timeout_s,
        "retries": profile.retries,
        "price_per_1k_input": profile.price_per_1k_input,
        "price_per_1k_output": profile.price_per_1k_output,
        "price_source": profile.price_source,
        "is_default": profile.is_default,
        "enabled": profile.enabled,
        "max_concurrency": profile.max_concurrency,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }
