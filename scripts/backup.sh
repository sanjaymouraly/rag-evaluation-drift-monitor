#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Back up the RAG Quality Monitor database.
#
#   ./scripts/backup.sh                    -> ./backups/rag_monitor-<timestamp>.db
#   RQM_DATABASE_URL=postgresql+psycopg://... ./scripts/backup.sh
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
URL="${RQM_DATABASE_URL:-sqlite:///./backend/rag_monitor.db}"

if [[ "$URL" == postgresql* ]]; then
  TARGET="$BACKUP_DIR/rag_monitor-$STAMP.sql"
  echo "==> Dumping PostgreSQL to $TARGET"
  pg_dump --dbname="$URL" --format=plain > "$TARGET"
else
  DB_PATH="${URL#sqlite:///}"
  DB_PATH="${DB_PATH#./}"
  if [ ! -f "$DB_PATH" ]; then
    echo "error: database not found at $DB_PATH" >&2
    exit 1
  fi
  TARGET="$BACKUP_DIR/rag_monitor-$STAMP.db"
  echo "==> Copying $DB_PATH to $TARGET"
  cp "$DB_PATH" "$TARGET"
fi

echo "==> Backup complete: $TARGET"
