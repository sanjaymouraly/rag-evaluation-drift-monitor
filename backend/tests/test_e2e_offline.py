"""Deterministic offline end-to-end test.

Seeds the demo, runs the evaluations, evaluates the release gate and checks the
three verdicts (PASS / FAIL / INCONCLUSIVE) and the CLI exit codes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.db import SessionLocal, init_db
from app.gates import FAIL, INCONCLUSIVE, PASS
from app.models import EvaluationRun, GateEvaluation, Project, RunResult
from app.seed import seed

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def demo():
    init_db()
    db = SessionLocal()
    try:
        result = seed(db, run_evals=True, reset=True)
        yield db, result
    finally:
        db.close()


def test_seed_creates_the_demo(demo):
    db, result = demo
    assert result["project_id"]
    project = db.get(Project, result["project_id"])
    assert project.is_demo is True
    runs = db.query(EvaluationRun).all()
    assert len(runs) >= 5
    for run in runs:
        assert run.status == "completed", run.error


def test_the_degraded_version_scores_worse(demo):
    db, result = demo
    baseline = db.get(EvaluationRun, result["runs"]["baseline"])
    degraded = db.get(EvaluationRun, result["runs"]["degraded"])
    baseline_recall = baseline.metrics["metrics"]["recall_at_5"]["value"]
    degraded_recall = degraded.metrics["metrics"]["recall_at_5"]["value"]
    assert degraded_recall < baseline_recall
    baseline_f1 = baseline.metrics["metrics"]["token_f1"]["value"]
    degraded_f1 = degraded.metrics["metrics"]["token_f1"]["value"]
    assert degraded_f1 < baseline_f1


def test_the_release_gate_blocks_the_degraded_candidate(demo):
    db, result = demo
    evaluations = {e.candidate_run_id: e for e in db.query(GateEvaluation).all()}
    candidate = evaluations[result["runs"]["candidate"]]
    degraded = evaluations[result["runs"]["degraded"]]
    tiny = evaluations[result["runs"]["tiny"]]
    assert candidate.verdict == PASS
    assert degraded.verdict == FAIL
    assert tiny.verdict == INCONCLUSIVE
    # The failing check must carry evidence.
    failing = [c for c in degraded.checks if c["status"] == "FAIL"]
    assert failing
    for check in failing:
        assert check["evidence"]
        assert check["observed"] is not None


def test_every_run_records_its_provenance(demo):
    db, _result = demo
    for run in db.query(EvaluationRun).all():
        snapshot = run.config_snapshot
        assert snapshot["dataset_checksum"]
        assert snapshot["corpus_manifest"]
        assert snapshot["eval_code_version"]
        assert snapshot["n_chunks"] > 0
        assert run.metrics["metric_kinds"]


def test_results_are_persisted_with_evidence(demo):
    db, result = demo
    results = db.query(RunResult).filter_by(run_id=result["runs"]["baseline"]).all()
    assert results
    for row in results:
        assert row.evidence
        assert "kind" in row.evidence["recall_at_5"]


def test_cli_gate_exit_codes(demo):
    """The CLI must be usable as a CI gate: 0 = pass, 1 = fail, 2 = inconclusive."""
    _db, result = demo
    policy_id = result["policy_id"]
    import os

    # The subprocess inherits RQM_DATABASE_URL from the test session, so the
    # CLI evaluates exactly the same data the test created.
    env = dict(os.environ)
    for run_key, expected in (("candidate", 0), ("degraded", 1), ("tiny", 2)):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.cli",
                "gate",
                "--policy",
                str(policy_id),
                "--candidate",
                str(result["runs"][run_key]),
            ],
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert completed.returncode == expected, (run_key, completed.stdout, completed.stderr)
        assert completed.stdout.strip()


def test_cli_gate_writes_a_machine_readable_summary(demo, tmp_path):
    _db, result = demo
    import os

    out = tmp_path / "gate.json"
    env = dict(os.environ)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "gate",
            "--policy",
            str(result["policy_id"]),
            "--candidate",
            str(result["runs"]["degraded"]),
            "--out",
            str(out),
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 1
    payload = json.loads(out.read_text())
    assert payload["verdict"] == "FAIL"
    assert payload["checks"]


def test_cli_report_and_metrics(demo):
    import os

    env = dict(os.environ)
    report = subprocess.run(
        [sys.executable, "-m", "app.cli", "report", "--run", str(1), "--format", "ci"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert report.returncode == 0
    assert json.loads(report.stdout)["schema"].startswith("rag-quality-monitor/")

    metrics = subprocess.run(
        [sys.executable, "-m", "app.cli", "metrics"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert metrics.returncode == 0
    names = {m["name"] for m in json.loads(metrics.stdout)["metrics"]}
    assert "recall_at_5" in names
