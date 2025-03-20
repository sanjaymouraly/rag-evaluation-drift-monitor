"""Example: drive the platform with the Python SDK.

Registers a project, a RAG version, a dataset and runs an evaluation plus a
release gate — the same flow a CI pipeline would use.

    python examples/sdk_usage.py --url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))

from rag_monitor_sdk import RAGMonitorClient  # noqa: E402

CORPUS = {
    "doc_bees": "A returning forager performs a waggle dance. The duration of the waggle phase "
                "encodes the distance to the food, with longer dances signalling farther sources.",
}

BENCHMARK = [
    ("What does the duration of the waggle phase signal?",
     "It encodes the distance to the food, with longer dances signalling farther sources.",
     ["doc_bees"]),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args(argv)

    with RAGMonitorClient(args.url, args.api_key) as client:
        project = client.create_project("SDK example", "Created by examples/sdk_usage.py")
        print("project:", project["id"])

        for doc_id, text in CORPUS.items():
            client.add_document(project["id"], doc_id, text)

        dataset = client.create_dataset(project["id"], "sdk-benchmark", "1.0")
        for question, reference, relevant in BENCHMARK:
            client.add_item(dataset["id"], question, reference, relevant_doc_ids=relevant,
                            expected_citations=[{"doc_id": d} for d in relevant])

        app = client.create_app(project["id"], "sdk-rag", "v1.0",
                                {"retriever": "bm25", "chunk_chars": 400, "top_k": 5})
        run = client.start_run(app["id"], dataset["id"], wait=True)
        print("run:", run["id"], run["status"])
        print(json.dumps(client.metrics(run["id"]), indent=2, default=str))

        policy = client.create_policy(project["id"], "sdk-policy", baseline_run_id=run["id"],
                                      min_samples=1)
        verdict = client.evaluate_gate(policy["id"], run["id"])
        print("gate:", verdict["verdict"], verdict["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
