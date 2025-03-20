"""Report generation: JSON, CSV, Markdown, HTML and the CI summary."""

from __future__ import annotations

import json

from app.reports import run_to_dict, to_ci_summary, to_csv, to_html, to_markdown


class _FakeResult:
    def __init__(self, index: int):
        self.item_id = index
        self.question = f"Question {index}?"
        self.category = "factual"
        self.cohorts = ["core"]
        self.answerable = True
        self.answer = "The answer | with a pipe."
        self.abstained = False
        self.retrieved = [{"chunk_id": "d::c0", "doc_id": "d", "score": 1.0, "text": "source"}]
        self.citations = [{"doc_id": "d", "chunk_id": "d::c0", "quote": "source"}]
        self.metrics = {"recall_at_5": 1.0, "token_f1": 0.5, "faithfulness": 0.9, "citation_support": 1.0}
        self.evidence = {"recall_at_5": {"kind": "deterministic"}}
        self.latency_ms = 12.5
        self.retrieval_latency_ms = 5.0
        self.generation_latency_ms = 7.5
        self.input_tokens = 10
        self.output_tokens = 20
        self.error = ""


class _FakeRun:
    id = 7
    app_id = 1
    dataset_id = 1
    mode = "end_to_end"
    status = "completed"
    progress = 100
    error = ""
    total_input_tokens = 100
    total_output_tokens = 200
    estimated_cost_usd = 0.01
    cost_is_estimate = True
    created_at = None
    finished_at = None
    metrics = {
        "n_questions": 2,
        "metrics": {
            "recall_at_5": {"value": 1.0, "n": 2, "kind": "deterministic", "std": 0.0},
            "token_f1": {"value": 0.5, "n": 2, "kind": "reference_based", "std": 0.1},
        },
        "metric_kinds": {"recall_at_5": "deterministic", "token_f1": "reference_based"},
        "by_category": {},
        "by_cohort": {},
        "latency_ms": {"p50": 12.5, "p95": 12.5, "p99": 12.5, "mean": 12.5, "n": 2},
    }
    config_snapshot = {"dataset_checksum": "abc", "eval_code_version": "1.1.0"}


class _FakeApp:
    name = "my-rag"
    version_label = "v1"


class _FakeDataset:
    name = "my-benchmark"


def _report():
    return run_to_dict(_FakeRun(), _FakeApp(), _FakeDataset(), [_FakeResult(1), _FakeResult(2)])


def test_json_report_contains_the_run_and_the_results():
    report = _report()
    assert report["schema"] == "rag-quality-monitor/run-report/v1"
    assert report["run"]["id"] == 7
    assert len(report["results"]) == 2
    assert report["results"][0]["evidence"]
    assert report["usage"]["estimated_cost_usd"] == 0.01
    assert report["usage"]["cost_is_estimate"] is True


def test_csv_report_has_a_header_and_one_row_per_result():
    csv_text = to_csv(_report())
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("run_id,item_id,category")
    assert len(lines) == 3
    assert "Question 1?" in csv_text


def test_markdown_report_lists_the_metrics_with_their_kind():
    markdown = to_markdown(_report())
    assert markdown.startswith("# Evaluation Report")
    assert "| recall_at_5 | 1.0000 | 2 | deterministic |" in markdown
    assert "reference_based" in markdown
    assert "heuristic" in markdown
    assert "not verified ground truth" in markdown


def test_markdown_report_escapes_pipes_in_answers():
    markdown = to_markdown(_report())
    assert "The answer \\| with a pipe." in markdown


def test_html_report_is_valid_and_labels_the_provenance():
    html_text = to_html(_report())
    assert html_text.startswith("<!DOCTYPE html>")
    assert "recall_at_5" in html_text
    assert "kind-deterministic" in html_text
    assert "</html>" in html_text


def test_gate_section_is_rendered():
    gate = {
        "verdict": "FAIL",
        "summary": "2 checks failed",
        "checks": [
            {
                "metric": "recall_at_5",
                "type": "min",
                "status": "FAIL",
                "observed": 0.4,
                "threshold": 0.8,
                "evidence": "below the floor",
            }
        ],
    }
    markdown = to_markdown(_report(), gate)
    assert "**Verdict: FAIL**" in markdown
    assert "below the floor" in markdown
    html_text = to_html(_report(), gate)
    assert "verdict-FAIL" in html_text


def test_ci_summary_is_machine_readable():
    gate = {
        "verdict": "PASS",
        "summary": "all good",
        "checks": [
            {
                "metric": "recall_at_5",
                "type": "min",
                "status": "PASS",
                "observed": 1.0,
                "threshold": 0.8,
                "severity": "hard",
                "evidence": "ok",
            }
        ],
    }
    summary = to_ci_summary(_report(), gate)
    assert summary["schema"] == "rag-quality-monitor/ci-summary/v1"
    assert summary["verdict"] == "PASS"
    assert summary["checks"][0]["metric"] == "recall_at_5"
    assert summary["metrics"]["recall_at_5"]["value"] == 1.0
    json.dumps(summary)  # must be serialisable
