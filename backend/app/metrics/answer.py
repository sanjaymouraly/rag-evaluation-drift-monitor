"""Answer quality metrics.

Three families live here and are always reported with their provenance:

* **deterministic / reference-based** — exact match, normalised match, token F1
  and completeness are exact computations against a human reference answer.
* **heuristic** — faithfulness, answer relevancy and claim support are
  surface-overlap *estimates*. They are useful for regression signal but they
  are not verified ground truth and the platform labels them as such.
* **embedding-based** — semantic similarity, only available when an embedder is
  configured.
"""

from __future__ import annotations

from collections import Counter

from .base import (
    DETERMINISTIC,
    EMBEDDING_BASED,
    HEURISTIC,
    REFERENCE_BASED,
    MetricContext,
    MetricResult,
)
from .text import content_tokens, normalize_answer, normalize_soft, numbers_in, sentences, tokenize

SUPPORT_THRESHOLD = 0.6  # share of a claim's content tokens that must be grounded


# ---------------------------------------------------------------- primitives


def exact_match_value(prediction: str, reference: str, aliases: list[str] | None = None) -> float:
    """1.0 when the normalised answer equals the reference or an alias."""
    refs = [reference, *(aliases or [])]
    p = normalize_answer(prediction)
    if not p:
        return 0.0
    return 1.0 if any(p == normalize_answer(r) and p for r in refs) else 0.0


def normalized_match_value(prediction: str, reference: str, aliases: list[str] | None = None) -> float:
    """Like exact match but keeps articles and only collapses whitespace/case."""
    refs = [reference, *(aliases or [])]
    p = normalize_soft(prediction)
    if not p:
        return 0.0
    return 1.0 if any(p == normalize_soft(r) and p for r in refs) else 0.0


def token_f1_value(prediction: str, reference: str, aliases: list[str] | None = None) -> float:
    """Token-level F1, taking the best score over the reference and aliases."""
    refs = [reference, *(aliases or [])]
    if not refs:
        return 0.0
    return max(_token_f1_single(prediction, r) for r in refs)


def _token_f1_single(prediction: str, reference: str) -> float:
    p, r = tokenize(prediction), tokenize(reference)
    if not p and not r:
        return 1.0
    if not p or not r:
        return 0.0
    common = Counter(p) & Counter(r)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / len(p), overlap / len(r)
    return 2 * precision * recall / (precision + recall)


def token_overlap(a: str, b: str) -> float:
    """Share of A's content tokens that also occur in B."""
    ta, tb = set(content_tokens(a)), set(content_tokens(b))
    if not ta:
        return 1.0
    return len(ta & tb) / len(ta)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def claim_support(claim: str, contexts: list[str]) -> float:
    """Best grounding score of a single claim over the retrieved contexts."""
    if not contexts:
        return 0.0
    ctx_tokens = set()
    for c in contexts:
        ctx_tokens.update(content_tokens(c))
    claim_tokens = set(content_tokens(claim))
    if not claim_tokens:
        return 1.0
    return len(claim_tokens & ctx_tokens) / len(claim_tokens)


def numeric_contradiction(answer: str, reference: str) -> bool:
    """True when the answer states a number that the reference does not contain."""
    ref_nums = set(numbers_in(reference))
    ans_nums = numbers_in(answer)
    if not ans_nums or not ref_nums:
        return False
    return any(n not in ref_nums for n in ans_nums)


# ------------------------------------------------------------------ metrics


def _needs_reference(ctx: MetricContext) -> MetricResult | None:
    if not (ctx.reference_answer or "").strip():
        return MetricResult.missing("no reference answer for this item")
    return None


def _exact_match(ctx: MetricContext) -> MetricResult:
    miss = _needs_reference(ctx)
    if miss:
        return miss
    return MetricResult(
        value=exact_match_value(ctx.answer, ctx.reference_answer, ctx.aliases),
        kind=REFERENCE_BASED,
        evidence={"reference": ctx.reference_answer},
    )


def _normalized_match(ctx: MetricContext) -> MetricResult:
    miss = _needs_reference(ctx)
    if miss:
        return miss
    return MetricResult(
        value=normalized_match_value(ctx.answer, ctx.reference_answer, ctx.aliases),
        kind=REFERENCE_BASED,
        evidence={"reference": ctx.reference_answer},
    )


def _token_f1(ctx: MetricContext) -> MetricResult:
    miss = _needs_reference(ctx)
    if miss:
        return miss
    return MetricResult(
        value=round(token_f1_value(ctx.answer, ctx.reference_answer, ctx.aliases), 6),
        kind=REFERENCE_BASED,
        evidence={"reference": ctx.reference_answer},
    )


def _completeness(ctx: MetricContext) -> MetricResult:
    """Share of the reference's content tokens covered by the answer."""
    miss = _needs_reference(ctx)
    if miss:
        return miss
    ref_tokens = set(content_tokens(ctx.reference_answer))
    if not ref_tokens:
        return MetricResult.missing("reference answer has no content tokens")
    ans_tokens = set(content_tokens(ctx.answer))
    return MetricResult(
        value=round(len(ref_tokens & ans_tokens) / len(ref_tokens), 6),
        kind=REFERENCE_BASED,
        evidence={"missing_tokens": sorted(ref_tokens - ans_tokens)},
    )


def _faithfulness(ctx: MetricContext) -> MetricResult:
    """Heuristic: share of answer claims that are grounded in the context."""
    claims = sentences(ctx.answer)
    if not claims:
        return MetricResult.missing("no answer claims to score")
    if not ctx.context_texts:
        return MetricResult.missing("no retrieved context to verify against")
    scores = [claim_support(c, ctx.context_texts) for c in claims]
    supported = sum(1 for s in scores if s >= SUPPORT_THRESHOLD)
    return MetricResult(
        value=round(supported / len(claims), 6),
        kind=HEURISTIC,
        evidence={
            "claims": claims,
            "claim_scores": [round(s, 4) for s in scores],
            "support_threshold": SUPPORT_THRESHOLD,
        },
        detail={"unsupported_claims": [c for c, s in zip(claims, scores, strict=True) if s < SUPPORT_THRESHOLD]},
    )


def _claim_support_rate(ctx: MetricContext) -> MetricResult:
    """Deterministic share of claims with at least one supporting context token."""
    claims = sentences(ctx.answer)
    if not claims:
        return MetricResult.missing("no answer claims to score")
    if not ctx.context_texts:
        return MetricResult.missing("no retrieved context to verify against")
    hits = sum(1 for c in claims if claim_support(c, ctx.context_texts) > 0)
    return MetricResult(
        value=round(hits / len(claims), 6), kind=DETERMINISTIC, evidence={"n_claims": len(claims), "n_supported": hits}
    )


def _hallucination_rate(ctx: MetricContext) -> MetricResult:
    """Share of answer claims that are *not* grounded in the retrieved context."""
    claims = sentences(ctx.answer)
    if not claims:
        return MetricResult.missing("no answer claims to score")
    if not ctx.context_texts:
        return MetricResult.missing("no retrieved context to verify against")
    unsupported = [c for c in claims if claim_support(c, ctx.context_texts) < SUPPORT_THRESHOLD]
    return MetricResult(
        value=round(len(unsupported) / len(claims), 6),
        kind=HEURISTIC,
        evidence={"unsupported_claims": unsupported, "support_threshold": SUPPORT_THRESHOLD},
    )


def _answer_relevancy(ctx: MetricContext) -> MetricResult:
    """Heuristic: share of the question's content terms addressed by the answer."""
    q_tokens = set(content_tokens(ctx.question))
    if not q_tokens:
        return MetricResult.missing("question has no content tokens")
    a_tokens = set(content_tokens(ctx.answer))
    return MetricResult(
        value=round(len(q_tokens & a_tokens) / len(q_tokens), 6),
        kind=HEURISTIC,
        evidence={"question_terms": sorted(q_tokens), "missing": sorted(q_tokens - a_tokens)},
    )


def _semantic_similarity(ctx: MetricContext) -> MetricResult:
    if ctx.embedder is None:
        return MetricResult.missing("no embedding function configured", kind=EMBEDDING_BASED)
    miss = _needs_reference(ctx)
    if miss:
        return miss
    try:
        va, vb = ctx.embedder(ctx.answer), ctx.embedder(ctx.reference_answer)
    except Exception as exc:  # noqa: BLE001 - a broken embedder must not fail the run
        return MetricResult.missing(f"embedder failed: {exc}", kind=EMBEDDING_BASED)
    return MetricResult(
        value=round(max(0.0, cosine(va, vb)), 6),
        kind=EMBEDDING_BASED,
        evidence={"method": "cosine similarity of configured embeddings"},
    )


def _correct_abstention(ctx: MetricContext) -> MetricResult:
    """1.0 when an unanswerable question was correctly refused."""
    if ctx.answerable:
        return MetricResult.missing("item is answerable — abstention is scored as over-abstention")
    return MetricResult(
        value=1.0 if ctx.abstained else 0.0,
        kind=DETERMINISTIC,
        evidence={"answer": ctx.answer[:200], "abstained": ctx.abstained},
    )


def _over_abstention(ctx: MetricContext) -> MetricResult:
    """1.0 when an answerable question was wrongly refused."""
    if not ctx.answerable:
        return MetricResult.missing("item is unanswerable — scored by correct_abstention")
    return MetricResult(value=1.0 if ctx.abstained else 0.0, kind=DETERMINISTIC, evidence={"abstained": ctx.abstained})


def _contradiction_rate(ctx: MetricContext) -> MetricResult:
    """Share of answerable items whose answer contradicts the reference."""
    miss = _needs_reference(ctx)
    if miss:
        return miss
    if ctx.abstained:
        return MetricResult(value=0.0, kind=DETERMINISTIC, evidence={"note": "abstained answer cannot contradict"})
    return MetricResult(
        value=1.0 if numeric_contradiction(ctx.answer, ctx.reference_answer) else 0.0,
        kind=DETERMINISTIC,
        evidence={"answer_numbers": numbers_in(ctx.answer), "reference_numbers": numbers_in(ctx.reference_answer)},
    )


def _empty_answer(ctx: MetricContext) -> MetricResult:
    return MetricResult(
        value=1.0 if not (ctx.answer or "").strip() else 0.0,
        kind=DETERMINISTIC,
        evidence={"answer": (ctx.answer or "")[:200]},
    )


ANSWER_METRICS = [
    ("exact_match", "Normalised string equality with the reference answer.", ("reference_answer",), _exact_match),
    (
        "normalized_match",
        "Case/whitespace-insensitive equality that keeps articles.",
        ("reference_answer",),
        _normalized_match,
    ),
    ("token_f1", "Token-level F1 against the reference answer (best of aliases).", ("reference_answer",), _token_f1),
    (
        "completeness",
        "Share of the reference's content terms present in the answer.",
        ("reference_answer",),
        _completeness,
    ),
    (
        "faithfulness",
        "Heuristic: share of answer claims grounded in the retrieved context.",
        ("retrieved_context",),
        _faithfulness,
    ),
    (
        "claim_support_rate",
        "Share of answer claims with at least one supporting context term.",
        ("retrieved_context",),
        _claim_support_rate,
    ),
    (
        "hallucination_rate",
        "Heuristic: share of answer claims not grounded in the context.",
        ("retrieved_context",),
        _hallucination_rate,
    ),
    (
        "answer_relevancy",
        "Heuristic: share of the question's content terms addressed by the answer.",
        (),
        _answer_relevancy,
    ),
    (
        "semantic_similarity",
        "Cosine similarity between answer and reference embeddings.",
        ("reference_answer", "embedder"),
        _semantic_similarity,
    ),
    (
        "correct_abstention",
        "1.0 when an unanswerable question was correctly refused.",
        ("answerable=False",),
        _correct_abstention,
    ),
    ("over_abstention", "1.0 when an answerable question was wrongly refused.", ("answerable=True",), _over_abstention),
    (
        "contradiction_rate",
        "1.0 when the answer states a number the reference does not contain.",
        ("reference_answer",),
        _contradiction_rate,
    ),
    ("empty_answer", "1.0 when the RAG returned an empty answer.", (), _empty_answer),
]
