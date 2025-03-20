"""Report generation: JSON, CSV, Markdown, HTML and a CI-friendly summary."""

from __future__ import annotations

import csv
import html
import io
from datetime import UTC, datetime

from ..metrics import KIND_DESCRIPTIONS


def run_to_dict(run, app, dataset, results, gate: dict | None = None) -> dict:
    """Machine-readable report of one evaluation run."""
    metrics = run.metrics or {}
    return {
        "schema": "rag-quality-monitor/run-report/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "run": {
            "id": run.id,
            "app_id": run.app_id,
            "app_name": getattr(app, "name", None),
            "app_version": getattr(app, "version_label", None),
            "dataset_id": run.dataset_id,
            "dataset_name": getattr(dataset, "name", None),
            "mode": run.mode,
            "status": run.status,
            "progress": run.progress,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "error": run.error,
        },
        "metrics": metrics,
        "metric_kinds": metrics.get("metric_kinds", {}),
        "metric_kind_descriptions": KIND_DESCRIPTIONS,
        "by_category": metrics.get("by_category", {}),
        "by_cohort": metrics.get("by_cohort", {}),
        "latency_ms": metrics.get("latency_ms", {}),
        "config_snapshot": run.config_snapshot or {},
        "usage": {
            "input_tokens": run.total_input_tokens,
            "output_tokens": run.total_output_tokens,
            "estimated_cost_usd": run.estimated_cost_usd,
            "cost_is_estimate": getattr(run, "cost_is_estimate", True),
        },
        "gate": gate,
        "results": [
            {
                "item_id": r.item_id,
                "question": r.question,
                "category": r.category,
                "cohorts": r.cohorts or [],
                "answerable": r.answerable,
                "answer": r.answer,
                "abstained": r.abstained,
                "retrieved": r.retrieved,
                "citations": r.citations,
                "metrics": r.metrics,
                "evidence": r.evidence,
                "latency_ms": r.latency_ms,
                "retrieval_latency_ms": r.retrieval_latency_ms,
                "generation_latency_ms": r.generation_latency_ms,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "error": r.error,
            }
            for r in results
        ],
    }


CSV_COLUMNS = [
    "run_id",
    "item_id",
    "category",
    "cohorts",
    "answerable",
    "question",
    "answer",
    "abstained",
    "recall_at_5",
    "precision_at_5",
    "token_f1",
    "faithfulness",
    "citation_support",
    "citation_structural_valid",
    "correct_abstention",
    "latency_ms",
    "input_tokens",
    "output_tokens",
]


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for result in report.get("results", []):
        metrics = result.get("metrics") or {}
        writer.writerow(
            [
                report["run"]["id"],
                result.get("item_id"),
                result.get("category"),
                "|".join(result.get("cohorts") or []),
                result.get("answerable"),
                result.get("question"),
                (result.get("answer") or "").replace("\n", " "),
                result.get("abstained"),
                metrics.get("recall_at_5"),
                metrics.get("precision_at_5"),
                metrics.get("token_f1"),
                metrics.get("faithfulness"),
                metrics.get("citation_support"),
                metrics.get("citation_structural_valid"),
                metrics.get("correct_abstention"),
                result.get("latency_ms"),
                result.get("input_tokens"),
                result.get("output_tokens"),
            ]
        )
    return buf.getvalue()


def _metric_rows(metrics: dict) -> list[tuple[str, object, object, str]]:
    rows = []
    for key, value in (metrics.get("metrics") or {}).items():
        if isinstance(value, dict) and "value" in value:
            rows.append((key, value.get("value"), value.get("n"), value.get("kind", "deterministic")))
    return sorted(rows)


def to_markdown(report: dict, gate: dict | None = None) -> str:
    run = report["run"]
    lines = [
        f"# Evaluation Report — Run #{run['id']}",
        "",
        f"**App:** {run['app_name']} ({run['app_version']}) · **Dataset:** {run['dataset_name']} · "
        f"**Mode:** `{run['mode']}` · **Status:** `{run['status']}`",
        "",
        f"Tokens: {report['usage']['input_tokens']} in / {report['usage']['output_tokens']} out · "
        f"Estimated cost: ${report['usage']['estimated_cost_usd']}"
        f"{' (estimate)' if report['usage'].get('cost_is_estimate') else ' (measured)'}",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Value | n | Kind |",
        "|---|---|---|---|",
    ]
    for key, value, n, kind in _metric_rows(report.get("metrics") or {}):
        shown = "n/a" if value is None else (f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append(f"| {key} | {shown} | {n} | {kind} |")
    lines += [
        "",
        "*Kind legend: deterministic = exact formula; reference_based = against a gold answer; "
        "heuristic = surface-overlap estimate, not verified ground truth; embedding_based = approximate "
        "similarity; judge = LLM opinion signal; operational = measured operational data.*",
    ]

    if gate:
        lines += [
            "",
            "## Release gate",
            "",
            f"**Verdict: {gate['verdict']}** — {gate['summary']}",
            "",
            "| Check | Status | Observed | Threshold | Evidence |",
            "|---|---|---|---|---|",
        ]
        for check in gate.get("checks", []):
            lines.append(
                f"| {check['metric']} ({check['type']}) | {check['status']} | {check.get('observed')} | "
                f"{check.get('threshold')} | {check.get('evidence')} |"
            )

    lines += [
        "",
        "## Per-question results",
        "",
        "| # | Category | Recall@5 | F1 | Faithfulness* | Citation support | Answer |",
        "|---|---|---|---|---|---|---|",
    ]
    for index, result in enumerate(report.get("results", []), 1):
        metrics = result.get("metrics") or {}
        answer = (result.get("answer") or "")[:120].replace("|", "\\|")
        lines.append(
            f"| {index} | {result.get('category')} | {metrics.get('recall_at_5')} | "
            f"{metrics.get('token_f1')} | {metrics.get('faithfulness')} | "
            f"{metrics.get('citation_support')} | {answer} |"
        )
    lines.append("")
    lines.append(
        "*Faithfulness is a heuristic token-overlap estimate, not verified ground truth. "
        "LLM-judge metrics are opinion signals and are labelled as such."
    )
    return "\n".join(lines)


def to_html(report: dict, gate: dict | None = None) -> str:
    run = report["run"]
    rows = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape('n/a' if value is None else f'{value}')}</td>"
        f"<td>{html.escape(str(n))}</td><td><span class='kind kind-{html.escape(str(kind))}'>{html.escape(str(kind))}</span></td></tr>"
        for key, value, n, kind in _metric_rows(report.get("metrics") or {})
    )
    gate_html = ""
    if gate:
        check_rows = "".join(
            f"<tr><td>{html.escape(str(c['metric']))} ({html.escape(str(c['type']))})</td>"
            f"<td class='verdict verdict-{html.escape(str(c['status']))}'>{html.escape(str(c['status']))}</td>"
            f"<td>{html.escape(str(c.get('observed')))}</td><td>{html.escape(str(c.get('threshold')))}</td>"
            f"<td>{html.escape(str(c.get('evidence')))}</td></tr>"
            for c in gate.get("checks", [])
        )
        gate_html = (
            f"<h2>Release gate: {html.escape(gate['verdict'])}</h2>"
            f"<p>{html.escape(gate.get('summary', ''))}</p>"
            "<table><tr><th>Check</th><th>Status</th><th>Observed</th><th>Threshold</th>"
            f"<th>Evidence</th></tr>{check_rows}</table>"
        )
    result_rows = "".join(
        f"<tr><td>{html.escape(str(i))}</td><td>{html.escape(str(r.get('category')))}</td>"
        f"<td>{html.escape(str((r.get('metrics') or {}).get('recall_at_5')))}</td>"
        f"<td>{html.escape(str((r.get('metrics') or {}).get('token_f1')))}</td>"
        f"<td>{html.escape(str((r.get('metrics') or {}).get('faithfulness')))}</td>"
        f"<td>{html.escape(str((r.get('metrics') or {}).get('citation_support')))}</td>"
        f"<td>{html.escape((r.get('answer') or '')[:160])}</td></tr>"
        for i, r in enumerate(report.get("results", []), 1)
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evaluation Report — Run #{run["id"]}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#111}}
h1{{margin-bottom:.25rem}} .meta{{color:#555;margin-top:0}}
table{{border-collapse:collapse;width:100%;margin:.75rem 0}}
td,th{{border:1px solid #d0d7de;padding:.4rem .6rem;text-align:left;vertical-align:top;font-size:.92rem}}
th{{background:#f6f8fa}}
.kind{{font-size:.78rem;padding:.1rem .45rem;border-radius:.99rem;background:#eef2f6}}
.kind-heuristic{{background:#fff3cd}} .kind-judge{{background:#e7dcf7}}
.kind-operational{{background:#d1ecf1}} .kind-embedding_based{{background:#d4edda}}
.verdict{{font-weight:600}} .verdict-FAIL{{color:#b42318}} .verdict-PASS{{color:#067647}}
.verdict-INCONCLUSIVE{{color:#b54708}}
.note{{background:#fff8e6;border-left:4px solid #f0b429;padding:.6rem .8rem;margin:1rem 0}}
</style></head>
<body>
<h1>Evaluation Report — Run #{run["id"]}</h1>
<p class="meta">{html.escape(str(run["app_name"]))} ({html.escape(str(run["app_version"]))}) ·
Dataset {html.escape(str(run["dataset_name"]))} · Mode {html.escape(str(run["mode"]))} ·
Status {html.escape(str(run["status"]))}</p>
<p>Tokens: {report["usage"]["input_tokens"]} in / {report["usage"]["output_tokens"]} out ·
Estimated cost: ${report["usage"]["estimated_cost_usd"]}
{" (estimate)" if report["usage"].get("cost_is_estimate") else " (measured)"}</p>
{gate_html}
<h2>Aggregate metrics</h2>
<table><tr><th>Metric</th><th>Value</th><th>n</th><th>Kind</th></tr>{rows}</table>
<h2>Per-question results</h2>
<table><tr><th>#</th><th>Category</th><th>Recall@5</th><th>F1</th><th>Faithfulness*</th>
<th>Citation support</th><th>Answer</th></tr>{result_rows}</table>
<div class="note">*Faithfulness is a heuristic token-overlap estimate, not verified ground truth.
LLM-judge metrics are opinion signals. A citation pointing at an existing document is not proof of support.</div>
</body></html>"""


def to_ci_summary(report: dict, gate: dict | None = None) -> dict:
    """Compact machine-readable summary for CI systems."""
    metrics = report.get("metrics") or {}
    flat = {}
    for key, value in (metrics.get("metrics") or {}).items():
        flat[key] = {"value": value.get("value"), "n": value.get("n"), "kind": value.get("kind")}
    return {
        "schema": "rag-quality-monitor/ci-summary/v1",
        "run_id": report["run"]["id"],
        "app_version": report["run"]["app_version"],
        "dataset": report["run"]["dataset_name"],
        "status": report["run"]["status"],
        "verdict": (gate or {}).get("verdict"),
        "summary": (gate or {}).get("summary"),
        "checks": [
            {
                "metric": c["metric"],
                "type": c["type"],
                "status": c["status"],
                "observed": c.get("observed"),
                "threshold": c.get("threshold"),
                "severity": c.get("severity"),
                "evidence": c.get("evidence"),
            }
            for c in (gate or {}).get("checks", [])
        ],
        "metrics": flat,
        "usage": report.get("usage", {}),
    }
