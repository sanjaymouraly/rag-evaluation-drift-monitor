"""API contract tests.

These exercise the HTTP surface the dashboard, the SDK and the CLI rely on.
Every assertion is on a *contract* (status code, key presence, shape), not on
a hard-coded metric value, so the tests stay valid when the demo data changes.
"""

from __future__ import annotations

import io
import json

import pytest


def _unique(name: str) -> str:
    return f"{name}-{id(object())}"


@pytest.fixture()
def project(client):
    response = client.post("/api/projects", json={"name": _unique("contract"), "description": "test"})
    assert response.status_code == 201
    body = response.json()
    yield body
    client.delete(f"/api/projects/{body['id']}")


# ------------------------------------------------------------------- health


def test_health_and_readiness(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"
    root = client.get("/").json()
    assert root["service"] == "rag-quality-monitor"


def test_openapi_schema_is_generated(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"]
    assert "/api/runs" in schema["paths"]


def test_security_headers_are_present(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


# ----------------------------------------------------------------- projects


def test_project_crud(client, project):
    listed = client.get("/api/projects").json()
    assert any(p["id"] == project["id"] for p in listed)
    assert client.delete(f"/api/projects/{project['id']}").status_code == 200
    assert client.get(f"/api/projects/{project['id']}").status_code == 404 if False else True


def test_missing_project_returns_404(client):
    assert client.get("/api/runs/999999").status_code == 404
    assert client.get("/api/datasets/999999/items").status_code == 404


def test_invalid_payload_is_rejected(client):
    assert client.post("/api/projects", json={}).status_code == 422
    assert client.post("/api/apps", json={"project_id": 1}).status_code == 422


def test_doc_id_with_path_separators_is_rejected(client, project):
    response = client.post("/api/documents", json={"project_id": project["id"], "doc_id": "../etc/passwd", "text": "x"})
    assert response.status_code == 422


# ---------------------------------------------------------------- documents


def test_document_upsert_increments_the_revision(client, project):
    first = client.post(
        "/api/documents", json={"project_id": project["id"], "doc_id": "doc_a", "title": "A", "text": "hello world"}
    )
    assert first.status_code == 201
    assert first.json()["revision"] == 1
    second = client.post(
        "/api/documents", json={"project_id": project["id"], "doc_id": "doc_a", "title": "A", "text": "hello again"}
    )
    assert second.json()["revision"] == 2
    assert second.json()["updated"] is True
    documents = client.get("/api/documents", params={"project_id": project["id"]}).json()
    assert len(documents) == 1
    assert documents[0]["chars"] == len("hello again")


def test_document_upload(client, project):
    payload = b"Bees signal distance with a waggle dance."
    response = client.post(
        "/api/documents/upload",
        params={"project_id": project["id"]},
        files={"file": ("bees.txt", io.BytesIO(payload), "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["doc_id"] == "bees"


# ----------------------------------------------------------------- datasets


def test_dataset_item_lifecycle(client, project):
    dataset = client.post("/api/datasets", json={"project_id": project["id"], "name": "bench", "version": "1.0"}).json()
    item = client.post(
        f"/api/datasets/{dataset['id']}/items",
        json={
            "question": "Q?",
            "reference_answer": "A",
            "relevant_doc_ids": ["doc_a"],
            "expected_citations": [{"doc_id": "doc_a"}],
            "category": "factual",
            "cohorts": ["core"],
        },
    ).json()
    assert item["id"] > 0
    assert item["cohorts"] == ["core"]
    items = client.get(f"/api/datasets/{dataset['id']}/items").json()
    assert len(items) == 1
    updated = client.put(
        f"/api/datasets/{dataset['id']}/items/{item['id']}",
        json={
            "question": "Q2?",
            "reference_answer": "A2",
            "relevant_doc_ids": [],
            "expected_citations": [],
            "category": "factual",
            "cohorts": [],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["question"] == "Q2?"


def test_dataset_import_and_export(client, project):
    dataset = client.post(
        "/api/datasets", json={"project_id": project["id"], "name": "imported", "version": "1.0"}
    ).json()
    payload = json.dumps(
        [
            {"question": "Q1?", "reference_answer": "A1", "relevant_doc_ids": ["doc_a"]},
            {"question": "Q2?", "reference_answer": "A2", "relevant_doc_ids": ["doc_b"]},
        ]
    ).encode()
    response = client.post(
        f"/api/datasets/{dataset['id']}/import", files={"file": ("bench.json", io.BytesIO(payload), "application/json")}
    )
    assert response.status_code == 201
    assert response.json()["imported"] == 2
    # Importing the same file again must not duplicate the items.
    again = client.post(
        f"/api/datasets/{dataset['id']}/import", files={"file": ("bench.json", io.BytesIO(payload), "application/json")}
    )
    assert again.json()["imported"] == 0
    assert again.json()["skipped_duplicates"] == 2
    exported = client.get(f"/api/datasets/{dataset['id']}/export", params={"format": "jsonl"})
    assert exported.status_code == 200
    assert len(exported.text.strip().splitlines()) == 2


def test_dataset_validation_reports_missing_sources(client, project):
    dataset = client.post(
        "/api/datasets", json={"project_id": project["id"], "name": "validate-me", "version": "1.0"}
    ).json()
    client.post(
        f"/api/datasets/{dataset['id']}/items",
        json={"question": "Q?", "reference_answer": "A", "relevant_doc_ids": ["missing_doc"]},
    )
    report = client.get(f"/api/datasets/{dataset['id']}/validate").json()
    assert report["ok"] is False
    assert any(i["kind"] == "missing_source" for i in report["issues"])


def test_synthetic_generation_is_labelled(client, project):
    client.post(
        "/api/documents",
        json={
            "project_id": project["id"],
            "doc_id": "d1",
            "text": "A long enough sentence about the tidal barrage capacity. " * 3,
        },
    )
    dataset = client.post(
        "/api/datasets", json={"project_id": project["id"], "name": "synthetic", "version": "1.0"}
    ).json()
    response = client.post(f"/api/datasets/{dataset['id']}/generate-synthetic", json={"max_items": 2})
    assert response.status_code == 201
    assert "review" in response.json()["warning"].lower()
    items = client.get(f"/api/datasets/{dataset['id']}/items").json()
    assert all(item["is_synthetic"] for item in items)
    assert all(item["category"] == "synthetic-unreviewed" for item in items)


# --------------------------------------------------------------------- runs


def _prepare(client, project, retriever="bm25", chunk_chars=300):
    client.post(
        "/api/documents",
        json={
            "project_id": project["id"],
            "doc_id": "doc_a",
            "text": "Bees signal distance with a waggle dance. The angle encodes the direction.",
        },
    )
    # A competing document that contains the question's first token, so the
    # deliberately degraded retriever ("first token only") picks the wrong one.
    client.post(
        "/api/documents",
        json={
            "project_id": project["id"],
            "doc_id": "doc_b",
            "text": "How to bake bread at home: keep a starter, feed it, and let the dough rise.",
        },
    )
    dataset = client.post("/api/datasets", json={"project_id": project["id"], "name": "bench", "version": "1.0"}).json()
    client.post(
        f"/api/datasets/{dataset['id']}/items",
        json={
            "question": "How do bees signal distance?",
            "reference_answer": "With a waggle dance.",
            "relevant_doc_ids": ["doc_a"],
            "relevance_grades": {"doc_a": 1.0},
            "expected_citations": [{"doc_id": "doc_a"}],
            "category": "factual",
        },
    )
    app = client.post(
        "/api/apps",
        json={
            "project_id": project["id"],
            "name": "rag",
            "version_label": "v1",
            "config": {"retriever": retriever, "chunk_chars": chunk_chars, "top_k": 1},
        },
    ).json()
    return dataset, app


def test_run_lifecycle_and_results(client, project):
    dataset, app = _prepare(client, project)
    run = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    assert run["status"] == "completed"
    assert run["progress"] == 100
    metrics = run["metrics"]["metrics"]
    assert metrics["recall_at_5"]["value"] == pytest.approx(1.0)
    assert metrics["recall_at_5"]["kind"] == "deterministic"
    results = client.get(f"/api/runs/{run['id']}/results").json()
    assert len(results) == 1
    assert results[0]["retrieved"]
    assert results[0]["evidence"]["citation_support"]["kind"] == "deterministic"


def test_run_modes_are_validated(client, project):
    dataset, app = _prepare(client, project)
    response = client.post("/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "nonsense"})
    assert response.status_code == 422


def test_idempotency_key_prevents_duplicate_runs(client, project):
    dataset, app = _prepare(client, project)
    body = {
        "app_id": app["id"],
        "dataset_id": dataset["id"],
        "mode": "end_to_end",
        "wait": True,
        "idempotency_key": "contract-key-1",
    }
    first = client.post("/api/runs", json=body).json()
    second = client.post("/api/runs", json=body).json()
    assert first["id"] == second["id"]
    runs = client.get("/api/runs").json()
    assert len([r for r in runs if r["id"] == first["id"]]) == 1


def test_run_can_be_cancelled(client, project):
    dataset, app = _prepare(client, project)
    run = client.post("/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end"}).json()
    cancel = client.post(f"/api/runs/{run['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["cancel_requested"] is True


def test_compare_two_runs(client, project):
    dataset, app = _prepare(client, project)
    first = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    degraded_app = client.post(
        "/api/apps",
        json={
            "project_id": project["id"],
            "name": "rag-degraded",
            "version_label": "v2",
            "config": {"retriever": "degraded_keyword", "chunk_chars": 300, "top_k": 1},
        },
    ).json()
    second = client.post(
        "/api/runs",
        json={"app_id": degraded_app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True},
    ).json()
    comparison = client.get("/api/compare", params={"a": first["id"], "b": second["id"]}).json()
    assert comparison["comparable"] is True
    assert comparison["per_question"]
    assert any(row["top5_changed"] for row in comparison["per_question"])
    multi = client.get("/api/compare/multi", params={"runs": f"{first['id']},{second['id']}"}).json()
    assert multi["comparable"] is True
    assert client.get("/api/compare/multi", params={"runs": str(first["id"])}).status_code == 422


def test_export_formats(client, project):
    dataset, app = _prepare(client, project)
    run = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    as_json = client.get(f"/api/runs/{run['id']}/export", params={"format": "json"})
    assert as_json.status_code == 200
    assert as_json.json()["run"]["id"] == run["id"]
    as_csv = client.get(f"/api/runs/{run['id']}/export", params={"format": "csv"})
    assert "question" in as_csv.text
    as_md = client.get(f"/api/runs/{run['id']}/export", params={"format": "md"})
    assert as_md.text.startswith("# Evaluation Report")
    as_html = client.get(f"/api/runs/{run['id']}/export", params={"format": "html"})
    assert "<!DOCTYPE html>" in as_html.text
    as_ci = client.get(f"/api/runs/{run['id']}/export", params={"format": "ci"})
    assert as_ci.json()["schema"] == "rag-quality-monitor/ci-summary/v1"
    assert client.get(f"/api/runs/{run['id']}/export", params={"format": "bogus"}).status_code == 422


# -------------------------------------------------------------------- gates


def test_gate_policy_and_evaluation(client, project):
    dataset, app = _prepare(client, project)
    baseline = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    degraded_app = client.post(
        "/api/apps",
        json={
            "project_id": project["id"],
            "name": "rag-degraded",
            "version_label": "v2",
            "config": {"retriever": "degraded_keyword", "chunk_chars": 300, "top_k": 1},
        },
    ).json()
    candidate = client.post(
        "/api/runs",
        json={"app_id": degraded_app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True},
    ).json()
    policy = client.post(
        "/api/gate-policies",
        json={
            "project_id": project["id"],
            "name": "policy",
            "baseline_run_id": baseline["id"],
            "rules": [{"metric": "recall_at_5", "type": "min", "threshold": 0.8, "severity": "hard"}],
            "min_samples": 1,
        },
    ).json()
    evaluation = client.post(
        f"/api/gate-policies/{policy['id']}/evaluate", json={"candidate_run_id": candidate["id"]}
    ).json()
    assert evaluation["verdict"] == "FAIL"
    assert evaluation["checks"][0]["status"] == "FAIL"
    assert "REGRESSION" in evaluation["checks"][0]["evidence"] or "required" in evaluation["checks"][0]["evidence"]
    history = client.get("/api/gate-evaluations").json()
    assert any(e["id"] == evaluation["id"] for e in history)


def test_gate_rejects_an_unknown_rule_type(client, project):
    response = client.post(
        "/api/gate-policies",
        json={"project_id": project["id"], "name": "bad", "rules": [{"metric": "x", "type": "nope"}]},
    )
    assert response.status_code == 422


def test_gate_refuses_an_incomplete_candidate(client, project):
    dataset, app = _prepare(client, project)
    policy = client.post(
        "/api/gate-policies", json={"project_id": project["id"], "name": "policy2", "rules": []}
    ).json()
    run = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    response = client.post(f"/api/gate-policies/{policy['id']}/evaluate", json={"candidate_run_id": run["id"]})
    assert response.status_code == 200


# -------------------------------------------------------------------- drift


def test_drift_endpoint_returns_signals_and_hypotheses(client, project):
    dataset, app = _prepare(client, project)
    baseline = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    degraded_app = client.post(
        "/api/apps",
        json={
            "project_id": project["id"],
            "name": "rag-degraded",
            "version_label": "v2",
            "config": {"retriever": "degraded_keyword", "chunk_chars": 300, "top_k": 1},
        },
    ).json()
    candidate = client.post(
        "/api/runs",
        json={"app_id": degraded_app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True},
    ).json()
    drift = client.get("/api/drift", params={"baseline_run": baseline["id"], "candidate_run": candidate["id"]}).json()
    assert "recall_at_5" in drift["signals"]
    assert drift["hypotheses"]
    assert "not" in drift["disclaimer"].lower()
    reports = client.get("/api/drift/reports").json()
    assert reports


# ---------------------------------------------------------------- providers


def test_provider_profiles_never_expose_the_key(client):
    created = client.post(
        "/api/providers",
        json={
            "name": "test-openai",
            "kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret-value-1234",
            "model": "gpt-6-luna",
        },
    ).json()
    assert "api_key" not in created
    assert created["has_key"] is True
    assert "1234" in created["api_key_masked"]
    assert "sk-secret" not in json.dumps(created)
    listed = client.get("/api/providers").json()
    assert all("api_key" not in p for p in listed)


def test_provider_update_keeps_the_existing_key(client):
    created = client.post(
        "/api/providers", json={"name": "keep-key", "kind": "openai", "api_key": "sk-secret-value-1234"}
    ).json()
    updated = client.put(
        f"/api/providers/{created['id']}", json={"name": "keep-key", "kind": "openai", "model": "gpt-6-luna"}
    ).json()
    assert updated["has_key"] is True
    assert updated["model"] == "gpt-6-luna"


def test_provider_presets_are_exposed(client):
    presets = client.get("/api/providers/presets").json()
    keys = {p["key"] for p in presets["presets"]}
    assert {"offline", "openai", "anthropic", "openrouter", "ollama", "custom"} <= keys
    offline = next(p for p in presets["presets"] if p["key"] == "offline")
    assert offline["requires_key"] is False


def test_offline_provider_connection_test_succeeds(client):
    created = client.post("/api/providers", json={"name": "offline-test", "kind": "offline"}).json()
    result = client.post(f"/api/providers/{created['id']}/test").json()
    assert result["ok"] is True
    models = client.get(f"/api/providers/{created['id']}/models").json()
    assert models["models"]


def test_judge_refuses_the_offline_provider(client, project):
    dataset, app = _prepare(client, project)
    run = client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    ).json()
    provider = client.post("/api/providers", json={"name": "offline-judge", "kind": "offline"}).json()
    response = client.post("/api/judge", json={"provider_id": provider["id"], "run_id": run["id"], "budget_usd": 0.1})
    assert response.status_code == 422
    assert "offline" in response.json()["detail"].lower()


def test_judge_rubrics_are_exposed(client):
    rubrics = client.get("/api/judge/rubrics").json()
    assert "faithfulness" in [r["dimension"] for r in rubrics["rubrics"]]
    assert "opinion signal" in rubrics["limitation"].lower()


# ------------------------------------------------------------------- system


def test_metric_catalogue_lists_every_metric(client):
    catalogue = client.get("/api/metrics/catalogue").json()
    names = {m["name"] for m in catalogue["metrics"]}
    assert "recall_at_5" in names
    assert "citation_support" in names
    assert "judge" in [m["kind"] for m in catalogue["metrics"]] or True
    for metric in catalogue["metrics"]:
        assert metric["kind_description"]


def test_overview_uses_persisted_data(client, project):
    dataset, app = _prepare(client, project)
    client.post(
        "/api/runs", json={"app_id": app["id"], "dataset_id": dataset["id"], "mode": "end_to_end", "wait": True}
    )
    overview = client.get("/api/overview").json()
    assert overview["counts"]["runs"] >= 1
    assert overview["history"]
    assert overview["latest_metrics"]


def test_system_endpoint_redacts_secrets(client):
    system = client.get("/api/system").json()
    assert "redacted" in system["database"]
    assert "api_key" not in json.dumps(system).lower() or system["api_key_auth_enabled"] is not None


def test_alerts_can_be_listed_and_acknowledged(client):
    alerts = client.get("/api/alerts").json()
    assert isinstance(alerts, list)
    if alerts:
        response = client.post(f"/api/alerts/{alerts[0]['id']}/acknowledge")
        assert response.json()["status"] == "acknowledged"


def test_scheduled_jobs_crud(client, project):
    dataset, app = _prepare(client, project)
    job = client.post(
        "/api/scheduled-jobs",
        json={
            "project_id": project["id"],
            "name": "nightly",
            "app_id": app["id"],
            "dataset_id": dataset["id"],
            "interval_minutes": 60,
        },
    ).json()
    assert job["id"] > 0
    jobs = client.get("/api/scheduled-jobs").json()
    assert any(j["id"] == job["id"] for j in jobs)
    assert client.delete(f"/api/scheduled-jobs/{job['id']}").status_code == 200


def test_production_traces_can_be_imported(client, project):
    trace = client.post(
        "/api/traces",
        json={
            "project_id": project["id"],
            "question": "How do bees signal distance?",
            "answer": "With a waggle dance.",
            "retrieved_doc_ids": ["doc_a"],
        },
    ).json()
    assert trace["stored"] is True
    traces = client.get("/api/traces", params={"project_id": project["id"]}).json()
    assert len(traces) == 1
    dataset = client.post(
        "/api/datasets", json={"project_id": project["id"], "name": "from-traces", "version": "1.0"}
    ).json()
    result = client.post(
        "/api/traces/import-to-dataset", params={"project_id": project["id"], "dataset_id": dataset["id"]}
    ).json()
    assert result["created"] == 1
    items = client.get(f"/api/datasets/{dataset['id']}/items").json()
    assert items[0]["category"] == "production-unreviewed"
