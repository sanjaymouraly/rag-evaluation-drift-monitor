#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Scheduled benchmark run + release gate (cron friendly).
#
#   ./scripts/scheduled_eval.sh --app 2 --dataset 1 --policy 1
#
# Exit codes: 0 = gate PASS, 1 = gate FAIL, 2 = gate INCONCLUSIVE, 3 = error.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_ID=""
DATASET_ID=""
POLICY_ID=""
BASELINE_ID=""
MODE="end_to_end"

while [ $# -gt 0 ]; do
  case "$1" in
    --app) APP_ID="$2"; shift 2 ;;
    --dataset) DATASET_ID="$2"; shift 2 ;;
    --policy) POLICY_ID="$2"; shift 2 ;;
    --baseline) BASELINE_ID="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 3 ;;
  esac
done

if [ -z "$APP_ID" ] || [ -z "$DATASET_ID" ]; then
  echo "usage: $0 --app <id> --dataset <id> [--policy <id>] [--baseline <id>]" >&2
  exit 3
fi

PYTHON="${PYTHON:-python3}"
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON="python"
fi

cd backend
RUN_JSON="$("$PYTHON" -m app.cli eval --app "$APP_ID" --dataset "$DATASET_ID" --mode "$MODE")"
echo "$RUN_JSON"
RUN_ID="$(printf '%s' "$RUN_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
echo "==> Evaluation run #$RUN_ID finished"

if [ -z "$POLICY_ID" ]; then
  exit 0
fi

if [ -n "$BASELINE_ID" ]; then
  "$PYTHON" -m app.cli gate --policy "$POLICY_ID" --candidate "$RUN_ID" --baseline "$BASELINE_ID"
else
  "$PYTHON" -m app.cli gate --policy "$POLICY_ID" --candidate "$RUN_ID"
fi
