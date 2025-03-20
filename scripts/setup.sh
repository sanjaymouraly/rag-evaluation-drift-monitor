#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# RAG Quality Monitor — Linux / macOS setup.
# Creates a virtual environment, installs the backend and frontend
# dependencies and (optionally) seeds the demo data.
#
#   ./scripts/setup.sh              full setup
#   ./scripts/setup.sh --no-seed    skip the demo seed
#   ./scripts/setup.sh --no-frontend skip the frontend install
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
SEED=1
FRONTEND=1

for arg in "$@"; do
  case "$arg" in
    --no-seed) SEED=0 ;;
    --no-frontend) FRONTEND=0 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: $PYTHON_BIN not found. Install Python 3.11 or newer." >&2
  exit 1
fi

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "==> Using Python $PY_VERSION ($PYTHON_BIN)"

if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "error: Python 3.11 or newer is required (found $PY_VERSION)." >&2
  exit 1
fi

echo "==> Creating the virtual environment (.venv)"
[ -d .venv ] || "$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing the backend dependencies"
python -m pip install --upgrade pip
pip install -r backend/requirements-dev.txt

if [ "$FRONTEND" -eq 1 ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "==> Installing the frontend dependencies"
    (cd frontend && npm install)
  else
    echo "warning: npm not found — skipping the frontend install." >&2
  fi
fi

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
  echo "    (edit .env to set RQM_API_KEY before exposing the server)"
fi

if [ "$SEED" -eq 1 ]; then
  echo "==> Seeding the demo project (documents, benchmark, runs, gate verdicts)"
  (cd backend && python -m app.seed --reset)
fi

echo
echo "Setup complete."
echo "  Start the backend : ./scripts/start.sh"
echo "  Start the frontend: ./scripts/start.sh --frontend-only"
echo "  API documentation  : http://127.0.0.1:8000/docs"
