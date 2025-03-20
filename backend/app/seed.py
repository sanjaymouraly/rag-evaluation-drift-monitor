"""Reproducible demo seed.

Creates a demo project with the built-in corpus, a versioned benchmark, four
RAG application versions and their evaluation runs, plus a release-gate policy
that **demonstrably blocks** a degraded candidate.

The seed is deterministic: the same command always produces the same metrics.

Usage::

    python -m app.seed                    # create the demo and run the evaluations
    python -m app.seed --no-run           # only create the project/dataset/apps
    python -m app.seed --reset            # delete the demo first
"""

from __future__ import annotations

from .db import SessionLocal, init_db
from .evaluation import dataset_checksum, execute_run
from .gates import DEFAULT_POLICY_RULES, RunView, evaluate_gate
from .models import (
    Alert,
    Dataset,
    DatasetItem,
    Document,
    DriftReport,
    EvaluationRun,
    GateEvaluation,
    GatePolicy,
    JudgeResult,
    ProductionTrace,
    Project,
    ProviderProfile,
    RagApp,
    RunResult,
    ScheduledJob,
)
from .sample_data import DOCUMENTS, ITEMS
from .security import fingerprint

DEMO_PROJECT_NAME = "Demo — Library Knowledge Base"

BASE_CONFIG = {
    "retriever": "bm25",
    "chunk_chars": 600,
    "overlap_chars": 80,
    "top_k": 5,
    "abstain_threshold": 0.18,
    "seed": 42,
    "adapter": {"type": "builtin"},
    "generator": {"mode": "extractive"},
    "price_per_1k_input": 0.0,
    "price_per_1k_output": 0.0,
}

#: The demo versions. ``degraded`` intentionally breaks retrieval so that the
#: release gate has something real to block.
VERSIONS = [
    (
        "legacy",
        "v0.9-legacy-chunking",
        "Older, coarser chunking",
        {**BASE_CONFIG, "chunk_chars": 900, "overlap_chars": 50},
    ),
    ("baseline", "v1.0-bm25", "Approved baseline", dict(BASE_CONFIG)),
    (
        "candidate",
        "v1.1-bm25-rechunked",
        "Smaller chunks with more overlap",
        {**BASE_CONFIG, "chunk_chars": 450, "overlap_chars": 120},
    ),
    (
        "degraded",
        "v1.2-DEGRADED-first-token-only",
        "Deliberately broken retriever (matches only the first query token)",
        {**BASE_CONFIG, "retriever": "degraded_keyword"},
    ),
]


def _delete_demo(db) -> None:
    project = db.query(Project).filter_by(name=DEMO_PROJECT_NAME).first()
    if project is None:
        return
    for app in db.query(RagApp).filter_by(project_id=project.id).all():
        for run in db.query(EvaluationRun).filter_by(app_id=app.id).all():
            db.query(JudgeResult).filter_by(run_id=run.id).delete()
            db.query(RunResult).filter_by(run_id=run.id).delete()
        db.query(EvaluationRun).filter_by(app_id=app.id).delete()
        db.delete(app)
    db.flush()
    # Gate evaluations reference the policy — they must go first.
    policies = db.query(GatePolicy).filter_by(project_id=project.id).all()
    policy_ids = [p.id for p in policies]
    if policy_ids:
        db.query(GateEvaluation).filter(GateEvaluation.policy_id.in_(policy_ids)).delete(synchronize_session=False)
        db.flush()
        for policy in policies:
            db.delete(policy)
    for dataset in db.query(Dataset).filter_by(project_id=project.id).all():
        db.query(DatasetItem).filter_by(dataset_id=dataset.id).delete()
        db.delete(dataset)
    db.query(Document).filter_by(project_id=project.id).delete()
    db.query(Alert).filter_by(project_id=project.id).delete()
    db.query(DriftReport).filter_by(project_id=project.id).delete()
    db.query(ScheduledJob).filter_by(project_id=project.id).delete()
    db.query(ProductionTrace).filter_by(project_id=project.id).delete()
    db.delete(project)
    db.commit()


def seed(db, run_evals: bool = True, reset: bool = False) -> dict:
    """Create (or return) the demo project."""
    if reset:
        _delete_demo(db)
    existing = db.query(Project).filter_by(name=DEMO_PROJECT_NAME).first()
    if existing is not None:
        return {
            "already_seeded": True,
            "project_id": existing.id,
            "hint": "Pass reset=True (or --reset) to rebuild the demo from scratch.",
        }

    project = Project(
        name=DEMO_PROJECT_NAME,
        description=(
            "Built-in demo. Original sample corpus written for this project, "
            "evaluated by an offline deterministic BM25 RAG. Demo data is labelled as such."
        ),
        is_demo=True,
    )
    db.add(project)
    db.flush()

    for doc_id, title, text in DOCUMENTS:
        db.add(
            Document(
                project_id=project.id,
                doc_id=doc_id,
                title=title,
                source="builtin-sample",
                text=text,
                fingerprint=fingerprint(text),
                metadata_={"licence": "MIT (written for this project)"},
            )
        )
    db.flush()

    dataset = Dataset(
        project_id=project.id,
        name="library-benchmark",
        version="1.0",
        description="Benchmark covering factual, multi-hop, unanswerable, "
        "missing-context, adversarial and ambiguous questions.",
    )
    db.add(dataset)
    db.flush()

    items = []
    for question, reference, relevant, category, answerable, aliases, cohorts, difficulty in ITEMS:
        item = DatasetItem(
            dataset_id=dataset.id,
            question=question,
            reference_answer=reference,
            aliases=list(aliases or []),
            relevant_doc_ids=list(relevant or []),
            relevance_grades=dict.fromkeys(relevant or [], 1.0),
            expected_citations=[{"doc_id": doc} for doc in (relevant or [])],
            category=category,
            answerable=answerable,
            difficulty=difficulty,
            language="en",
            topic=(relevant[0] if relevant else "general"),
            cohorts=list(cohorts or []),
            human_reviewed=True,
        )
        db.add(item)
        items.append(item)
    db.flush()
    dataset.checksum = dataset_checksum(items)

    # A four-item dataset used to demonstrate the INCONCLUSIVE verdict
    # (fewer samples than the policy's minimum).
    tiny = Dataset(
        project_id=project.id,
        name="smoke-4",
        version="1.0",
        description="Tiny dataset used to demonstrate an INCONCLUSIVE gate verdict.",
    )
    db.add(tiny)
    db.flush()
    for item in items[:4]:
        db.add(
            DatasetItem(
                dataset_id=tiny.id,
                question=item.question,
                reference_answer=item.reference_answer,
                aliases=item.aliases,
                relevant_doc_ids=item.relevant_doc_ids,
                relevance_grades=item.relevance_grades,
                expected_citations=item.expected_citations,
                category=item.category,
                answerable=item.answerable,
                difficulty=item.difficulty,
                cohorts=item.cohorts,
            )
        )
    db.flush()

    apps = {}
    for key, version, description, config in VERSIONS:
        app = RagApp(
            project_id=project.id,
            name=f"library-rag-{key}",
            version_label=version,
            environment="staging",
            description=description,
            config=config,
        )
        db.add(app)
        apps[key] = app
    if not db.query(ProviderProfile).filter_by(kind="offline").first():
        db.add(
            ProviderProfile(
                name="Offline deterministic (no key)",
                kind="offline",
                role="judge",
                model="offline-deterministic",
                is_default=True,
                price_source="free",
            )
        )
    db.commit()

    out: dict = {
        "project_id": project.id,
        "dataset_id": dataset.id,
        "tiny_dataset_id": tiny.id,
        "apps": {k: v.id for k, v in apps.items()},
        "runs": {},
    }
    if not run_evals:
        return out

    run_ids: dict[str, int] = {}
    for key, app in apps.items():
        run = EvaluationRun(
            app_id=app.id, dataset_id=dataset.id, mode="end_to_end", status="queued", idempotency_key=f"seed-{key}"
        )
        db.add(run)
        db.commit()
        execute_run(db, run.id)
        run_ids[key] = run.id
        out["runs"][key] = run.id

    tiny_run = EvaluationRun(
        app_id=apps["candidate"].id, dataset_id=tiny.id, mode="end_to_end", status="queued", idempotency_key="seed-tiny"
    )
    db.add(tiny_run)
    db.commit()
    execute_run(db, tiny_run.id)
    out["runs"]["tiny"] = tiny_run.id
    run_ids["tiny"] = tiny_run.id

    policy = GatePolicy(
        project_id=project.id,
        name="release-gate-demo",
        version=1,
        description="Demo policy: quality floors, a relative regression limit "
        "against the approved baseline, and cost/latency warnings.",
        baseline_run_id=run_ids["baseline"],
        rules=DEFAULT_POLICY_RULES,
        min_samples=5,
    )
    db.add(policy)
    db.commit()
    out["policy_id"] = policy.id

    out["gate_evaluations"] = {}
    for key in ("candidate", "degraded", "tiny"):
        evaluation = evaluate_and_store(db, policy, run_ids[key])
        out["gate_evaluations"][key] = {
            "id": evaluation.id,
            "verdict": evaluation.verdict,
            "summary": evaluation.summary,
        }
    return out


def _run_view(db, run: EvaluationRun) -> RunView:
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


def evaluate_and_store(
    db, policy: GatePolicy, candidate_run_id: int, baseline_run_id: int | None = None
) -> GateEvaluation:
    """Evaluate a candidate against a policy and persist the audit record."""
    candidate = db.get(EvaluationRun, candidate_run_id)
    if candidate is None:
        raise ValueError(f"run {candidate_run_id} not found")
    baseline_id = baseline_run_id or policy.baseline_run_id
    baseline = db.get(EvaluationRun, baseline_id) if baseline_id else None
    result = evaluate_gate(
        policy.rules,
        policy.min_samples,
        _run_view(db, candidate),
        _run_view(db, baseline) if baseline is not None else None,
    )
    evaluation = GateEvaluation(
        policy_id=policy.id,
        candidate_run_id=candidate_run_id,
        baseline_run_id=baseline_id,
        verdict=result["verdict"],
        checks=result["checks"],
        summary=result["summary"],
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed the RAG Quality Monitor demo project")
    parser.add_argument("--db", default=None, help="database URL (defaults to RQM_DATABASE_URL)")
    parser.add_argument("--no-run", action="store_true", help="only create the project, do not evaluate")
    parser.add_argument("--reset", action="store_true", help="delete an existing demo first")
    args = parser.parse_args()
    if args.db:
        import os

        os.environ["RQM_DATABASE_URL"] = args.db
    init_db()
    db = SessionLocal()
    try:
        result = seed(db, run_evals=not args.no_run, reset=args.reset)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
