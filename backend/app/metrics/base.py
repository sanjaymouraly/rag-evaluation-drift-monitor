"""Metric plugin interface.

A metric is a small object with a stable name, a declared *kind* and the
evidence it needs. Two rules are enforced across the whole platform:

1. A metric whose evidence is missing returns ``value=None`` with a reason.
   It is never replaced by a fabricated number.
2. The *kind* of a metric is always reported next to its value so a reader
   can tell a deterministic computation from a heuristic estimate or an
   LLM-judge opinion.

Third-party metrics can be registered at runtime::

    from app.metrics import register_metric, MetricResult, MetricContext

    class MyMetric:
        name = "my_metric"
        kind = "deterministic"
        requires = ("reference_answer",)

        def compute(self, ctx: MetricContext) -> MetricResult:
            return MetricResult(value=1.0, evidence={"note": "..."})

    register_metric(MyMetric())
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Metric provenance kinds.
DETERMINISTIC = "deterministic"  # exact formula over given evidence
REFERENCE_BASED = "reference_based"  # needs a gold reference answer
HEURISTIC = "heuristic"  # token-overlap style estimate
EMBEDDING_BASED = "embedding_based"  # needs a (possibly approximate) embedding
JUDGE = "judge"  # LLM-as-a-judge opinion signal
OPERATIONAL = "operational"  # latency / tokens / cost

KIND_DESCRIPTIONS = {
    DETERMINISTIC: "Exact formula over the supplied evidence.",
    REFERENCE_BASED: "Computed against a human-authored reference answer.",
    HEURISTIC: "Estimate from token/surface overlap. Not verified ground truth.",
    EMBEDDING_BASED: "Similarity from an embedding model. Approximate.",
    JUDGE: "LLM-as-a-judge opinion signal. Not proof of correctness.",
    OPERATIONAL: "Measured operational signal (latency, tokens, cost).",
}

# Evidence requirements, used by the API to explain why a metric is missing.
REQUIRES = {
    "relevance_labels": "dataset item must declare relevant_doc_ids",
    "reference_answer": "dataset item must declare a reference answer",
    "graded_relevance": "dataset item must declare relevance_grades",
    "expected_citations": "dataset item must declare expected_citations",
    "retrieved_context": "the RAG run must return retrieved context",
    "citations": "the RAG run must return citations",
    "embedder": "an embedding function must be configured",
    "judge": "an LLM judge provider must be configured",
    "corpus": "the project corpus must be loaded",
}


@dataclass
class MetricContext:
    """Everything a metric may look at for a single benchmark item."""

    question: str = ""
    reference_answer: str = ""
    aliases: list[str] = field(default_factory=list)
    relevant_doc_ids: list[str] = field(default_factory=list)
    relevance_grades: dict[str, float] = field(default_factory=dict)
    expected_citations: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    answer: str = ""
    abstained: bool = False
    chunks_by_id: dict[str, dict] = field(default_factory=dict)
    corpus_doc_ids: list[str] = field(default_factory=list)
    category: str = "uncategorized"
    cohorts: list[str] = field(default_factory=list)
    answerable: bool = True
    mode: str = "end_to_end"
    latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_is_estimate: bool = True
    error: str = ""
    embedder: Callable[[str], list[float]] | None = None
    judge: Callable[[str], dict] | None = None

    @property
    def retrieved_doc_ids(self) -> list[str]:
        return [str(r.get("doc_id", "")) for r in self.retrieved]

    @property
    def retrieved_chunk_ids(self) -> list[str]:
        return [str(r.get("chunk_id", "")) for r in self.retrieved]

    @property
    def context_texts(self) -> list[str]:
        return [str(r.get("text", "")) for r in self.retrieved]

    @property
    def relevance_set(self) -> set[str]:
        return {str(d) for d in (self.relevant_doc_ids or [])}


@dataclass
class MetricResult:
    """Outcome of a single metric computation on one item."""

    value: float | None
    kind: str = DETERMINISTIC
    evidence: dict = field(default_factory=dict)
    reason: str = ""
    detail: dict = field(default_factory=dict)

    @classmethod
    def missing(cls, reason: str, kind: str = DETERMINISTIC) -> MetricResult:
        return cls(value=None, kind=kind, reason=reason)


@runtime_checkable
class Metric(Protocol):
    name: str
    kind: str
    requires: tuple[str, ...]

    def compute(self, ctx: MetricContext) -> MetricResult: ...


class MetricSpec:
    """Concrete metric implementation used by the built-in registry."""

    def __init__(self, name: str, kind: str, requires: tuple[str, ...], fn, description: str = ""):
        self.name = name
        self.kind = kind
        # Guard against a bare string being passed as the requirements
        # ("abc" would silently become the tuple ('a', 'b', 'c')).
        if isinstance(requires, str):
            raise TypeError(f"metric {name!r}: requires must be a tuple of strings, not a string")
        if not all(isinstance(item, str) for item in requires):
            raise TypeError(f"metric {name!r}: every requirement must be a string")
        self.requires = tuple(requires)
        self.description = description
        self._fn = fn

    def compute(self, ctx: MetricContext) -> MetricResult:
        return self._fn(ctx)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MetricSpec {self.name} kind={self.kind}>"


_REGISTRY: dict[str, MetricSpec] = {}


def register_metric(metric: MetricSpec) -> MetricSpec:
    """Register (or replace) a metric implementation."""
    if not metric.name:
        raise ValueError("metric must have a name")
    _REGISTRY[metric.name] = metric
    return metric


def get_metric(name: str) -> MetricSpec | None:
    return _REGISTRY.get(name)


def all_metrics() -> dict[str, MetricSpec]:
    return dict(_REGISTRY)


def metric_catalogue() -> list[dict]:
    """Machine-readable description of every registered metric."""
    return [
        {
            "name": m.name,
            "kind": m.kind,
            "kind_description": KIND_DESCRIPTIONS.get(m.kind, m.kind),
            "requires": list(m.requires),
            "requirements": [REQUIRES.get(r, r) for r in m.requires],
            "description": m.description,
        }
        for m in sorted(_REGISTRY.values(), key=lambda x: x.name)
    ]
