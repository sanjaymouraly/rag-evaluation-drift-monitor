"""Evaluation package: orchestration, aggregation and optional LLM judging."""

from __future__ import annotations

from .aggregate import aggregate_results, percentile_summary
from .judge import JUDGE_LIMITATION, RUBRIC_VERSION, RUBRICS, judge_metric_summary, run_judge
from .orchestrator import (
    corpus_manifest,
    dataset_checksum,
    execute_run,
    score_item,
    submit_run,
)

__all__ = [
    "JUDGE_LIMITATION",
    "RUBRICS",
    "RUBRIC_VERSION",
    "aggregate_results",
    "corpus_manifest",
    "dataset_checksum",
    "execute_run",
    "judge_metric_summary",
    "percentile_summary",
    "run_judge",
    "score_item",
    "submit_run",
]
