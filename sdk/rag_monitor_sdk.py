"""RAG Quality Monitor — Python SDK.

A thin, dependency-light client for the monitoring API. Use it from CI, from a
release script or from a notebook::

    from rag_monitor_sdk import RAGMonitorClient

    client = RAGMonitorClient("http://127.0.0.1:8000", api_key="…")
    project = client.create_project("My RAG app")
    app = client.create_app(project["id"], "support-bot", "v1.0",
                            {"retriever": "bm25", "top_k": 5})
    dataset = client.create_dataset(project["id"], "golden-set", "1.0")
    client.add_item(dataset["id"], "How do I reset my password?",
                    "Open Settings and choose Reset password.",
                    relevant_doc_ids=["doc_password"], category="factual")
    run = client.start_run(app["id"], dataset["id"], wait=True)
    print(client.metrics(run["id"]))
    verdict = client.evaluate_gate(policy_id, run["id"])
    if verdict["verdict"] != "PASS":
        raise SystemExit(1)
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx

__all__ = ["RAGMonitorClient", "RAGMonitorError", "main"]


class RAGMonitorError(RuntimeError):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class RAGMonitorClient:
    """Client for the RAG Quality Monitor REST API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: str | None = None,
                 timeout: float = 60.0, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("RQM_API_KEY", "")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout,
                                    transport=transport)

    # -- plumbing -------------------------------------------------------
    def _request(self, method: str, path: str, *, params: dict | None = None,
                 json_body: Any = None) -> Any:
        response = self._client.request(method, path, params=params, json=json_body)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise RAGMonitorError(response.status_code, str(detail))
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RAGMonitorClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- health ---------------------------------------------------------
    def health(self) -> dict:
        return self._request("GET", "/health")

    def overview(self) -> dict:
        return self._request("GET", "/api/overview")

    # -- projects / apps ------------------------------------------------
    def create_project(self, name: str, description: str = "") -> dict:
        return self._request("POST", "/api/projects",
                             json_body={"name": name, "description": description})

    def list_projects(self) -> list[dict]:
        return self._request("GET", "/api/projects")

    def create_app(self, project_id: int, name: str, version_label: str = "v1",
                   config: dict | None = None, environment: str = "dev",
                   description: str = "") -> dict:
        return self._request("POST", "/api/apps", json_body={
            "project_id": project_id, "name": name, "version_label": version_label,
            "config": config or {}, "environment": environment, "description": description})

    def list_apps(self, project_id: int | None = None) -> list[dict]:
        return self._request("GET", "/api/apps", params={"project_id": project_id} if project_id else None)

    # -- documents / datasets -------------------------------------------
    def add_document(self, project_id: int, doc_id: str, text: str, title: str = "",
                     source: str = "sdk") -> dict:
        return self._request("POST", "/api/documents", json_body={
            "project_id": project_id, "doc_id": doc_id, "text": text,
            "title": title, "source": source})

    def create_dataset(self, project_id: int, name: str, version: str = "1.0",
                       description: str = "") -> dict:
        return self._request("POST", "/api/datasets", json_body={
            "project_id": project_id, "name": name, "version": version,
            "description": description})

    def add_item(self, dataset_id: int, question: str, reference_answer: str = "",
                 relevant_doc_ids: list[str] | None = None, expected_citations: list[dict] | None = None,
                 category: str = "factual", answerable: bool = True,
                 aliases: list[str] | None = None, cohorts: list[str] | None = None) -> dict:
        return self._request("POST", f"/api/datasets/{dataset_id}/items", json_body={
            "question": question, "reference_answer": reference_answer,
            "relevant_doc_ids": relevant_doc_ids or [],
            "expected_citations": expected_citations or [],
            "category": category, "answerable": answerable,
            "aliases": aliases or [], "cohorts": cohorts or []})

    def validate_dataset(self, dataset_id: int) -> dict:
        return self._request("GET", f"/api/datasets/{dataset_id}/validate")

    # -- runs ------------------------------------------------------------
    def start_run(self, app_id: int, dataset_id: int, mode: str = "end_to_end",
                  wait: bool = False, idempotency_key: str | None = None) -> dict:
        return self._request("POST", "/api/runs", json_body={
            "app_id": app_id, "dataset_id": dataset_id, "mode": mode, "wait": wait,
            "idempotency_key": idempotency_key})

    def wait_for_run(self, run_id: int, timeout_s: float = 900.0, poll_s: float = 2.0) -> dict:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            run = self.get_run(run_id)
            if run["status"] in ("completed", "failed", "cancelled"):
                return run
            time.sleep(poll_s)
        raise TimeoutError(f"run {run_id} did not finish within {timeout_s}s")

    def get_run(self, run_id: int) -> dict:
        return self._request("GET", f"/api/runs/{run_id}")

    def list_runs(self, app_id: int | None = None, dataset_id: int | None = None) -> list[dict]:
        params = {k: v for k, v in (("app_id", app_id), ("dataset_id", dataset_id)) if v}
        return self._request("GET", "/api/runs", params=params or None)

    def results(self, run_id: int, failures_only: bool = False) -> list[dict]:
        return self._request("GET", f"/api/runs/{run_id}/results",
                             params={"failures_only": "true"} if failures_only else None)

    def metrics(self, run_id: int) -> dict:
        return self.get_run(run_id).get("metrics", {}).get("metrics", {})

    def cancel_run(self, run_id: int) -> dict:
        return self._request("POST", f"/api/runs/{run_id}/cancel")

    # -- comparison / drift ---------------------------------------------
    def compare(self, run_a: int, run_b: int) -> dict:
        return self._request("GET", "/api/compare", params={"a": run_a, "b": run_b})

    def drift(self, baseline_run: int, candidate_run: int) -> dict:
        return self._request("GET", "/api/drift",
                             params={"baseline_run": baseline_run, "candidate_run": candidate_run})

    # -- gates -----------------------------------------------------------
    def create_policy(self, project_id: int, name: str, rules: list[dict] | None = None,
                      baseline_run_id: int | None = None, min_samples: int = 5) -> dict:
        body: dict = {"project_id": project_id, "name": name, "min_samples": min_samples}
        if rules:
            body["rules"] = rules
        if baseline_run_id is not None:
            body["baseline_run_id"] = baseline_run_id
        return self._request("POST", "/api/gate-policies", json_body=body)

    def evaluate_gate(self, policy_id: int, candidate_run_id: int,
                      baseline_run_id: int | None = None) -> dict:
        body: dict = {"candidate_run_id": candidate_run_id}
        if baseline_run_id is not None:
            body["baseline_run_id"] = baseline_run_id
        return self._request("POST", f"/api/gate-policies/{policy_id}/evaluate", json_body=body)

    def gate_history(self, policy_id: int | None = None) -> list[dict]:
        return self._request("GET", "/api/gate-evaluations",
                             params={"policy_id": policy_id} if policy_id else None)

    # -- providers -------------------------------------------------------
    def list_providers(self) -> list[dict]:
        return self._request("GET", "/api/providers")

    def create_provider(self, name: str, kind: str, role: str = "judge", base_url: str = "",
                        api_key: str = "", model: str = "", **extra) -> dict:
        body = {"name": name, "kind": kind, "role": role, "base_url": base_url,
                "api_key": api_key, "model": model}
        body.update(extra)
        return self._request("POST", "/api/providers", json_body=body)

    def test_provider(self, provider_id: int) -> dict:
        return self._request("POST", f"/api/providers/{provider_id}/test")

    def discover_models(self, provider_id: int) -> list[dict]:
        return self._request("GET", f"/api/providers/{provider_id}/models").get("models", [])

    def judge(self, provider_id: int, run_id: int, budget_usd: float = 1.0,
              dimensions: list[str] | None = None) -> dict:
        return self._request("POST", "/api/judge", json_body={
            "provider_id": provider_id, "run_id": run_id, "budget_usd": budget_usd,
            "dimensions": dimensions or []})

    # -- reports ---------------------------------------------------------
    def export_report(self, run_id: int, format: str = "json") -> Any:
        return self._request("GET", f"/api/runs/{run_id}/export", params={"format": format})

    def ci_summary(self, run_id: int, policy_id: int | None = None) -> dict:
        return self._request("GET", f"/api/runs/{run_id}/export",
                             params={"format": "ci", "gate_policy": policy_id})


def main(argv: list[str] | None = None) -> int:
    """Small CLI wrapper: ``python sdk/rag_monitor_sdk.py health``."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="RAG Quality Monitor SDK")
    parser.add_argument("command", choices=["health", "overview", "runs", "providers"])
    parser.add_argument("--url", default=os.environ.get("RQM_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.environ.get("RQM_API_KEY", ""))
    args = parser.parse_args(argv)
    with RAGMonitorClient(args.url, args.api_key) as client:
        if args.command == "health":
            payload = client.health()
        elif args.command == "overview":
            payload = client.overview()
        elif args.command == "runs":
            payload = client.list_runs()
        else:
            payload = client.list_providers()
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
