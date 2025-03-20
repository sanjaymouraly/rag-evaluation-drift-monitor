"""Citation and evidence metrics.

The platform deliberately separates two questions that are often conflated:

* **Structural validity** — does the citation point at a document/chunk that
  actually exists in the indexed corpus?
* **Genuine support** — is the cited content real evidence for the answer?

A citation that references an existing document id is *not* automatically
accurate. A quote is only counted as supported when it is found verbatim in the
cited chunk (normalised comparison), or — when the citation carries source
offsets — when the text at those offsets matches. Citations without a quote
must additionally support at least one claim of the answer.
"""

from __future__ import annotations

from .answer import SUPPORT_THRESHOLD, claim_support, sentences
from .base import DETERMINISTIC, MetricContext, MetricResult
from .text import normalize_answer, tokenize

SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
IRRELEVANT = "irrelevant"
STRUCTURAL_INVALID = "structural_invalid"


def _chunk_for(citation: dict, chunks_by_id: dict[str, dict]) -> dict | None:
    chunk_id = str(citation.get("chunk_id", "") or "")
    if chunk_id and chunk_id in chunks_by_id:
        return chunks_by_id[chunk_id]
    doc_id = str(citation.get("doc_id", "") or "")
    if doc_id and doc_id in chunks_by_id:
        return chunks_by_id[doc_id]
    return None


def _quote_in_chunk(quote: str, chunk_text: str) -> bool:
    q = normalize_answer(quote)
    if not q or len(tokenize(quote)) < 2:
        return False
    return q in normalize_answer(chunk_text)


def _offset_matches(citation: dict, chunk: dict) -> bool | None:
    """Verify a quote against explicit source offsets, when present."""
    quote = citation.get("quote") or ""
    start, end = citation.get("char_start"), citation.get("char_end")
    if quote and isinstance(start, int) and isinstance(end, int) and end > start:
        text = chunk.get("text", "")
        if end <= len(text):
            slice_text = text[start - (chunk.get("char_start", 0) or 0) : end - (chunk.get("char_start", 0) or 0)]
            return normalize_answer(slice_text) == normalize_answer(quote)
        return False
    return None


def classify_citations(
    citations: list[dict], chunks_by_id: dict[str, dict], answer: str, answer_claims: list[str] | None = None
) -> list[dict]:
    """Classify every citation. Returns one evidence record per citation."""
    claims = answer_claims if answer_claims is not None else sentences(answer)
    records: list[dict] = []
    for idx, citation in enumerate(citations or []):
        doc_id = str(citation.get("doc_id", "") or "")
        chunk_id = str(citation.get("chunk_id", "") or "")
        quote = citation.get("quote") or ""
        chunk = _chunk_for(citation, chunks_by_id)
        record = {
            "index": idx,
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "quote": (quote[:300] if isinstance(quote, str) else str(quote)[:300]),
            "outcome": SUPPORTED,
            "reason": "",
        }
        if chunk is None:
            record["outcome"] = STRUCTURAL_INVALID
            record["reason"] = "cited document/chunk does not exist in the indexed corpus"
            records.append(record)
            continue
        if chunk.get("doc_id") and doc_id and chunk.get("doc_id") != doc_id:
            record["outcome"] = STRUCTURAL_INVALID
            record["reason"] = f"chunk {chunk_id} belongs to document {chunk.get('doc_id')}, not {doc_id}"
            records.append(record)
            continue
        offset_ok = _offset_matches(citation, chunk)
        if offset_ok is False:
            record["outcome"] = UNSUPPORTED
            record["reason"] = "quoted text does not match the source span at the cited offsets"
            records.append(record)
            continue
        if quote:
            if not _quote_in_chunk(quote, chunk.get("text", "")):
                record["outcome"] = UNSUPPORTED
                record["reason"] = "quote was not found in the cited chunk"
                records.append(record)
                continue
            if claims and not any(claim_support(c, [chunk.get("text", "")]) >= SUPPORT_THRESHOLD for c in claims):
                record["outcome"] = IRRELEVANT
                record["reason"] = "quote exists but does not support any claim of the answer"
                records.append(record)
                continue
            record["reason"] = "quote verified in the cited chunk"
        else:
            if not claims:
                record["outcome"] = UNSUPPORTED
                record["reason"] = "no answer claims to attribute"
                records.append(record)
                continue
            best = max((claim_support(c, [chunk.get("text", "")]) for c in claims), default=0.0)
            if best < SUPPORT_THRESHOLD:
                record["outcome"] = UNSUPPORTED
                record["reason"] = "cited chunk does not support any claim of the answer"
                records.append(record)
                continue
            record["reason"] = f"cited chunk supports an answer claim (best support {best:.2f})"
        records.append(record)
    return records


def _expected_doc_ids(expected: list) -> set[str]:
    out: set[str] = set()
    for e in expected or []:
        if isinstance(e, str):
            out.add(e)
        elif isinstance(e, dict):
            doc = e.get("doc_id") or e.get("document_id")
            if doc:
                out.add(str(doc))
    return out


# ------------------------------------------------------------------ metrics


def _citation_records(ctx: MetricContext) -> list[dict]:
    return classify_citations(ctx.citations, ctx.chunks_by_id, ctx.answer)


def _citation_presence(ctx: MetricContext) -> MetricResult:
    if ctx.abstained:
        return MetricResult.missing("answer was abstained — no citation expected")
    return MetricResult(
        value=1.0 if ctx.citations else 0.0, kind=DETERMINISTIC, evidence={"n_citations": len(ctx.citations)}
    )


def _citation_structural_rate(ctx: MetricContext) -> MetricResult:
    records = _citation_records(ctx)
    if not records:
        return MetricResult.missing("the RAG returned no citations")
    valid = sum(1 for r in records if r["outcome"] != STRUCTURAL_INVALID)
    return MetricResult(value=round(valid / len(records), 6), kind=DETERMINISTIC, evidence={"records": records})


def _citation_support_rate(ctx: MetricContext) -> MetricResult:
    records = _citation_records(ctx)
    if not records:
        return MetricResult.missing("the RAG returned no citations")
    supported = sum(1 for r in records if r["outcome"] == SUPPORTED)
    return MetricResult(
        value=round(supported / len(records), 6),
        kind=DETERMINISTIC,
        evidence={"records": records, "n_supported": supported, "n_citations": len(records)},
    )


def _citation_unsupported_rate(ctx: MetricContext) -> MetricResult:
    records = _citation_records(ctx)
    if not records:
        return MetricResult.missing("the RAG returned no citations")
    bad = sum(1 for r in records if r["outcome"] in (UNSUPPORTED, STRUCTURAL_INVALID, IRRELEVANT))
    return MetricResult(value=round(bad / len(records), 6), kind=DETERMINISTIC, evidence={"records": records})


def _citation_precision(ctx: MetricContext) -> MetricResult:
    """Share of citations that point at a document the benchmark expects."""
    records = _citation_records(ctx)
    if not records:
        return MetricResult.missing("the RAG returned no citations")
    expected = _expected_doc_ids(ctx.expected_citations) or ctx.relevance_set
    if not expected:
        return MetricResult.missing("no expected citations or relevance labels for this item")
    good = sum(1 for r in records if r["doc_id"] in expected)
    return MetricResult(
        value=round(good / len(records), 6),
        kind=DETERMINISTIC,
        evidence={"expected_docs": sorted(expected), "records": records},
    )


def _citation_doc_recall(ctx: MetricContext) -> MetricResult:
    """Share of the expected cited documents that the answer actually cites."""
    expected = _expected_doc_ids(ctx.expected_citations)
    if not expected:
        return MetricResult.missing("no expected citations declared for this item")
    got = {str(c.get("doc_id", "")) for c in ctx.citations}
    return MetricResult(
        value=round(len(expected & got) / len(expected), 6),
        kind=DETERMINISTIC,
        evidence={"expected": sorted(expected), "cited": sorted(got), "missing": sorted(expected - got)},
    )


def _claim_attribution(ctx: MetricContext) -> MetricResult:
    """Share of answer claims that are attributed to a supporting citation."""
    claims = sentences(ctx.answer)
    if not claims:
        return MetricResult.missing("no answer claims to attribute")
    if not ctx.citations:
        return MetricResult.missing("the RAG returned no citations")
    chunk_texts = []
    for c in ctx.citations:
        chunk = _chunk_for(c, ctx.chunks_by_id)
        if chunk:
            chunk_texts.append(chunk.get("text", ""))
    if not chunk_texts:
        return MetricResult.missing("cited chunks are not available in the corpus")
    attributed = 0
    details = []
    for claim in claims:
        best = max((claim_support(claim, [text]) for text in chunk_texts), default=0.0)
        if best >= SUPPORT_THRESHOLD:
            attributed += 1
        details.append({"claim": claim, "support": round(best, 4)})
    return MetricResult(
        value=round(attributed / len(claims), 6),
        kind=DETERMINISTIC,
        evidence={"claims": details, "support_threshold": SUPPORT_THRESHOLD},
    )


def _citation_coverage(ctx: MetricContext) -> MetricResult:
    """Share of the answer's claims that have at least one (any) citation."""
    claims = sentences(ctx.answer)
    if not claims:
        return MetricResult.missing("no answer claims to cover")
    if not ctx.citations:
        return MetricResult(value=0.0, kind=DETERMINISTIC, evidence={"n_citations": 0})
    supported_claims = 0
    for claim in claims:
        for c in ctx.citations:
            chunk = _chunk_for(c, ctx.chunks_by_id)
            if chunk and claim_support(claim, [chunk.get("text", "")]) >= SUPPORT_THRESHOLD:
                supported_claims += 1
                break
    return MetricResult(
        value=round(supported_claims / len(claims), 6),
        kind=DETERMINISTIC,
        evidence={"n_claims": len(claims), "n_covered": supported_claims},
    )


CITATION_METRICS = [
    ("citation_presence", "1.0 when the answer carries at least one citation.", ("citations",), _citation_presence),
    (
        "citation_structural_valid",
        "Share of citations pointing at an existing document/chunk.",
        ("citations", "corpus"),
        _citation_structural_rate,
    ),
    (
        "citation_support",
        "Share of citations whose evidence genuinely supports the answer.",
        ("citations", "corpus"),
        _citation_support_rate,
    ),
    (
        "citation_unsupported_rate",
        "Share of citations that are unsupported, irrelevant or invalid.",
        ("citations", "corpus"),
        _citation_unsupported_rate,
    ),
    (
        "citation_precision",
        "Share of citations that point at an expected/relevant document.",
        ("citations", "expected_citations"),
        _citation_precision,
    ),
    (
        "citation_doc_recall",
        "Share of expected cited documents that the answer cites.",
        ("expected_citations",),
        _citation_doc_recall,
    ),
    (
        "claim_attribution",
        "Share of answer claims attributed to a supporting citation.",
        ("citations", "corpus"),
        _claim_attribution,
    ),
    (
        "citation_coverage",
        "Share of answer claims covered by at least one citation.",
        ("citations", "corpus"),
        _citation_coverage,
    ),
]
