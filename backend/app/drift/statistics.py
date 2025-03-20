"""Drift statistics.

Drift is a *distribution change*. It is reported separately from a proven
quality regression: a distribution can move without the product getting worse,
and a regression can happen without any distributional signal.
"""

from __future__ import annotations

import math

import numpy as np


def psi(expected: list[float], actual: list[float], bins: int = 10) -> float | None:
    """Population Stability Index over numeric samples.

    Bins are quantiles of the expected sample. Degenerate (constant) metrics
    fall back to equal-width bins instead of returning nothing.
    """
    e = np.array([x for x in expected if x is not None], dtype=float)
    a = np.array([x for x in actual if x is not None], dtype=float)
    if len(e) < 5 or len(a) < 5:
        return None
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        lo, hi = float(min(e.min(), a.min())), float(max(e.max(), a.max()))
        if hi <= lo:
            return 0.0
        edges = np.linspace(0.0, 1.0, 6) if lo >= 0.0 and hi <= 1.0 else np.linspace(lo, hi, 8)
    edges = edges.astype(float).copy()
    edges[0], edges[-1] = -np.inf, np.inf
    e_pct = np.histogram(e, bins=edges)[0] / len(e)
    a_pct = np.histogram(a, bins=edges)[0] / len(a)
    e_pct = np.where(e_pct == 0, 0.0001, e_pct)
    a_pct = np.where(a_pct == 0, 0.0001, a_pct)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def psi_categorical(expected: list[str], actual: list[str]) -> float | None:
    """PSI over categorical samples (categories, cohorts, document ids)."""
    if len(expected) < 5 or len(actual) < 5:
        return None
    cats = set(expected) | set(actual)
    total = 0.0
    for c in cats:
        e = max(expected.count(c) / len(expected), 0.0001)
        a = max(actual.count(c) / len(actual), 0.0001)
        total += (a - e) * math.log(a / e)
    return float(total)


def ks_test(expected: list[float], actual: list[float]) -> dict:
    """Two-sample Kolmogorov-Smirnov test with a sample-size caveat."""
    e = [x for x in expected if x is not None]
    a = [x for x in actual if x is not None]
    if len(e) < 5 or len(a) < 5:
        return {
            "statistic": None,
            "p_value": None,
            "n_baseline": len(e),
            "n_candidate": len(a),
            "note": "need at least 5 samples per run",
        }
    try:
        from scipy.stats import ks_2samp

        r = ks_2samp(e, a)
        return {
            "statistic": float(r.statistic),
            "p_value": float(r.pvalue),
            "n_baseline": len(e),
            "n_candidate": len(a),
        }
    except Exception:  # noqa: BLE001
        return {"statistic": None, "p_value": None, "n_baseline": len(e), "n_candidate": len(a)}


def jsd_from_counts(p_counts: dict, q_counts: dict) -> float | None:
    """Jensen-Shannon divergence between two categorical count maps (natural log)."""
    keys = set(p_counts) | set(q_counts)
    if not keys:
        return None
    p = np.array([p_counts.get(k, 0) for k in keys], dtype=float)
    q = np.array([q_counts.get(k, 0) for k in keys], dtype=float)
    if p.sum() == 0 or q.sum() == 0:
        return None
    p, q = p / p.sum(), q / q.sum()
    m = 0.5 * (p + q)

    def kl(x: np.ndarray, y: np.ndarray) -> float:
        mask = x > 0
        return float(np.sum(x[mask] * np.log(x[mask] / y[mask])))

    return float(0.5 * kl(p, m) + 0.5 * kl(q, m))


def embedding_drift(baseline_vectors: list[list[float]], candidate_vectors: list[list[float]]) -> dict:
    """Compare two embedding distributions.

    Only meaningful when both runs use the *same* embedding model and space;
    the function checks the dimensionality and reports a warning otherwise.
    """
    if not baseline_vectors or not candidate_vectors:
        return {"comparable": False, "reason": "no embeddings available on one side"}
    dim_b = len(baseline_vectors[0])
    dim_c = len(candidate_vectors[0])
    if dim_b != dim_c:
        return {
            "comparable": False,
            "reason": f"embedding dimensions differ ({dim_b} vs {dim_c}) — the embedding spaces are not comparable",
        }
    b = np.array(baseline_vectors, dtype=float)
    c = np.array(candidate_vectors, dtype=float)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    c_norm = c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-9)
    centroid_shift = float(np.linalg.norm(b_norm.mean(axis=0) - c_norm.mean(axis=0)))
    from ..gates.stats import bootstrap_ci  # local import to avoid a package cycle

    per_dim_shift = np.abs(b_norm.mean(axis=0) - c_norm.mean(axis=0))
    return {
        "comparable": True,
        "n_baseline": len(b_norm),
        "n_candidate": len(c_norm),
        "centroid_shift": round(centroid_shift, 6),
        "mean_dimension_shift": round(float(per_dim_shift.mean()), 6),
        "max_dimension_shift": round(float(per_dim_shift.max()), 6),
        "ci": [round(v, 6) for v in bootstrap_ci(list(per_dim_shift.tolist()), n_boot=500)],
        "note": "Only comparable when both runs use the same embedding model.",
    }


def control_chart(values: list[float], sigma: float = 3.0) -> dict:
    """Shewhart-style control chart limits around the mean of the series."""
    if len(values) < 3:
        return {"mean": None, "upper": None, "lower": None, "outliers": [], "n": len(values)}
    arr = np.array(values, dtype=float)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1))
    upper, lower = mean + sigma * sd, mean - sigma * sd
    outliers = [i for i, v in enumerate(arr) if v > upper or v < lower]
    return {
        "mean": round(mean, 6),
        "std": round(sd, 6),
        "upper": round(upper, 6),
        "lower": round(lower, 6),
        "sigma": sigma,
        "outliers": outliers,
        "n": len(arr),
    }


def interpret_psi(value: float | None) -> str:
    if value is None:
        return "insufficient data (need >= 5 samples per run)"
    if value < 0.1:
        return "no significant shift"
    if value < 0.25:
        return "moderate shift — investigate"
    return "large shift — likely drift"
