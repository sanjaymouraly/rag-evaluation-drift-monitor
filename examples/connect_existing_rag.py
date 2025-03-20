"""Example: connect an existing RAG application *without rewriting it*.

The platform can evaluate any RAG system that exposes a small HTTP endpoint.
You describe the request and the response shape once (a "REST adapter"), and
the platform turns it into a full evaluation with retrieval, answer, citation
and latency metrics.

This script:

1. registers a project, the documents and a benchmark dataset;
2. registers a RAG application version whose config points at the adapter;
3. starts an evaluation run and prints the metrics;
4. evaluates a release gate.

Run it against the bundled demo API::

    # terminal 1
    cd backend && python -m uvicorn app.main:app --port 8000
    # terminal 2
    python examples/connect_existing_rag.py --url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))

from rag_monitor_sdk import RAGMonitorClient  # noqa: E402

#: The adapter description. Every field is configurable.
ADAPTER = {
    "type": "rest",
    "url": "http://localhost:9000/ask",
    "method": "POST",
    "question_field": "question",
    "answer_path": "answer",
    "retrieved_path": "sources",
    "citations_path": "citations",
    "headers": {},
    "timeout_s": 30,
}

DOCUMENTS = {
    "doc_password": "Resetting a password: open Settings, choose Security, "
                    "select Reset password and confirm with the code sent to your email.",
    "doc_refund": "Refunds are issued to the original payment method within five business days "
                  "after the return is received.",
}

BENCHMARK = [
    ("How do I reset my password?",
     "Open Settings, choose Security, select Reset password and confirm with the code sent to your email.",
     ["doc_password"]),
    ("How long does a refund take?",
     "Refunds are issued to the original payment method within five business days.",
     ["doc_refund"]),
    ("What is the support phone number?",
     "", []),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--adapter-url", default=ADAPTER["url"],
                        help="the URL of your own RAG service")
    parser.add_argument("--keep", action="store_true", help="keep the demo project if it exists")
    args = parser.parse_args(argv)

    adapter = dict(ADAPTER, url=args.adapter_url)

    with RAGMonitorClient(args.url, args.api_key) as client:
        print("==> health:", client.health())

        project = client.create_project("Example — existing RAG adapter",
                                        "Evaluates an existing RAG service over REST.")
        print(f"==> project #{project['id']}")

        for doc_id, text in DOCUMENTS.items():
            client.add_document(project["id"], doc_id, text, title=doc_id)
        print(f"==> {len(DOCUMENTS)} documents ingested")

        dataset = client.create_dataset(project["id"], "support-benchmark", "1.0")
        for question, reference, relevant in BENCHMARK:
            client.add_item(dataset["id"], question, reference,
                            relevant_doc_ids=relevant,
                            expected_citations=[{"doc_id": d} for d in relevant],
                            category="factual" if reference else "unanswerable",
                            answerable=bool(reference))
        print(f"==> dataset #{dataset['id']} with {len(BENCHMARK)} items")

        report = client.validate_dataset(dataset["id"])
        if not report["ok"]:
            print("warning: dataset issues:", json.dumps(report["issues"], indent=2))

        app = client.create_app(project["id"], "existing-rag", "v1.0",
                                {"adapter": adapter, "top_k": 3, "retriever": "external"})
        print(f"==> RAG application #{app['id']} registered with the REST adapter")

        print("==> starting the evaluation ...")
        run = client.start_run(app["id"], dataset["id"], wait=False)
        run = client.wait_for_run(run["id"])
        print(f"==> run #{run['id']} status={run['status']}")
        if run["status"] != "completed":
            print("error:", run.get("error"))
            return 1

        metrics = client.metrics(run["id"])
        for name, value in sorted(metrics.items()):
            if name in ("recall_at_5", "token_f1", "citation_support", "latency_p95_ms",
                        "estimated_cost_usd"):
                print(f"    {name:<24} {value.get('value')} (n={value.get('n')})")

        policy = client.create_policy(project["id"], "example-policy", baseline_run_id=run["id"],
                                      min_samples=1)
        verdict = client.evaluate_gate(policy["id"], run["id"])
        print("==> gate verdict:", verdict["verdict"], "-", verdict["summary"])

        if not args.keep:
            print("==> (delete the project manually with DELETE /api/projects/{id} "
                  f"-> {args.url}/api/projects/{project['id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
