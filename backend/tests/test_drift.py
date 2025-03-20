"""Drift statistics and run-to-run drift analysis."""

from __future__ import annotations

import pytest

from app.drift import analyse, embedding_drift, jsd_from_counts, ks_test, psi, psi_categorical
from app.drift.statistics import control_chart, interpret_psi


def test_psi_is_zero_for_identical_distributions():
    sample = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert psi(sample, sample) == pytest.approx(0.0, abs=1e-9)


def test_psi_is_large_for_a_shifted_distribution():
    baseline = [0.10] * 20
    candidate = [0.90] * 20
    assert psi(baseline, candidate) > 0.25


def test_psi_needs_enough_samples():
    assert psi([0.1, 0.2], [0.3, 0.4]) is None
    assert psi([0.1] * 10, [0.2] * 10) is not None


def test_psi_handles_discrete_metrics():
    baseline = [1.0] * 10 + [0.0] * 10
    candidate = [0.0] * 10 + [1.0] * 10
    value = psi(baseline, candidate)
    assert value is not None


def test_psi_categorical_detects_a_mix_change():
    baseline = ["a"] * 10 + ["b"] * 10
    candidate = ["a"] * 20
    assert psi_categorical(baseline, candidate) > 0.1
    assert psi_categorical(baseline, baseline) == pytest.approx(0.0, abs=1e-6)


def test_ks_test_reports_sample_sizes():
    result = ks_test([0.1] * 10, [0.5] * 10)
    assert result["n_baseline"] == 10
    assert result["n_candidate"] == 10
    assert result["statistic"] is not None
    assert ks_test([0.1], [0.5])["statistic"] is None


def test_jsd_is_zero_for_identical_counts():
    assert jsd_from_counts({"a": 5, "b": 5}, {"a": 5, "b": 5}) == pytest.approx(0.0, abs=1e-9)


def test_jsd_grows_for_disjoint_distributions():
    value = jsd_from_counts({"a": 10}, {"b": 10})
    assert value > 0.6


def test_embedding_drift_refuses_incomparable_spaces():
    result = embedding_drift([[1.0, 0.0]], [[1.0, 0.0, 0.0]])
    assert result["comparable"] is False
    assert "not comparable" in result["reason"]


def test_embedding_drift_reports_centroid_shift():
    baseline = [[1.0, 0.0]] * 5
    candidate = [[0.0, 1.0]] * 5
    result = embedding_drift(baseline, candidate)
    assert result["comparable"] is True
    assert result["centroid_shift"] > 0.5


def test_control_chart_flags_outliers():
    chart = control_chart([1.0] * 20 + [50.0])
    assert chart["outliers"] == [20]
    assert chart["mean"] is not None


def test_interpret_psi_labels():
    assert "no significant" in interpret_psi(0.01)
    assert "moderate" in interpret_psi(0.15)
    assert "large" in interpret_psi(0.4)
    assert "insufficient" in interpret_psi(None)


def test_analyse_produces_signals_and_labelled_hypotheses():
    class FakeRun:
        def __init__(self, config):
            self.config_snapshot = config

    baseline_run = FakeRun(
        {
            "app_config": {"retriever": "bm25", "chunk_chars": 600, "top_k": 5},
            "corpus_manifest": [{"doc_id": "a", "revision": 1, "fingerprint": "aaa"}],
            "dataset_checksum": "abc",
            "n_chunks": 12,
            "chunk_stats": {"n_chunks": 12},
        }
    )
    candidate_run = FakeRun(
        {
            "app_config": {"retriever": "degraded_keyword", "chunk_chars": 300, "top_k": 5},
            "corpus_manifest": [{"doc_id": "a", "revision": 2, "fingerprint": "bbb"}],
            "dataset_checksum": "abc",
            "n_chunks": 20,
            "chunk_stats": {"n_chunks": 20},
        }
    )

    def _rows(recall: float, docs: list[str]):
        return [
            {
                "item_id": i,
                "question": f"q{i}",
                "category": "factual",
                "cohorts": ["core"],
                "metrics": {"recall_at_5": recall, "token_f1": 0.5},
                "retrieved": [{"doc_id": d, "score": 1.0} for d in docs],
                "latency_ms": 10.0,
                "input_tokens": 100,
                "output_tokens": 20,
            }
            for i in range(10)
        ]

    signals, hypotheses = analyse(baseline_run, candidate_run, _rows(1.0, ["a"] * 5), _rows(0.0, ["z"] * 5))
    assert "recall_at_5" in signals
    assert signals["recall_at_5"]["psi"] is not None
    assert signals["corpus"]["changed_doc_ids"] == ["a"]
    assert signals["config_diff"]["changed_keys"]
    assert any("HYPOTHESIS" in h for h in hypotheses)
    # Every cause hypothesis must be explicitly labelled as unproven.
    for hypothesis in hypotheses:
        assert hypothesis.startswith(("HYPOTHESIS (unproven):", "FINDING:"))
