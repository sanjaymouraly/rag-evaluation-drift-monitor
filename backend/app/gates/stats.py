"""Paired statistics used by the release gate.

The gate must distinguish *noise* from a *proven regression*, so every relative
rule is evaluated on paired per-question differences with a bootstrap
confidence interval, a rank test and a standardised effect size.
"""

from __future__ import annotations

import math

import numpy as np


def bootstrap_ci(
    diffs: list[float], seed: int = 42, n_boot: int = 2000, confidence: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean of the paired differences."""
    if not diffs:
        return (0.0, 0.0)
    arr = np.array(diffs, dtype=float)
    if len(arr) == 1:
        return (float(arr[0]), float(arr[0]))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    means = arr[idx].mean(axis=1)
    alpha = (1 - confidence) / 2
    return (float(np.percentile(means, 100 * alpha)), float(np.percentile(means, 100 * (1 - alpha))))


def cohens_dz(diffs: list[float]) -> float | None:
    """Paired standardised effect size (dz)."""
    if len(diffs) < 2:
        return None
    arr = np.array(diffs, dtype=float)
    sd = arr.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(arr.mean() / sd)


def wilcoxon_p(diffs: list[float]) -> float | None:
    """Two-sided Wilcoxon signed-rank p-value (exact for small samples)."""
    nz = [d for d in diffs if d != 0]
    if len(nz) < 5:
        return None
    try:
        from scipy.stats import wilcoxon

        return float(wilcoxon(nz).pvalue)
    except Exception:  # noqa: BLE001 - scipy is optional at runtime
        return None


def paired_t_p(diffs: list[float]) -> float | None:
    if len(diffs) < 3:
        return None
    try:
        from scipy.stats import ttest_rel

        return float(ttest_rel(diffs, [0.0] * len(diffs)).pvalue)
    except Exception:  # noqa: BLE001
        return None


def mann_whitney_p(a: list[float], b: list[float]) -> float | None:
    """Unpaired comparison (used only when pairing is impossible)."""
    if len(a) < 3 or len(b) < 3:
        return None
    try:
        from scipy.stats import mannwhitneyu

        return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
    except Exception:  # noqa: BLE001
        return None


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values (multiple-comparison control)."""
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted = [0.0] * n
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        k = n - rank + 1
        value = min(prev, p_values[idx] * n / k)
        adjusted[idx] = value
        prev = value
    return adjusted


def interpret_effect(dz: float | None) -> str:
    if dz is None:
        return "not computable"
    magnitude = abs(dz)
    if magnitude < 0.2:
        return "negligible"
    if magnitude < 0.5:
        return "small"
    if magnitude < 0.8:
        return "medium"
    return "large"


def safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)
