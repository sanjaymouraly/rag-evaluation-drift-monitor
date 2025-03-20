"""Unit tests for the metric primitives.

The expected values in this file are computed by hand from the metric
definitions, not copied from an implementation output.
"""

from __future__ import annotations

import math

import pytest

from app.metrics import (
    DETERMINISTIC,
    HEURISTIC,
    MetricContext,
    MetricResult,
    all_metrics,
    metric_catalogue,
    register_metric,
)
from app.metrics.answer import (
    claim_support,
    cosine,
    exact_match_value,
    normalized_match_value,
    numeric_contradiction,
    token_f1_value,
    token_overlap,
)
from app.metrics.base import MetricSpec
from app.metrics.citation import (
    IRRELEVANT,
    STRUCTURAL_INVALID,
    SUPPORTED,
    UNSUPPORTED,
    classify_citations,
)
from app.metrics.retrieval import (
    average_precision,
    context_precision,
    context_recall,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.metrics.text import normalize_answer, numbers_in, tokenize

# --------------------------------------------------------------- retrieval


def test_precision_at_k_known_ranking():
    # 2 of the top 5 retrieved documents are relevant.
    assert precision_at_k(["a", "b", "c", "d", "e"], {"b", "d"}, 5) == pytest.approx(0.4)
    # A relevant document at rank 1 gives precision 1.0 at k=1.
    assert precision_at_k(["b", "c"], {"b"}, 1) == pytest.approx(1.0)
    # Nothing retrieved at all scores zero, not "missing".
    assert precision_at_k([], {"b"}, 5) == 0.0


def test_recall_at_k_known_ranking():
    assert recall_at_k(["a", "b", "c", "d", "e"], {"b", "d", "f"}, 5) == pytest.approx(2 / 3)
    assert recall_at_k(["a"], {"b", "d"}, 5) == 0.0


def test_hit_rate_at_k_known_ranking():
    assert hit_rate_at_k(["a", "b"], {"b"}, 5) == 1.0
    assert hit_rate_at_k(["a"], {"b"}, 5) == 0.0


def test_reciprocal_rank_known_ranking():
    assert reciprocal_rank(["a", "b", "c"], {"b"}) == pytest.approx(0.5)
    assert reciprocal_rank(["a", "b", "c"], {"c"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["a"], {"z"}) == 0.0


def test_average_precision_known_ranking():
    # Relevant at ranks 2 and 4 -> (1/2 + 2/4) / 2 = 0.5
    assert average_precision(["a", "b", "c", "d"], {"b", "d"}) == pytest.approx(0.5)
    # A duplicate of a relevant document is not counted twice.
    assert average_precision(["b", "b", "c"], {"b"}) == pytest.approx(1.0)


def test_ndcg_at_k_known_ranking():
    grades = {"b": 1.0, "d": 1.0}
    # With equal grades, DCG only depends on the positions, so both orders tie.
    assert ndcg_at_k(["b", "d"], grades, 5) == pytest.approx(1.0)
    assert ndcg_at_k(["d", "b"], grades, 5) == pytest.approx(1.0)
    # A relevant document that is not retrieved at all scores zero.
    assert ndcg_at_k(["x", "y"], grades, 5) == pytest.approx(0.0)
    # Graded relevance: the ideal order puts the grade-2 document first.
    graded = {"x": 2.0, "y": 1.0}
    assert ndcg_at_k(["x", "y"], graded, 5) == pytest.approx(1.0)
    # DCG([y,x]) = 1/log2(2) + 3/log2(3); IDCG = 3/log2(2) + 1/log2(3)
    expected = (1 / math.log2(2) + 3 / math.log2(3)) / (3 / math.log2(2) + 1 / math.log2(3))
    assert ndcg_at_k(["y", "x"], graded, 5) == pytest.approx(expected)
    assert ndcg_at_k(["y", "x"], graded, 5) < 1.0


def test_context_precision_and_recall():
    assert context_precision(["a", "b", "c"], {"b"}, 5) == pytest.approx(1 / 3)
    assert context_recall(["a", "b", "c"], {"b", "d"}, 5) == pytest.approx(0.5)


def test_retrieval_metrics_require_labels():
    for fn, args in (
        (precision_at_k, ([], set(), 5)),
        (recall_at_k, ([], set(), 5)),
        (hit_rate_at_k, ([], set(), 5)),
        (
            reciprocal_rank,
            (
                [],
                set(),
            ),
        ),
        (
            average_precision,
            (
                [],
                set(),
            ),
        ),
        (context_precision, ([], set(), 5)),
        (context_recall, ([], set(), 5)),
    ):
        with pytest.raises(ValueError):
            fn(*args)


# ------------------------------------------------------------------ answer


def test_exact_match_normalises_articles_and_punctuation():
    assert exact_match_value("The 254 megawatts.", "254 megawatts") == 1.0
    assert exact_match_value("254 megawatts", "254 megawatts", ["254 MW"]) == 1.0
    assert exact_match_value("512 megawatts", "254 megawatts") == 0.0
    assert exact_match_value("", "254 megawatts") == 0.0


def test_normalized_match_keeps_articles():
    assert normalized_match_value("The cat", "cat") == 0.0
    assert normalized_match_value("The cat", "the cat") == 1.0


def test_token_f1_known_values():
    # Perfect overlap -> 1.0
    assert token_f1_value("a b c", "a b c") == pytest.approx(1.0)
    # No overlap -> 0.0
    assert token_f1_value("a b", "x y") == 0.0
    # One common token out of two on each side -> 2*(1/2*1/2)/(1) = 0.5
    assert token_f1_value("a b", "a c") == pytest.approx(0.5)
    # The best alias wins.
    assert token_f1_value("Sihwa Lake 254 MW", "Sihwa Lake 254 megawatts", ["Sihwa Lake 254 MW"]) == pytest.approx(1.0)


def test_token_overlap_and_claim_support():
    # Stopwords are ignored, so "the" does not count against the overlap.
    assert token_overlap("the cat sat", "cat") == pytest.approx(0.5)
    assert token_overlap("cat", "cat") == pytest.approx(1.0)
    assert token_overlap("dog", "cat") == 0.0
    assert claim_support("bees signal distance", ["bees signal distance with a waggle dance"]) == pytest.approx(1.0)
    assert claim_support("totally unrelated content", ["bees signal distance"]) == 0.0


def test_numeric_contradiction_detects_a_wrong_number():
    assert numeric_contradiction("The station has 900 megawatts.", "The station has 254 megawatts.") is True
    assert numeric_contradiction("The station has 254 megawatts.", "The station has 254 megawatts.") is False
    # No numbers on one side -> no contradiction can be proven.
    assert numeric_contradiction("A tidal barrage traps water.", "254 megawatts") is False


def test_cosine_similarity():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)


def test_numbers_in_normalises_thousands_separators():
    assert numbers_in("about 1,500 litres and 12.5%") == ["1500", "12.5"]


def test_normalize_answer():
    assert normalize_answer("The  Honeybees' dance!") == "honeybees dance"


# --------------------------------------------------------------- citations


def _chunks():
    return {
        "doc_a::c0": {"chunk_id": "doc_a::c0", "doc_id": "doc_a", "text": "Bees signal distance with a waggle dance."},
        "doc_b::c0": {"chunk_id": "doc_b::c0", "doc_id": "doc_b", "text": "Sourdough needs flour and water."},
    }


def test_citation_to_unknown_document_is_structurally_invalid():
    records = classify_citations(
        [{"doc_id": "doc_zzz", "chunk_id": "doc_zzz::c0", "quote": "anything"}], _chunks(), "some answer"
    )
    assert records[0]["outcome"] == STRUCTURAL_INVALID


def test_citation_pointing_at_the_wrong_document_is_invalid():
    records = classify_citations(
        [{"doc_id": "doc_b", "chunk_id": "doc_a::c0", "quote": "Bees signal distance."}],
        _chunks(),
        "Bees signal distance.",
    )
    assert records[0]["outcome"] == STRUCTURAL_INVALID


def test_quote_not_present_in_the_chunk_is_unsupported():
    records = classify_citations(
        [{"doc_id": "doc_a", "chunk_id": "doc_a::c0", "quote": "Bees sing at midnight."}],
        _chunks(),
        "Bees sing at midnight.",
    )
    assert records[0]["outcome"] == UNSUPPORTED


def test_verified_quote_is_supported():
    records = classify_citations(
        [{"doc_id": "doc_a", "chunk_id": "doc_a::c0", "quote": "Bees signal distance with a waggle dance."}],
        _chunks(),
        "Bees signal distance with a waggle dance.",
    )
    assert records[0]["outcome"] == SUPPORTED


def test_quote_that_exists_but_does_not_support_the_answer_is_irrelevant():
    records = classify_citations(
        [{"doc_id": "doc_b", "chunk_id": "doc_b::c0", "quote": "Sourdough needs flour and water."}],
        _chunks(),
        "Bees signal distance with a waggle dance.",
    )
    assert records[0]["outcome"] == IRRELEVANT


def test_citation_without_a_quote_must_support_a_claim():
    records = classify_citations(
        [{"doc_id": "doc_a", "chunk_id": "doc_a::c0"}], _chunks(), "Bees signal distance with a waggle dance."
    )
    assert records[0]["outcome"] == SUPPORTED
    records = classify_citations(
        [{"doc_id": "doc_b", "chunk_id": "doc_b::c0"}], _chunks(), "Bees signal distance with a waggle dance."
    )
    assert records[0]["outcome"] == UNSUPPORTED


def test_source_offsets_are_verified_against_the_chunk():
    chunk = {
        "chunk_id": "doc_a::c0",
        "doc_id": "doc_a",
        "text": "Bees signal distance with a waggle dance.",
        "char_start": 0,
    }
    citation = {
        "doc_id": "doc_a",
        "chunk_id": "doc_a::c0",
        "quote": "Bees signal distance with a waggle dance.",
        "char_start": 0,
        "char_end": 40,
    }
    records = classify_citations([citation], {"doc_a::c0": chunk}, "Bees signal distance with a waggle dance.")
    assert records[0]["outcome"] == SUPPORTED
    bad = dict(citation, quote="Something else entirely here.", char_end=20)
    records = classify_citations([bad], {"doc_a::c0": chunk}, "Something else entirely here.")
    assert records[0]["outcome"] == UNSUPPORTED


# ------------------------------------------------------------ metric layer


def test_metric_without_evidence_returns_none_with_a_reason():
    ctx = MetricContext(question="q", reference_answer="", relevant_doc_ids=[])
    result = all_metrics()["token_f1"].compute(ctx)
    assert result.value is None
    assert "reference" in result.reason.lower()


def test_metric_with_missing_relevance_labels_returns_none():
    ctx = MetricContext(question="q", retrieved=[{"doc_id": "x", "chunk_id": "x::c0", "text": "text"}])
    result = all_metrics()["recall_at_5"].compute(ctx)
    assert result.value is None
    assert "relevance" in result.reason.lower()


def test_empty_retrieval_is_measured_not_missing():
    ctx = MetricContext(question="q")
    result = all_metrics()["empty_retrieval"].compute(ctx)
    assert result.value == 1.0


def test_faithfulness_is_labelled_heuristic():
    ctx = MetricContext(
        question="q",
        answer="Bees signal distance.",
        retrieved=[{"doc_id": "d", "chunk_id": "d::c0", "text": "Bees signal distance."}],
    )
    result = all_metrics()["faithfulness"].compute(ctx)
    assert result.kind == HEURISTIC
    assert result.value == pytest.approx(1.0)


def test_hallucinated_claim_is_detected():
    ctx = MetricContext(
        question="q",
        answer="Bees sing at midnight in a choir.",
        retrieved=[{"doc_id": "d", "chunk_id": "d::c0", "text": "Bees signal distance."}],
    )
    result = all_metrics()["hallucination_rate"].compute(ctx)
    assert result.value == pytest.approx(1.0)


def test_correct_abstention_only_applies_to_unanswerable_items():
    ctx = MetricContext(question="q", answerable=False, abstained=True)
    assert all_metrics()["correct_abstention"].compute(ctx).value == 1.0
    ctx = MetricContext(question="q", answerable=True, abstained=True)
    assert all_metrics()["correct_abstention"].compute(ctx).value is None
    assert all_metrics()["over_abstention"].compute(ctx).value == 1.0


def test_semantic_similarity_requires_an_embedder():
    ctx = MetricContext(question="q", reference_answer="r", answer="a")
    assert all_metrics()["semantic_similarity"].compute(ctx).value is None
    ctx.embedder = lambda text: [1.0, 0.0]
    assert all_metrics()["semantic_similarity"].compute(ctx).value == pytest.approx(1.0)


def test_every_metric_declares_its_requirements_as_a_tuple_of_strings():
    """A bare string would silently become a tuple of characters."""
    for name, spec in all_metrics().items():
        assert isinstance(spec.requires, tuple), name
        assert all(isinstance(item, str) for item in spec.requires), name
        assert len(set(spec.requires)) == len(spec.requires), name


def test_metric_spec_rejects_a_string_requirement():
    with pytest.raises(TypeError):
        MetricSpec(
            name="bad",
            kind=DETERMINISTIC,
            requires="abc",  # type: ignore[arg-type]
            fn=lambda ctx: MetricResult(value=1.0),
            description="d",
        )


def test_metric_catalogue_documents_every_metric():
    catalogue = metric_catalogue()
    names = {m["name"] for m in catalogue}
    assert "recall_at_5" in names
    assert "citation_support" in names
    for entry in catalogue:
        assert entry["kind_description"]
        assert entry["description"]


def test_third_party_metrics_can_be_registered():
    class MyMetric:
        name = "unit_test_metric"
        kind = DETERMINISTIC
        requires = ()

        def compute(self, ctx: MetricContext) -> MetricResult:
            return MetricResult(value=0.5, kind=DETERMINISTIC, evidence={"note": "unit test"})

    register_metric(MyMetric())
    assert "unit_test_metric" in all_metrics()
    result = all_metrics()["unit_test_metric"].compute(MetricContext())
    assert result.value == 0.5


def test_registered_spec_is_usable_directly():
    spec = MetricSpec(
        name="x", kind=DETERMINISTIC, requires=(), fn=lambda ctx: MetricResult(value=1.0), description="d"
    )
    assert spec.compute(MetricContext()).value == 1.0


def test_math_helpers_are_stable():
    assert math.isclose(math.log2(8), 3.0)
    assert tokenize("Hello, World! 42") == ["hello", "world", "42"]
