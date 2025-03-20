"""Aggregation of per-item metric values into run-level metrics.

Every aggregated metric carries three things: the value, the number of items
that contributed (``n``) and the metric *kind*. A metric with ``n = 0`` was not
computed for any item — it is missing evidence, and the release gate treats it
as such.
"""

from __future__ import annotations

import math
import statistics

from ..metrics import all_metrics


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, max(0, math.ceil(pct / 100 * len(sorted_values)) - 1))
    return sorted_values[idx]


def percentile_summary(values: list[float]) -> dict:
    if not values:
        return {"p50": None, "p95": None, "p99": None, "mean": None, "min": None, "max": None, "n": 0}
    ordered = sorted(values)
    return {
        "p50": round(_percentile(ordered, 50), 3),
        "p95": round(_percentile(ordered, 95), 3),
        "p99": round(_percentile(ordered, 99), 3),
        "mean": round(statistics.fmean(ordered), 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
        "n": len(ordered),
    }


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 6) if values else None


def _stdev(values: list[float]) -> float | None:
    return round(statistics.stdev(values), 6) if len(values) > 1 else None


def _metric_kinds() -> dict[str, str]:
    return {name: spec.kind for name, spec in all_metrics().items()}


def _collect(results, key: str) -> list[float]:
    values = []
    for result in results:
        value = (result.metrics or {}).get(key)
        if value is not None:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
    return values


def aggregate_results(results: list, mode: str) -> dict:
    """Build the run-level metric dictionary."""
    kinds = _metric_kinds()
    names = sorted({key for r in results for key in (r.metrics or {})})
    metrics: dict = {}
    for name in names:
        values = _collect(results, name)
        metrics[name] = {
            "value": _mean(values),
            "n": len(values),
            "kind": kinds.get(name, "deterministic"),
            "std": _stdev(values),
        }

    latencies = [float(r.latency_ms or 0.0) for r in results]
    latency = percentile_summary(latencies)
    for label, key in (("latency_p50_ms", "p50"), ("latency_p95_ms", "p95"), ("latency_p99_ms", "p99")):
        metrics[label] = {"value": latency[key], "n": latency["n"], "kind": "operational", "std": None}

    total_in = sum(int(r.input_tokens or 0) for r in results)
    total_out = sum(int(r.output_tokens or 0) for r in results)
    total_cost = round(sum(float(r.metrics.get("estimated_cost_usd") or 0.0) if r.metrics else 0.0 for r in results), 8)
    metrics["total_input_tokens"] = {"value": float(total_in), "n": len(results), "kind": "operational", "std": None}
    metrics["total_output_tokens"] = {"value": float(total_out), "n": len(results), "kind": "operational", "std": None}
    metrics["estimated_cost_usd"] = {"value": total_cost, "n": len(results), "kind": "operational", "std": None}

    successful = [
        r for r in results if not r.abstained and (r.metrics or {}).get("empty_answer") != 1.0 and not r.error
    ]
    metrics["cost_per_request_usd"] = {
        "value": round(total_cost / len(results), 8) if results else None,
        "n": len(results),
        "kind": "operational",
        "std": None,
    }
    metrics["cost_per_successful_answer_usd"] = {
        "value": round(total_cost / len(successful), 8) if successful else None,
        "n": len(successful),
        "kind": "operational",
        "std": None,
    }

    answerable = [r for r in results if r.answerable]
    failures = [
        r
        for r in answerable
        if (r.metrics or {}).get("token_f1") is not None and float(r.metrics.get("token_f1")) < 0.3
    ]
    metrics["failure_rate"] = {
        "value": round(len(failures) / len(answerable), 6) if answerable else None,
        "n": len(answerable),
        "kind": "deterministic",
        "std": None,
    }
    metrics["error_rate"] = {
        "value": round(sum(1 for r in results if r.error) / len(results), 6) if results else None,
        "n": len(results),
        "kind": "operational",
        "std": None,
    }

    def _breakdown(group_key) -> dict:
        groups: dict[str, list] = {}
        for r in results:
            if group_key == "category":
                keys = [r.category or "uncategorized"]
            else:
                keys = list(getattr(r, "cohorts", None) or []) or ["uncategorized"]
            for key in keys:
                groups.setdefault(str(key), []).append(r)
        out = {}
        for key, group in sorted(groups.items()):
            group_metrics = {}
            for name in names:
                values = _collect(group, name)
                if values:
                    group_metrics[name] = {
                        "value": _mean(values),
                        "n": len(values),
                        "kind": kinds.get(name, "deterministic"),
                    }
            out[key] = {"n": len(group), "metrics": group_metrics}
        return out

    return {
        "n_questions": len(results),
        "mode": mode,
        "metrics": metrics,
        "metric_kinds": {name: kinds.get(name, "deterministic") for name in names},
        "latency_ms": latency,
        "by_category": _breakdown("category"),
        "by_cohort": _breakdown("cohort"),
        "n_errors": sum(1 for r in results if r.error),
        "n_abstained": sum(1 for r in results if r.abstained),
        "n_with_citations": sum(1 for r in results if r.citations),
    }
