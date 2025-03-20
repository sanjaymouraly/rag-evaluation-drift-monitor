"""Metric registry.

Importing this package registers every built-in metric. Third-party metrics
can be added at runtime with :func:`register_metric`.
"""

from __future__ import annotations

from .answer import ANSWER_METRICS
from .base import (
    DETERMINISTIC,
    EMBEDDING_BASED,
    HEURISTIC,
    JUDGE,
    KIND_DESCRIPTIONS,
    OPERATIONAL,
    REFERENCE_BASED,
    MetricContext,
    MetricResult,
    MetricSpec,
    all_metrics,
    get_metric,
    metric_catalogue,
    register_metric,
)
from .citation import CITATION_METRICS
from .operational import OPERATIONAL_METRICS
from .retrieval import RETRIEVAL_METRICS
from .text import (
    content_tokens,
    normalize_answer,
    normalize_soft,
    numbers_in,
    sentences,
    tokenize,
)


def _install() -> None:
    for name, description, requires, fn in (
        *RETRIEVAL_METRICS,
        *ANSWER_METRICS,
        *CITATION_METRICS,
        *OPERATIONAL_METRICS,
    ):
        register_metric(
            MetricSpec(name=name, kind=_kind_for(name), requires=tuple(requires), fn=fn, description=description)
        )


#: Explicit provenance per metric name. Anything not listed here is an
#: authoring error and is caught by the test suite.
METRIC_KINDS: dict[str, str] = {
    # retrieval — exact formulas over relevance labels
    "precision_at_5": DETERMINISTIC,
    "recall_at_5": DETERMINISTIC,
    "recall_at_3": DETERMINISTIC,
    "hit_at_5": DETERMINISTIC,
    "mrr": DETERMINISTIC,
    "map": DETERMINISTIC,
    "ndcg_at_5": DETERMINISTIC,
    "context_precision": DETERMINISTIC,
    "context_recall": DETERMINISTIC,
    "retrieval_coverage": DETERMINISTIC,
    # answer — reference based
    "exact_match": REFERENCE_BASED,
    "normalized_match": REFERENCE_BASED,
    "token_f1": REFERENCE_BASED,
    "completeness": REFERENCE_BASED,
    # answer — heuristics
    "faithfulness": HEURISTIC,
    "hallucination_rate": HEURISTIC,
    "answer_relevancy": HEURISTIC,
    # answer — deterministic
    "claim_support_rate": DETERMINISTIC,
    "correct_abstention": DETERMINISTIC,
    "over_abstention": DETERMINISTIC,
    "contradiction_rate": DETERMINISTIC,
    "empty_answer": DETERMINISTIC,
    # embeddings
    "semantic_similarity": EMBEDDING_BASED,
    # citations
    "citation_presence": DETERMINISTIC,
    "citation_structural_valid": DETERMINISTIC,
    "citation_support": DETERMINISTIC,
    "citation_unsupported_rate": DETERMINISTIC,
    "citation_precision": DETERMINISTIC,
    "citation_doc_recall": DETERMINISTIC,
    "claim_attribution": DETERMINISTIC,
    "citation_coverage": DETERMINISTIC,
    # operational
    "latency_ms": OPERATIONAL,
    "retrieval_latency_ms": OPERATIONAL,
    "generation_latency_ms": OPERATIONAL,
    "input_tokens": OPERATIONAL,
    "output_tokens": OPERATIONAL,
    "estimated_cost_usd": OPERATIONAL,
    "request_error": OPERATIONAL,
    "empty_retrieval": OPERATIONAL,
    "duplicate_chunk_rate": OPERATIONAL,
    "missing_source_rate": OPERATIONAL,
}


def _kind_for(name: str) -> str:
    return METRIC_KINDS[name]


_install()

__all__ = [
    "DETERMINISTIC",
    "EMBEDDING_BASED",
    "HEURISTIC",
    "JUDGE",
    "KIND_DESCRIPTIONS",
    "OPERATIONAL",
    "REFERENCE_BASED",
    "MetricContext",
    "MetricResult",
    "MetricSpec",
    "all_metrics",
    "content_tokens",
    "get_metric",
    "metric_catalogue",
    "normalize_answer",
    "normalize_soft",
    "numbers_in",
    "register_metric",
    "sentences",
    "tokenize",
]
