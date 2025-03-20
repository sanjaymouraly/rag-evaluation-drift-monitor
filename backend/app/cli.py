"""Command line interface.

::

    python -m app.cli init                     create the database
    python -m app.cli serve --port 8000        start the API server
    python -m app.cli seed --reset             build the demo project
    python -m app.cli eval --app 2 --dataset 1 run an evaluation
    python -m app.cli gate --policy 1 --candidate 4   release gate (exit codes!)
    python -m app.cli compare --runs 2,3
    python -m app.cli drift --baseline 2 --candidate 4
    python -m app.cli report --run 2 --format markdown --out report.md
    python -m app.cli metrics                  list every metric and its provenance
    python -m app.cli providers list|test

Exit codes of ``gate``:
    0 = PASS, 1 = FAIL, 2 = INCONCLUSIVE, 3 = usage/error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import settings
from .db import SessionLocal, init_db
from .gates import RunView, evaluate_gate
from .models import (
    Dataset,
    EvaluationRun,
    GateEvaluation,
    GatePolicy,
    ProviderProfile,
    RagApp,
    RunResult,
)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INCONCLUSIVE = 2
EXIT_ERROR = 3


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


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


# ------------------------------------------------------------------ commands


def cmd_init(args) -> int:
    init_db()
    print(f"database ready: {settings.database_url.split('://')[0]}://…")
    return EXIT_PASS


def cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload, workers=1)
    return EXIT_PASS


def cmd_seed(args) -> int:
    from .seed import seed

    init_db()
    db = SessionLocal()
    try:
        _print(seed(db, run_evals=not args.no_run, reset=args.reset))
    finally:
        db.close()
    return EXIT_PASS


def cmd_eval(args) -> int:
    from .evaluation import execute_run

    init_db()
    db = SessionLocal()
    try:
        run = EvaluationRun(app_id=args.app, dataset_id=args.dataset, mode=args.mode, status="queued")
        db.add(run)
        db.commit()
        db.refresh(run)
        execute_run(db, run.id)
        db.refresh(run)
        metrics = (run.metrics or {}).get("metrics", {})
        summary = {k: {"value": v.get("value"), "n": v.get("n"), "kind": v.get("kind")} for k, v in metrics.items()}
        _print({"run_id": run.id, "status": run.status, "error": run.error, "metrics": summary})
        return EXIT_PASS if run.status == "completed" else EXIT_FAIL
    finally:
        db.close()


def cmd_gate(args) -> int:
    init_db()
    db = SessionLocal()
    try:
        policy = db.get(GatePolicy, args.policy)
        if policy is None:
            print(f"policy {args.policy} not found", file=sys.stderr)
            return EXIT_ERROR
        candidate = db.get(EvaluationRun, args.candidate)
        if candidate is None:
            print(f"candidate run {args.candidate} not found", file=sys.stderr)
            return EXIT_ERROR
        if candidate.status != "completed":
            print(f"candidate run status is '{candidate.status}', not completed", file=sys.stderr)
            return EXIT_ERROR
        baseline_id = args.baseline or policy.baseline_run_id
        baseline = db.get(EvaluationRun, baseline_id) if baseline_id else None
        result = evaluate_gate(
            policy.rules,
            policy.min_samples,
            _run_view(db, candidate),
            _run_view(db, baseline) if baseline is not None else None,
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
        payload = {
            "verdict": result["verdict"],
            "summary": result["summary"],
            "checks": result["checks"],
            "candidate_run_id": candidate.id,
            "baseline_run_id": baseline_id,
            "evaluation_id": evaluation.id,
        }
        if args.out:
            with Path(args.out).open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, default=str)
        if args.json:
            _print(payload)
        else:
            print(f"{result['verdict']}: {result['summary']}")
            for check in result["checks"]:
                print(f"  [{check['status']:<12}] {check['label']} — {check['evidence']}")
        return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL, "INCONCLUSIVE": EXIT_INCONCLUSIVE}[result["verdict"]]
    finally:
        db.close()


def cmd_compare(args) -> int:
    init_db()
    db = SessionLocal()
    try:
        ids = [int(x) for x in args.runs.split(",") if x.strip()]
        runs = [db.get(EvaluationRun, i) for i in ids]
        if any(r is None for r in runs):
            print("one or more runs do not exist", file=sys.stderr)
            return EXIT_ERROR
        metrics = [(r.metrics or {}).get("metrics", {}) or {} for r in runs]
        keys = sorted({k for m in metrics for k in m})
        table = {}
        for key in keys:
            table[key] = [
                {
                    "run_id": r.id,
                    "app": (db.get(RagApp, r.app_id).version_label if db.get(RagApp, r.app_id) else None),
                    "value": (m.get(key) or {}).get("value"),
                    "n": (m.get(key) or {}).get("n"),
                }
                for r, m in zip(runs, metrics, strict=True)
            ]
        _print({"runs": [r.id for r in runs], "same_dataset": len({r.dataset_id for r in runs}) == 1, "metrics": table})
        return EXIT_PASS
    finally:
        db.close()


def cmd_drift(args) -> int:
    from .drift import analyse

    init_db()
    db = SessionLocal()
    try:
        baseline = db.get(EvaluationRun, args.baseline)
        candidate = db.get(EvaluationRun, args.candidate)
        if baseline is None or candidate is None:
            print("baseline or candidate run does not exist", file=sys.stderr)
            return EXIT_ERROR

        def rows(run_id):
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
                for r in db.query(RunResult).filter_by(run_id=run_id).all()
            ]

        signals, hypotheses = analyse(baseline, candidate, rows(baseline.id), rows(candidate.id))
        _print(
            {
                "signals": signals,
                "hypotheses": hypotheses,
                "disclaimer": "Drift is a distribution change, not proof of a quality regression.",
            }
        )
        return EXIT_PASS
    finally:
        db.close()


def cmd_report(args) -> int:
    from .reports import run_to_dict, to_ci_summary, to_csv, to_html, to_markdown

    init_db()
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, args.run)
        if run is None:
            print(f"run {args.run} not found", file=sys.stderr)
            return EXIT_ERROR
        results = db.query(RunResult).filter_by(run_id=run.id).order_by(RunResult.id).all()
        report = run_to_dict(run, db.get(RagApp, run.app_id), db.get(Dataset, run.dataset_id), results)
        if args.format == "json":
            body = json.dumps(report, indent=2, default=str)
        elif args.format == "csv":
            body = to_csv(report)
        elif args.format == "html":
            body = to_html(report)
        elif args.format == "ci":
            body = json.dumps(to_ci_summary(report), indent=2, default=str)
        else:
            body = to_markdown(report)
        if args.out:
            with Path(args.out).open("w", encoding="utf-8") as handle:
                handle.write(body)
            print(f"report written to {args.out}")
        else:
            print(body)
        return EXIT_PASS
    finally:
        db.close()


def cmd_metrics(args) -> int:
    from .metrics import metric_catalogue

    _print({"metrics": metric_catalogue()})
    return EXIT_PASS


def cmd_providers(args) -> int:
    from .providers import ProviderConfig, build_provider

    init_db()
    db = SessionLocal()
    try:
        if args.action == "list":
            _print(
                [
                    {
                        "id": p.id,
                        "name": p.name,
                        "kind": p.kind,
                        "role": p.role,
                        "model": p.model,
                        "has_key": bool(p.api_key),
                        "enabled": p.enabled,
                    }
                    for p in db.query(ProviderProfile).all()
                ]
            )
            return EXIT_PASS
        profile = db.get(ProviderProfile, args.id)
        if profile is None:
            print(f"provider {args.id} not found", file=sys.stderr)
            return EXIT_ERROR
        result = build_provider(ProviderConfig.from_profile(profile)).test_connection()
        _print(result)
        return EXIT_PASS if result.get("ok") else EXIT_FAIL
    finally:
        db.close()


# -------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ragm", description="RAG Quality Monitor CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database").set_defaults(func=cmd_init)

    serve = sub.add_parser("serve", help="start the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    seed = sub.add_parser("seed", help="create the demo project")
    seed.add_argument("--no-run", action="store_true")
    seed.add_argument("--reset", action="store_true")
    seed.set_defaults(func=cmd_seed)

    evaluate = sub.add_parser("eval", help="run an evaluation")
    evaluate.add_argument("--app", type=int, required=True)
    evaluate.add_argument("--dataset", type=int, required=True)
    evaluate.add_argument("--mode", default="end_to_end", choices=["end_to_end", "retrieval_only", "generation_only"])
    evaluate.set_defaults(func=cmd_eval)

    gate = sub.add_parser("gate", help="evaluate a release gate (exit code 0/1/2)")
    gate.add_argument("--policy", type=int, required=True)
    gate.add_argument("--candidate", type=int, required=True)
    gate.add_argument("--baseline", type=int, default=None)
    gate.add_argument("--json", action="store_true", help="print the full JSON result")
    gate.add_argument("--out", default=None, help="write the JSON result to a file")
    gate.set_defaults(func=cmd_gate)

    compare = sub.add_parser("compare", help="compare several runs")
    compare.add_argument("--runs", required=True, help="comma separated run ids")
    compare.set_defaults(func=cmd_compare)

    drift = sub.add_parser("drift", help="drift analysis between two runs")
    drift.add_argument("--baseline", type=int, required=True)
    drift.add_argument("--candidate", type=int, required=True)
    drift.set_defaults(func=cmd_drift)

    report = sub.add_parser("report", help="export a run report")
    report.add_argument("--run", type=int, required=True)
    report.add_argument("--format", default="json", choices=["json", "csv", "markdown", "html", "ci"])
    report.add_argument("--out", default=None)
    report.set_defaults(func=cmd_report)

    sub.add_parser("metrics", help="list the metric catalogue").set_defaults(func=cmd_metrics)

    providers = sub.add_parser("providers", help="list or test provider profiles")
    providers.add_argument("action", choices=["list", "test"])
    providers.add_argument("--id", type=int, default=None)
    providers.set_defaults(func=cmd_providers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - the CLI reports failures clearly
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
