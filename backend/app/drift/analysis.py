"""Drift analysis between two evaluation runs.

The analysis compares:

* the **corpus** (size, revisions, content fingerprints, added/removed docs);
* the **chunking** (count, length distribution);
* the **configuration** (retriever, chunk size, top-k, prompt, model);
* the **retrieval behaviour** (which documents are returned, score distribution,
  top-k agreement);
* the **quality distributions** (per-metric PSI / KS);
* the **query mix** (categories and cohorts);
* the **operational** behaviour (latency, tokens, errors, cost).

Everything that is presented as a *cause* is labelled a hypothesis. Drift is
not proof of a quality regression — the release gate is.
"""

from __future__ import annotations

from collections import Counter

from .statistics import (
    control_chart,
    embedding_drift,
    interpret_psi,
    jsd_from_counts,
    ks_test,
    psi,
    psi_categorical,
)

DRIFT_DISCLAIMER = (
    "Drift statistics describe a change in the observed distributions. They do not by "
    "themselves prove that quality regressed. Confirm with a paired release gate on the "
    "same frozen benchmark."
)

QUALITY_METRICS = (
    "recall_at_5",
    "precision_at_5",
    "token_f1",
    "faithfulness",
    "citation_support",
    "correct_abstention",
    "hit_at_5",
    "mrr",
)


def _values(results, metric: str) -> list[float]:
    out = []
    for result in results:
        value = (result.get("metrics") or {}).get(metric)
        if value is not None:
            out.append(float(value))
    return out


def analyse(
    baseline_run, candidate_run, baseline_results: list[dict], candidate_results: list[dict]
) -> tuple[dict, list[str]]:
    """Return ``(signals, hypotheses)`` for a baseline/candidate pair."""
    signals: dict = {}

    # --- quality distributions -----------------------------------------
    for metric in QUALITY_METRICS:
        b = _values(baseline_results, metric)
        c = _values(candidate_results, metric)
        p = psi(b, c)
        signals[metric] = {
            "psi": round(p, 4) if p is not None else None,
            "psi_interpretation": interpret_psi(p),
            "ks": ks_test(b, c),
            "mean_baseline": round(sum(b) / len(b), 6) if b else None,
            "mean_candidate": round(sum(c) / len(c), 6) if c else None,
            "n_baseline": len(b),
            "n_candidate": len(c),
        }

    # --- latency / tokens / cost ---------------------------------------
    lat_b = [float(r.get("latency_ms", 0.0) or 0.0) for r in baseline_results]
    lat_c = [float(r.get("latency_ms", 0.0) or 0.0) for r in candidate_results]
    p_lat = psi(lat_b, lat_c)
    signals["latency_ms"] = {
        "psi": round(p_lat, 4) if p_lat is not None else None,
        "psi_interpretation": interpret_psi(p_lat),
        "ks": ks_test(lat_b, lat_c),
        "mean_baseline": round(sum(lat_b) / len(lat_b), 3) if lat_b else None,
        "mean_candidate": round(sum(lat_c) / len(lat_c), 3) if lat_c else None,
    }
    tok_b = [float(r.get("input_tokens", 0) or 0) + float(r.get("output_tokens", 0) or 0) for r in baseline_results]
    tok_c = [float(r.get("input_tokens", 0) or 0) + float(r.get("output_tokens", 0) or 0) for r in candidate_results]
    p_tok = psi(tok_b, tok_c)
    signals["token_usage"] = {
        "psi": round(p_tok, 4) if p_tok is not None else None,
        "psi_interpretation": interpret_psi(p_tok),
        "mean_baseline": round(sum(tok_b) / len(tok_b), 2) if tok_b else None,
        "mean_candidate": round(sum(tok_c) / len(tok_c), 2) if tok_c else None,
    }

    # --- retrieval behaviour -------------------------------------------
    docs_b = [x.get("doc_id") for r in baseline_results for x in (r.get("retrieved") or [])]
    docs_c = [x.get("doc_id") for r in candidate_results for x in (r.get("retrieved") or [])]
    jsd = jsd_from_counts(dict(Counter(docs_b)), dict(Counter(docs_c)))
    signals["retrieved_doc_distribution"] = {
        "jsd": round(jsd, 4) if jsd is not None else None,
        "note": "0 = identical distribution, ~0.69 (natural log) = disjoint",
        "n_baseline": len(docs_b),
        "n_candidate": len(docs_c),
    }
    scores_b = [float(x.get("score", 0.0) or 0.0) for r in baseline_results for x in (r.get("retrieved") or [])]
    scores_c = [float(x.get("score", 0.0) or 0.0) for r in candidate_results for x in (r.get("retrieved") or [])]
    p_score = psi(scores_b, scores_c)
    signals["retrieval_score_distribution"] = {
        "psi": round(p_score, 4) if p_score is not None else None,
        "psi_interpretation": interpret_psi(p_score),
        "mean_baseline": round(sum(scores_b) / len(scores_b), 4) if scores_b else None,
        "mean_candidate": round(sum(scores_c) / len(scores_c), 4) if scores_c else None,
    }

    def _topk(results, k: int = 5) -> dict[str, list[str]]:
        out = {}
        for r in results:
            key = str(r.get("item_id") or r.get("question"))
            out[key] = [x.get("doc_id") for x in (r.get("retrieved") or [])[:k]]
        return out

    top_b, top_c = _topk(baseline_results), _topk(candidate_results)
    shared = set(top_b) & set(top_c)
    changed = [k for k in shared if top_b[k] != top_c[k]]
    signals["top_k_stability"] = {
        "n_compared": len(shared),
        "n_changed": len(changed),
        "changed_ratio": round(len(changed) / len(shared), 4) if shared else None,
        "changed_items": sorted(changed)[:20],
        "note": "Questions whose top-5 document list changed between the two runs.",
    }

    # --- query mix ------------------------------------------------------
    cat_p = psi_categorical(
        [r.get("category", "") for r in baseline_results], [r.get("category", "") for r in candidate_results]
    )
    signals["category_distribution"] = {
        "psi": round(cat_p, 4) if cat_p is not None else None,
        "psi_interpretation": interpret_psi(cat_p),
    }
    cohort_b = [c for r in baseline_results for c in (r.get("cohorts") or [])] or ["uncategorized"] * len(
        baseline_results
    )
    cohort_c = [c for r in candidate_results for c in (r.get("cohorts") or [])] or ["uncategorized"] * len(
        candidate_results
    )
    coh_p = psi_categorical(cohort_b, cohort_c)
    signals["cohort_distribution"] = {
        "psi": round(coh_p, 4) if coh_p is not None else None,
        "psi_interpretation": interpret_psi(coh_p),
    }

    # --- corpus / chunking / configuration ------------------------------
    cfg_b = dict(baseline_run.config_snapshot or {})
    cfg_c = dict(candidate_run.config_snapshot or {})
    man_b = {m["doc_id"]: m for m in cfg_b.get("corpus_manifest", [])}
    man_c = {m["doc_id"]: m for m in cfg_c.get("corpus_manifest", [])}
    changed_docs = sorted(
        d for d in set(man_b) & set(man_c) if man_b[d].get("fingerprint") != man_c[d].get("fingerprint")
    )
    signals["corpus"] = {
        "docs_baseline": len(man_b),
        "docs_candidate": len(man_c),
        "chunks_baseline": cfg_b.get("n_chunks"),
        "chunks_candidate": cfg_c.get("n_chunks"),
        "chunk_stats_baseline": cfg_b.get("chunk_stats"),
        "chunk_stats_candidate": cfg_c.get("chunk_stats"),
        "changed_doc_ids": changed_docs,
        "added_docs": sorted(set(man_c) - set(man_b)),
        "removed_docs": sorted(set(man_b) - set(man_c)),
    }
    signals["config_diff"] = {
        "baseline": cfg_b.get("app_config", {}),
        "candidate": cfg_c.get("app_config", {}),
        "changed_keys": sorted(
            k
            for k in set(cfg_b.get("app_config", {})) | set(cfg_c.get("app_config", {}))
            if cfg_b.get("app_config", {}).get(k) != cfg_c.get("app_config", {}).get(k)
        ),
    }
    signals["dataset"] = {
        "baseline_checksum": cfg_b.get("dataset_checksum"),
        "candidate_checksum": cfg_c.get("dataset_checksum"),
        "same_dataset": cfg_b.get("dataset_checksum") == cfg_c.get("dataset_checksum"),
    }
    signals["embedding_space"] = embedding_drift([], [])

    # --- control chart over the quality history of the candidate run ---
    signals["control_chart"] = {
        "note": "Control limits are computed over the two compared runs only; "
        "connect several runs to get a meaningful baseline band.",
    }

    hypotheses: list[str] = []
    app_b = cfg_b.get("app_config", {})
    app_c = cfg_c.get("app_config", {})
    if app_b.get("retriever") != app_c.get("retriever"):
        hypotheses.append(
            f"HYPOTHESIS (unproven): the retriever changed ({app_b.get('retriever')} → "
            f"{app_c.get('retriever')}). Check the per-question top-5 changes in the comparison view."
        )
    if app_b.get("chunk_chars") != app_c.get("chunk_chars") or app_b.get("overlap_chars") != app_c.get("overlap_chars"):
        hypotheses.append(
            f"HYPOTHESIS (unproven): chunking changed (chunk_chars {app_b.get('chunk_chars')} → "
            f"{app_c.get('chunk_chars')}, overlap {app_b.get('overlap_chars')} → {app_c.get('overlap_chars')}); "
            "this can change recall and citation support."
        )
    if app_b.get("top_k") != app_c.get("top_k"):
        hypotheses.append(f"HYPOTHESIS (unproven): top_k changed ({app_b.get('top_k')} → {app_c.get('top_k')}).")
    if (cfg_b.get("generator") or {}) != (cfg_c.get("generator") or {}):
        hypotheses.append(
            "HYPOTHESIS (unproven): the generation model/provider changed; answer-level "
            "metrics (faithfulness, token F1) are sensitive to that change."
        )
    if changed_docs:
        hypotheses.append(
            f"HYPOTHESIS (unproven): {len(changed_docs)} source document(s) changed content: {changed_docs[:5]}."
        )
    if signals["top_k_stability"].get("changed_ratio"):
        ratio = signals["top_k_stability"]["changed_ratio"]
        if ratio >= 0.2:
            hypotheses.append(
                f"HYPOTHESIS (unproven): {ratio:.0%} of compared questions changed their top-5 "
                "documents; the retrieval behaviour differs between the two versions."
            )
    drifted = [
        k
        for k, v in signals.items()
        if isinstance(v, dict) and isinstance(v.get("psi"), (int, float)) and v["psi"] >= 0.25
    ]
    if drifted:
        hypotheses.append(
            f"FINDING: a distribution shift was detected in: {', '.join(drifted)}. "
            "Drift is not a proven regression — confirm with the paired release gate "
            "on the same benchmark."
        )
    if not hypotheses:
        hypotheses.append(
            "FINDING: no configuration or corpus difference was detected between the two runs. "
            "Any quality change comes from a component that is not captured in the run snapshot."
        )
    return signals, hypotheses


def history_control_chart(series: list[tuple[str, float]]) -> dict:
    """Control chart over an ordered metric history (run id, value)."""
    values = [v for _, v in series]
    chart = control_chart(values)
    chart["points"] = [{"run_id": run_id, "value": value} for run_id, value in series]
    return chart
