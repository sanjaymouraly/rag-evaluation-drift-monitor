#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# RAG Quality Monitor — start the API and the dashboard.
#
#   ./scripts/start.sh                 backend + frontend
#   ./scripts/start.sh --backend-only  only the API
#   ./scripts/start.sh --frontend-only only the dashboard
#   PORT=9000 ./scripts/start.sh        use a different API port
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND=1
FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --backend-only) FRONTEND=0 ;;
    --frontend-only) BACKEND=0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ ! -d .venv ]; then
  echo "error: .venv not found. Run ./scripts/setup.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if [ "$BACKEND" -eq 1 ]; then
  echo "==> API      : http://127.0.0.1:${PORT}  (docs at /docs)"
  (cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT") &
  PIDS+=("$!")
fi

if [ "$FRONTEND" -eq 1 ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "==> Dashboard: http://127.0.0.1:${FRONTEND_PORT}"
    (cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
    PIDS+=("$!")
  else
    echo "warning: npm not found — the dashboard cannot be started." >&2
  fi
fi

wait -n
