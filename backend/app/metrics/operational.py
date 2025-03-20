"""Operational metrics: latency, throughput, tokens and cost.

These are measured, not estimated, except for cost: the token counts come from
the real provider response when one exists, and the monetary amount is always
labelled as an estimate derived from the configured prices.
"""

from __future__ import annotations

from .base import OPERATIONAL, MetricContext, MetricResult


def _latency(ctx: MetricContext) -> MetricResult:
    return MetricResult(
        value=round(float(ctx.latency_ms), 3),
        kind=OPERATIONAL,
        evidence={"retrieval_ms": ctx.retrieval_latency_ms, "generation_ms": ctx.generation_latency_ms},
    )


def _retrieval_latency(ctx: MetricContext) -> MetricResult:
    if ctx.mode == "generation_only":
        return MetricResult.missing("retrieval is bypassed in generation_only mode")
    return MetricResult(value=round(float(ctx.retrieval_latency_ms), 3), kind=OPERATIONAL)


def _generation_latency(ctx: MetricContext) -> MetricResult:
    if ctx.mode == "retrieval_only":
        return MetricResult.missing("generation is bypassed in retrieval_only mode")
    return MetricResult(value=round(float(ctx.generation_latency_ms), 3), kind=OPERATIONAL)


def _input_tokens(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=float(ctx.input_tokens), kind=OPERATIONAL)


def _output_tokens(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=float(ctx.output_tokens), kind=OPERATIONAL)


def _cost(ctx: MetricContext) -> MetricResult:
    return MetricResult(
        value=round(float(ctx.estimated_cost_usd), 8),
        kind=OPERATIONAL,
        evidence={
            "is_estimate": ctx.cost_is_estimate,
            "note": "cost is derived from measured token counts and configured prices",
        },
    )


def _error_flag(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=1.0 if ctx.error else 0.0, kind=OPERATIONAL, evidence={"error": ctx.error[:300]})


OPERATIONAL_METRICS = [
    ("latency_ms", "End-to-end latency of the RAG call in milliseconds.", (), _latency),
    ("retrieval_latency_ms", "Retrieval stage latency in milliseconds.", (), _retrieval_latency),
    ("generation_latency_ms", "Generation stage latency in milliseconds.", (), _generation_latency),
    ("input_tokens", "Input tokens consumed for this question.", (), _input_tokens),
    ("output_tokens", "Output tokens produced for this question.", (), _output_tokens),
    (
        "estimated_cost_usd",
        "Estimated spend for this question in USD (measured tokens x configured prices).",
        (),
        _cost,
    ),
    ("request_error", "1.0 when the request failed.", (), _error_flag),
]
