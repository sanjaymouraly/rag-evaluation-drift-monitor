"""Release gate tests.

These cover the three verdicts, the "missing evidence must not pass" rule,
paired statistics and per-scope (category/cohort) rules.
"""

from __future__ import annotations

import pytest

from app.gates import (
    DEFAULT_POLICY_RULES,
    FAIL,
    INCONCLUSIVE,
    PASS,
    RunView,
    bootstrap_ci,
    evaluate_gate,
)


def _view(run_id: int, metrics: dict, results: list[dict]) -> RunView:
    return RunView(run_id=run_id, metrics=metrics, results=results)


def _result(item_id: int, category: str, metrics: dict, cohorts: list[str] | None = None) -> dict:
    return {
        "item_id": item_id,
        "question": f"q{item_id}",
        "category": category,
        "cohorts": cohorts or [],
        "metrics": metrics,
    }


def test_min_rule_passes_and_fails():
    candidate = _view(1, {"recall_at_5": {"value": 0.9, "n": 20}}, [])
    result = evaluate_gate([{"metric": "recall_at_5", "type": "min", "threshold": 0.8}], 5, candidate)
    assert result["verdict"] == PASS
    candidate = _view(1, {"recall_at_5": {"value": 0.5, "n": 20}}, [])
    result = evaluate_gate([{"metric": "recall_at_5", "type": "min", "threshold": 0.8}], 5, candidate)
    assert result["verdict"] == FAIL


def test_max_rule():
    candidate = _view(1, {"latency_p95_ms": {"value": 100.0, "n": 20}}, [])
    result = evaluate_gate([{"metric": "latency_p95_ms", "type": "max", "threshold": 500}], 5, candidate)
    assert result["verdict"] == PASS
    candidate = _view(1, {"latency_p95_ms": {"value": 900.0, "n": 20}}, [])
    result = evaluate_gate([{"metric": "latency_p95_ms", "type": "max", "threshold": 500}], 5, candidate)
    assert result["verdict"] == FAIL


def test_missing_metric_is_inconclusive_not_pass():
    candidate = _view(1, {}, [])
    result = evaluate_gate([{"metric": "recall_at_5", "type": "min", "threshold": 0.8}], 5, candidate)
    assert result["verdict"] == INCONCLUSIVE
    assert "Insufficient evidence" in result["checks"][0]["evidence"]


def test_too_few_samples_is_inconclusive():
    candidate = _view(1, {"recall_at_5": {"value": 0.95, "n": 3}}, [])
    result = evaluate_gate([{"metric": "recall_at_5", "type": "min", "threshold": 0.8}], 5, candidate)
    assert result["verdict"] == INCONCLUSIVE
    assert "below the required minimum" in result["checks"][0]["evidence"]


def test_relative_rule_without_a_baseline_is_inconclusive():
    candidate = _view(1, {"recall_at_5": {"value": 0.9, "n": 20}}, [])
    result = evaluate_gate([{"metric": "recall_at_5", "type": "max_drop", "threshold": 0.05}], 5, candidate, None)
    assert result["verdict"] == INCONCLUSIVE
    assert "baseline" in result["checks"][0]["evidence"]


def test_relative_rule_detects_a_paired_regression():
    baseline = _view(
        1, {"recall_at_5": {"value": 0.9, "n": 10}}, [_result(i, "factual", {"recall_at_5": 1.0}) for i in range(10)]
    )
    candidate = _view(
        2, {"recall_at_5": {"value": 0.4, "n": 10}}, [_result(i, "factual", {"recall_at_5": 0.0}) for i in range(10)]
    )
    result = evaluate_gate(
        [{"metric": "recall_at_5", "type": "max_drop", "threshold": 0.05, "tolerance": 0.01}], 5, candidate, baseline
    )
    assert result["verdict"] == FAIL
    check = result["checks"][0]
    assert check["observed_change"] == pytest.approx(0.5)
    assert check["ci"] is not None
    assert check["p_value"] is not None


def test_relative_rule_tolerates_noise():
    # Differences of +-0.05 with a tolerance of 0.1 are noise, not a regression.
    baseline = _view(
        1, {"recall_at_5": {"value": 0.9, "n": 10}}, [_result(i, "factual", {"recall_at_5": 1.0}) for i in range(10)]
    )
    candidate = _view(
        2, {"recall_at_5": {"value": 0.85, "n": 10}}, [_result(i, "factual", {"recall_at_5": 0.9}) for i in range(10)]
    )
    result = evaluate_gate(
        [{"metric": "recall_at_5", "type": "max_drop", "threshold": 0.02, "tolerance": 0.1}], 5, candidate, baseline
    )
    assert result["verdict"] == PASS
    assert "consistent with noise" in result["checks"][0]["evidence"]


def test_warning_severity_does_not_fail_the_gate():
    candidate = _view(1, {"latency_p95_ms": {"value": 9000.0, "n": 20}}, [])
    result = evaluate_gate(
        [{"metric": "latency_p95_ms", "type": "max", "threshold": 500, "severity": "warn"}], 5, candidate
    )
    assert result["verdict"] == PASS
    assert "warnings" in result["summary"]


def test_scope_rule_only_looks_at_the_selected_category():
    results = [_result(i, "factual", {"recall_at_5": 1.0}) for i in range(10)] + [
        _result(100 + i, "multi-hop", {"recall_at_5": 0.0}) for i in range(5)
    ]
    candidate = _view(1, {"recall_at_5": {"value": 0.5, "n": 15}}, results)
    result = evaluate_gate(
        [{"metric": "recall_at_5", "type": "min", "threshold": 0.8, "scope": {"category": "factual"}}], 5, candidate
    )
    assert result["verdict"] == PASS
    assert result["checks"][0]["observed"] == pytest.approx(1.0)
    assert result["checks"][0]["n"] == 10


def test_cohort_scope_rule():
    results = [_result(i, "factual", {"recall_at_5": 1.0}, cohorts=["core"]) for i in range(10)]
    results += [_result(100 + i, "factual", {"recall_at_5": 0.0}, cohorts=["edge"]) for i in range(5)]
    candidate = _view(1, {"recall_at_5": {"value": 0.5, "n": 15}}, results)
    result = evaluate_gate(
        [{"metric": "recall_at_5", "type": "min", "threshold": 0.8, "scope": {"cohort": "core"}}], 5, candidate
    )
    assert result["verdict"] == PASS


def test_unknown_rule_type_is_inconclusive():
    candidate = _view(1, {"recall_at_5": {"value": 0.9, "n": 20}}, [])
    result = evaluate_gate([{"metric": "recall_at_5", "type": "nonsense", "threshold": 1}], 5, candidate)
    assert result["verdict"] == INCONCLUSIVE


def test_bootstrap_ci_is_deterministic():
    diffs = [0.1, -0.2, 0.3, 0.0, 0.05]
    first = bootstrap_ci(diffs, seed=7)
    second = bootstrap_ci(diffs, seed=7)
    assert first == second
    assert first[0] <= sum(diffs) / len(diffs) <= first[1]


def test_default_policy_rules_are_valid():
    from app.gates import RULE_TYPES

    assert DEFAULT_POLICY_RULES
    for rule in DEFAULT_POLICY_RULES:
        assert rule["type"] in RULE_TYPES
        assert rule["metric"]
        assert "threshold" in rule
