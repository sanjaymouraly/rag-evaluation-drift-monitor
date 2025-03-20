"""Release gate script for CI.

Evaluates a candidate evaluation run against a release gate policy and exits
with a meaningful status code:

* ``0`` — PASS
* ``1`` — FAIL (a hard quality check failed; the release is blocked)
* ``2`` — INCONCLUSIVE (missing or insufficient evidence; the release is blocked)
* ``3`` — usage / connection error

Usage::

    python examples/release_gate.py --url http://127.0.0.1:8000 \\
        --policy 1 --candidate 4 --output gate-result.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))

from rag_monitor_sdk import RAGMonitorClient, RAGMonitorError  # noqa: E402

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INCONCLUSIVE = 2
EXIT_ERROR = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a release gate in CI")
    parser.add_argument("--url", default=os.environ.get("RQM_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.environ.get("RQM_API_KEY", ""))
    parser.add_argument("--policy", type=int, required=True)
    parser.add_argument("--candidate", type=int, required=True)
    parser.add_argument("--baseline", type=int, default=None)
    parser.add_argument("--output", default=None, help="write the JSON result to this file")
    args = parser.parse_args(argv)

    try:
        with RAGMonitorClient(args.url, args.api_key) as client:
            result = client.evaluate_gate(args.policy, args.candidate, args.baseline)
    except RAGMonitorError as exc:
        print(f"gate evaluation failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"gate evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, default=str)

    verdict = result.get("verdict", "INCONCLUSIVE")
    print(f"{verdict}: {result.get('summary', '')}")
    for check in result.get("checks", []):
        print(f"  [{check['status']:<12}] {check['metric']} ({check['type']}) — {check['evidence']}")
    if verdict == "PASS":
        return EXIT_PASS
    if verdict == "FAIL":
        return EXIT_FAIL
    return EXIT_INCONCLUSIVE


if __name__ == "__main__":
    raise SystemExit(main())
