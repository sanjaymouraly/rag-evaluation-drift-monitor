"""Release quality gates.

A gate evaluates a *candidate* run against a policy and, when the policy
defines relative rules, against an approved *baseline* run.

Verdicts
--------
``PASS``          every hard rule passed, every warning rule passed or only warned.
``FAIL``          at least one hard rule failed.
``INCONCLUSIVE``  evidence is missing: the metric was not computed, the sample
                  count is below the minimum, or a relative rule has no approved
                  baseline. Missing evidence can never produce a PASS.

Rule types
----------
``min``          absolute lower bound (e.g. faithfulness >= 0.90)
``max``          absolute upper bound (e.g. p95 latency <= 800 ms)
``max_drop``     the metric may not fall more than ``threshold`` below the baseline
``max_increase`` the metric may not rise more than ``threshold`` above the baseline
``min_delta``    the metric may not be *lower* than the baseline by more than ``threshold``
                 (alias of max_drop kept for readability)

Every rule may be scoped to a category or a cohort, which is how critical
question classes get their own gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .stats import (
    benjamini_hochberg,
    bootstrap_ci,
    cohens_dz,
    interpret_effect,
    safe_round,
    wilcoxon_p,
)

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"

RULE_TYPES = ("min", "max", "max_drop", "max_increase", "min_delta")
SEVERITIES = ("hard", "warn")


@dataclass
class RunView:
    """The view of a run the gate needs: aggregates and per-item results."""

    run_id: int
    metrics: dict = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)
    label: str = ""

    def metric(self, name: str) -> dict:
        return self.metrics.get(name) or {}


def _scope_matches(result: dict, scope: dict) -> bool:
    if not scope:
        return True
    categories = scope.get("categories") or ([scope["category"]] if scope.get("category") else [])
    cohorts = scope.get("cohorts") or ([scope["cohort"]] if scope.get("cohort") else [])
    if categories and result.get("category") not in categories:
        return False
    if cohorts:
        result_cohorts = set(result.get("cohorts") or [])
        if not (result_cohorts & set(cohorts)):
            return False
    return True


def _scoped_metric(view: RunView | None, metric: str, scope: dict) -> dict:
    """Mean and n of a metric restricted to a scope (category/cohort)."""
    if view is None:
        return {"value": None, "n": 0}
    values = []
    for result in view.results:
        if not _scope_matches(result, scope):
            continue
        value = (result.get("metrics") or {}).get(metric)
        if value is not None:
            values.append(float(value))
    if not values:
        return {"value": None, "n": 0}
    return {"value": sum(values) / len(values), "n": len(values)}


def _paired(view_a: RunView | None, view_b: RunView | None, metric: str, scope: dict) -> dict:
    """Paired per-item differences (candidate - baseline) for one metric."""
    if view_a is None or view_b is None:
        return {"candidate": [], "baseline": [], "keys": []}

    def index(view: RunView) -> dict:
        out = {}
        for result in view.results:
            key = result.get("item_id") or result.get("question")
            out[str(key)] = result
        return out

    index_a, index_b = index(view_a), index(view_b)
    candidates, baselines, keys = [], [], []
    for key in sorted(set(index_a) & set(index_b)):
        ra, rb = index_a[key], index_b[key]
        if not _scope_matches(ra, scope) and scope:
            continue
        va = (ra.get("metrics") or {}).get(metric)
        vb = (rb.get("metrics") or {}).get(metric)
        if va is None or vb is None:
            continue
        candidates.append(float(va))
        baselines.append(float(vb))
        keys.append(key)
    return {"candidate": candidates, "baseline": baselines, "keys": keys}


def _describe(rule: dict) -> str:
    scope = rule.get("scope") or {}
    parts = []
    if scope.get("category"):
        parts.append(f"category={scope['category']}")
    if scope.get("categories"):
        parts.append(f"categories={','.join(scope['categories'])}")
    if scope.get("cohort"):
        parts.append(f"cohort={scope['cohort']}")
    if scope.get("cohorts"):
        parts.append(f"cohorts={','.join(scope['cohorts'])}")
    return f" [{' '.join(parts)}]" if parts else ""


def evaluate_gate(
    rules: list[dict],
    min_samples: int,
    candidate: RunView,
    baseline: RunView | None = None,
    apply_multiple_comparison_correction: bool = True,
) -> dict:
    """Evaluate a policy against a candidate run."""
    checks: list[dict] = []
    has_fail = False
    has_inconclusive = False
    p_values: list[tuple[int, float]] = []

    for rule in rules:
        metric = rule.get("metric")
        kind = rule.get("type", "min")
        severity = rule.get("severity", "hard")
        scope = rule.get("scope") or {}
        required_n = max(int(min_samples or 0), int(rule.get("min_samples", 0) or 0))
        check = {
            "metric": metric,
            "type": kind,
            "severity": severity,
            "threshold": rule.get("threshold"),
            "tolerance": rule.get("tolerance"),
            "scope": scope,
            "label": rule.get("label") or f"{metric} {kind} {rule.get('threshold')}{_describe(rule)}",
            "observed": None,
            "baseline_value": None,
            "observed_change": None,
            "n": 0,
            "ci": None,
            "p_value": None,
            "effect_size": None,
            "effect_magnitude": None,
            "status": INCONCLUSIVE,
            "evidence": "",
        }
        if not metric or kind not in RULE_TYPES:
            check["evidence"] = f"Invalid rule: metric={metric!r}, type={kind!r}."
            has_inconclusive = True
            checks.append(check)
            continue

        scoped = bool(scope)
        if scoped:
            observed = _scoped_metric(candidate, metric, scope)
            baseline_observed = _scoped_metric(baseline, metric, scope)
        else:
            observed = candidate.metric(metric)
            baseline_observed = baseline.metric(metric) if baseline is not None else {}

        value = observed.get("value")
        n = int(observed.get("n", 0) or 0)
        check["observed"] = safe_round(value)
        check["n"] = n
        check["baseline_value"] = safe_round(baseline_observed.get("value"))
        check["baseline_n"] = int(baseline_observed.get("n", 0) or 0)

        if value is None:
            check["evidence"] = (
                f"Insufficient evidence: metric '{metric}' was not computed "
                f"(value=None, n={n}). Required missing evidence must not pass."
            )
            has_inconclusive = True
            checks.append(check)
            continue
        if n < required_n:
            check["evidence"] = (
                f"Insufficient evidence: n={n} is below the required minimum of "
                f"{required_n}. Required missing evidence must not pass."
            )
            has_inconclusive = True
            checks.append(check)
            continue

        if kind in ("max_drop", "max_increase", "min_delta"):
            bvalue = baseline_observed.get("value")
            if bvalue is None:
                check["evidence"] = (
                    "Relative rule requires an approved baseline with this metric "
                    "(and the same scope); none is available."
                )
                has_inconclusive = True
                checks.append(check)
                continue
            paired = _paired(candidate, baseline, metric, scope)
            diffs = [c - b for c, b in zip(paired["candidate"], paired["baseline"], strict=True)]
            if diffs:
                lo, hi = bootstrap_ci(diffs)
                check["ci"] = [safe_round(lo), safe_round(hi)]
                check["p_value"] = safe_round(wilcoxon_p(diffs))
                p_values.append((len(checks), check["p_value"]))
                dz = cohens_dz(diffs)
                check["effect_size"] = safe_round(dz)
                check["effect_magnitude"] = interpret_effect(dz)
                check["n_paired"] = len(diffs)
            else:
                check["n_paired"] = 0
            threshold = float(rule.get("threshold", 0.0))
            tolerance = float(rule.get("tolerance", 0.0) or 0.0)
            change = value - bvalue if kind == "max_increase" else bvalue - value  # max_drop / min_delta
            check["observed_change"] = safe_round(change)
            ci = check["ci"]
            if (
                ci
                and tolerance > 0
                and ci[0] is not None
                and ci[1] is not None
                and -tolerance <= ci[0]
                and ci[1] <= tolerance
            ):
                check["status"] = PASS
                check["evidence"] = (
                    f"Change {change:+.4f}; paired 95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}] "
                    f"lies within +/-{tolerance} tolerance — consistent with noise, "
                    f"not a proven regression."
                )
            elif change <= threshold:
                check["status"] = PASS
                extra = f" (paired CI {check['ci']}, p={check['p_value']})" if check["ci"] else ""
                check["evidence"] = (
                    f"Candidate {value:.4f} vs baseline {bvalue:.4f}: change "
                    f"{change:+.4f} within the allowed {threshold}{extra}."
                )
            else:
                check["status"] = FAIL
                extra = (
                    f" (paired CI {check['ci']}, p={check['p_value']}, effect {check['effect_magnitude']})"
                    if check["ci"]
                    else ""
                )
                check["evidence"] = (
                    f"REGRESSION: candidate {value:.4f} vs baseline {bvalue:.4f}: change "
                    f"{change:+.4f} exceeds the allowed {threshold}{extra}."
                )
        elif kind == "min":
            threshold = float(rule["threshold"])
            ok = value >= threshold
            check["status"] = PASS if ok else FAIL
            check["evidence"] = (
                f"Candidate {value:.4f} {'>=' if ok else '<'} required {threshold} "
                f"(n={n}{', ' + _describe(scope) if scope else ''})."
            )
        else:  # max
            threshold = float(rule["threshold"])
            ok = value <= threshold
            check["status"] = PASS if ok else FAIL
            check["evidence"] = (
                f"Candidate {value:.4f} {'<=' if ok else '>'} allowed maximum {threshold} "
                f"(n={n}{', ' + _describe(scope) if scope else ''})."
            )

        if check["status"] == FAIL and severity == "hard":
            has_fail = True
        checks.append(check)

    if apply_multiple_comparison_correction and p_values:
        significant = [(index, p) for index, p in p_values if p is not None]
        adjusted = benjamini_hochberg([p for _, p in significant])
        for (index, _), adj in zip(significant, adjusted, strict=True):
            checks[index]["p_value_adjusted"] = safe_round(adj)

    if has_fail:
        verdict = FAIL
    elif has_inconclusive:
        verdict = INCONCLUSIVE
    else:
        verdict = PASS

    warnings = [c["label"] for c in checks if c["status"] == FAIL and c["severity"] == "warn"]
    passed = sum(1 for c in checks if c["status"] == PASS)
    failed = sum(1 for c in checks if c["status"] == FAIL)
    inconclusive = sum(1 for c in checks if c["status"] == INCONCLUSIVE)
    summary = f"{verdict}: {passed}/{len(checks)} checks passed"
    if failed:
        summary += f", {failed} failed"
    if inconclusive:
        summary += f", {inconclusive} inconclusive"
    if warnings:
        summary += f" (warnings: {', '.join(warnings)})"
    if verdict == INCONCLUSIVE:
        summary += " — missing or insufficient evidence; a release cannot be approved on this evidence"
    return {
        "verdict": verdict,
        "checks": checks,
        "summary": summary,
        "n_passed": passed,
        "n_failed": failed,
        "n_inconclusive": inconclusive,
    }


#: Demonstration defaults. These are *examples*, not universal industry standards —
#: tune them to your own benchmark before using them in a real pipeline.
DEFAULT_POLICY_RULES: list[dict] = [
    {
        "metric": "recall_at_5",
        "type": "min",
        "threshold": 0.80,
        "severity": "hard",
        "label": "Recall@5 must stay at or above 0.80",
    },
    {
        "metric": "recall_at_5",
        "type": "max_drop",
        "threshold": 0.05,
        "tolerance": 0.02,
        "severity": "hard",
        "label": "Recall@5 must not drop more than 0.05 vs the approved baseline",
    },
    {
        "metric": "citation_support",
        "type": "min",
        "threshold": 0.80,
        "severity": "hard",
        "label": "Citation support must stay at or above 0.80",
    },
    {
        "metric": "token_f1",
        "type": "min",
        "threshold": 0.30,
        "severity": "hard",
        "label": "Token F1 must stay at or above 0.30",
    },
    {
        "metric": "latency_p95_ms",
        "type": "max",
        "threshold": 5000,
        "severity": "warn",
        "label": "p95 latency must stay below 5000 ms",
    },
    {
        "metric": "estimated_cost_usd",
        "type": "max",
        "threshold": 1.0,
        "severity": "warn",
        "label": "Estimated run cost must stay below USD 1.00",
    },
]
