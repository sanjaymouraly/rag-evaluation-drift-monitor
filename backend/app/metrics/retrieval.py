"""Retrieval metrics.

All of these need *relevance labels* (the benchmark item must declare which
document ids are relevant). When those labels are missing the metric returns
``None`` with a reason instead of scoring zero — a missing label is missing
evidence, not a failure.
"""

from __future__ import annotations

import math

from .base import DETERMINISTIC, OPERATIONAL, MetricContext, MetricResult

# ---------------------------------------------------------------- primitives


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k retrieved items that are relevant."""
    if not relevant:
        raise ValueError("precision_at_k requires non-empty relevance labels")
    topk = retrieved[:k]
    if not topk:
        return 0.0
    return sum(1 for d in topk if d in relevant) / len(topk)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the relevant items found in the top-k."""
    if not relevant:
        raise ValueError("recall_at_k requires non-empty relevance labels")
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 when at least one relevant item is in the top-k."""
    if not relevant:
        raise ValueError("hit_rate_at_k requires non-empty relevance labels")
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant item (0 when none is retrieved)."""
    if not relevant:
        raise ValueError("reciprocal_rank requires non-empty relevance labels")
    for i, d in enumerate(retrieved, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def average_precision(retrieved: list[str], relevant: set[str]) -> float:
    """Mean of the precision values at every relevant rank, divided by |relevant|."""
    if not relevant:
        raise ValueError("average_precision requires non-empty relevance labels")
    hits, precisions, seen = 0, [], set()
    for i, d in enumerate(retrieved, start=1):
        if d in relevant and d not in seen:
            hits += 1
            precisions.append(hits / i)
        seen.add(d)
    return sum(precisions) / len(relevant) if precisions else 0.0


def ndcg_at_k(retrieved: list[str], grades: dict[str, float], k: int) -> float:
    """Normalised discounted cumulative gain for graded relevance."""
    if not grades or max(grades.values(), default=0.0) <= 0:
        raise ValueError("ndcg_at_k requires positive graded relevance")

    def dcg(ids: list[str]) -> float:
        return sum((2 ** grades.get(d, 0.0) - 1) / math.log2(i + 1) for i, d in enumerate(ids, start=1))

    ideal = sorted(grades, key=lambda d: (-grades[d], d))[:k]
    idcg = dcg(ideal)
    if idcg <= 0:
        return 0.0
    return dcg(retrieved[:k]) / idcg


def context_precision(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Share of retrieved context that is relevant (Ragas-style context precision)."""
    if not relevant:
        raise ValueError("context_precision requires non-empty relevance labels")
    topk = retrieved[:k]
    if not topk:
        return 0.0
    return sum(1 for d in topk if d in relevant) / len(topk)


def context_recall(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Share of the relevant documents that appear in the retrieved context."""
    if not relevant:
        raise ValueError("context_recall requires non-empty relevance labels")
    return len(set(retrieved[:k]) & relevant) / len(relevant)


# ------------------------------------------------------------------ metrics


def _grades(ctx: MetricContext) -> dict[str, float]:
    grades = {str(k): float(v) for k, v in (ctx.relevance_grades or {}).items()}
    for d in ctx.relevance_set:
        grades.setdefault(d, 1.0)
    return grades


def _retrieval_metric(fn, requires: tuple):
    def _impl(ctx: MetricContext) -> MetricResult:
        if ctx.mode == "generation_only":
            return MetricResult.missing("retrieval is bypassed in generation_only mode")
        relevant = ctx.relevance_set
        if not relevant:
            return MetricResult.missing("no relevance labels for this item")
        retrieved = ctx.retrieved_doc_ids
        value = fn(retrieved, relevant)
        return MetricResult(
            value=round(float(value), 6),
            kind=DETERMINISTIC,
            evidence={
                "retrieved": retrieved[:10],
                "relevant": sorted(relevant),
                "k": requires[-1] if requires else None,
            },
        )

    return _impl


def _ndcg(ctx: MetricContext) -> MetricResult:
    if ctx.mode == "generation_only":
        return MetricResult.missing("retrieval is bypassed in generation_only mode")
    grades = _grades(ctx)
    if not grades:
        return MetricResult.missing("no graded relevance labels for this item")
    value = ndcg_at_k(ctx.retrieved_doc_ids, grades, 5)
    return MetricResult(
        value=round(float(value), 6),
        kind=DETERMINISTIC,
        evidence={"grades": grades, "retrieved": ctx.retrieved_doc_ids[:10]},
    )


def _empty_retrieval(ctx: MetricContext) -> MetricResult:
    return MetricResult(
        value=1.0 if not ctx.retrieved else 0.0, kind=OPERATIONAL, evidence={"n_retrieved": len(ctx.retrieved)}
    )


def _duplicate_chunk_rate(ctx: MetricContext) -> MetricResult:
    ids = ctx.retrieved_chunk_ids
    if not ids:
        return MetricResult(value=0.0, kind=OPERATIONAL, evidence={"n_retrieved": 0})
    dup = 1 - len(set(ids)) / len(ids)
    return MetricResult(value=round(dup, 6), kind=OPERATIONAL, evidence={"n_retrieved": len(ids)})


def _missing_source_rate(ctx: MetricContext) -> MetricResult:
    """Share of the labelled relevant documents that are absent from the corpus."""
    if not ctx.relevance_set:
        return MetricResult.missing("no relevance labels for this item")
    corpus = set(ctx.corpus_doc_ids)
    if not corpus:
        return MetricResult.missing("corpus not loaded")
    missing = sorted(ctx.relevance_set - corpus)
    return MetricResult(
        value=round(len(missing) / len(ctx.relevance_set), 6), kind=OPERATIONAL, evidence={"missing_doc_ids": missing}
    )


def _retrieval_coverage(ctx: MetricContext) -> MetricResult:
    """Distinct relevant documents found anywhere in the retrieved list."""
    if not ctx.relevance_set:
        return MetricResult.missing("no relevance labels for this item")
    covered = set(ctx.retrieved_doc_ids) & ctx.relevance_set
    return MetricResult(
        value=round(len(covered) / len(ctx.relevance_set), 6),
        kind=DETERMINISTIC,
        evidence={"covered": sorted(covered), "relevant": sorted(ctx.relevance_set)},
    )


RETRIEVAL_METRICS = [
    (
        "precision_at_5",
        "Share of the 5 retrieved documents that are labelled relevant.",
        ("relevance_labels", "retrieved_context", "k=5"),
        _retrieval_metric(lambda r, rel: precision_at_k(r, rel, 5), ("relevance_labels", "retrieved_context", 5)),
    ),
    (
        "recall_at_5",
        "Share of the labelled relevant documents found in the top 5.",
        ("relevance_labels", "retrieved_context", "k=5"),
        _retrieval_metric(lambda r, rel: recall_at_k(r, rel, 5), ("relevance_labels", "retrieved_context", 5)),
    ),
    (
        "recall_at_3",
        "Share of the labelled relevant documents found in the top 3.",
        ("relevance_labels", "retrieved_context", "k=3"),
        _retrieval_metric(lambda r, rel: recall_at_k(r, rel, 3), ("relevance_labels", "retrieved_context", 3)),
    ),
    (
        "hit_at_5",
        "1.0 when at least one relevant document is in the top 5.",
        ("relevance_labels", "retrieved_context", "k=5"),
        _retrieval_metric(lambda r, rel: hit_rate_at_k(r, rel, 5), ("relevance_labels", "retrieved_context", 5)),
    ),
    (
        "mrr",
        "Mean reciprocal rank of the first relevant document.",
        ("relevance_labels", "retrieved_context"),
        _retrieval_metric(reciprocal_rank, ("relevance_labels", "retrieved_context")),
    ),
    (
        "map",
        "Mean average precision over the retrieved ranking.",
        ("relevance_labels", "retrieved_context"),
        _retrieval_metric(average_precision, ("relevance_labels", "retrieved_context")),
    ),
    (
        "ndcg_at_5",
        "Normalised discounted cumulative gain of the top 5 (graded relevance supported).",
        ("graded_relevance", "retrieved_context", "k=5"),
        _ndcg,
    ),
    (
        "context_precision",
        "Share of the retrieved context that is relevant.",
        ("relevance_labels", "retrieved_context"),
        _retrieval_metric(lambda r, rel: context_precision(r, rel, 5), ("relevance_labels", "retrieved_context")),
    ),
    (
        "context_recall",
        "Share of the relevant documents present in the retrieved context.",
        ("relevance_labels", "retrieved_context"),
        _retrieval_metric(lambda r, rel: context_recall(r, rel, 5), ("relevance_labels", "retrieved_context")),
    ),
    (
        "retrieval_coverage",
        "Share of relevant documents found anywhere in the retrieved list.",
        ("relevance_labels", "retrieved_context"),
        _retrieval_coverage,
    ),
    ("empty_retrieval", "1.0 when the retriever returned nothing.", ("retrieved_context",), _empty_retrieval),
    (
        "duplicate_chunk_rate",
        "Share of retrieved chunks that are duplicates.",
        ("retrieved_context",),
        _duplicate_chunk_rate,
    ),
    (
        "missing_source_rate",
        "Share of labelled relevant documents missing from the corpus.",
        ("relevance_labels", "corpus"),
        _missing_source_rate,
    ),
]
