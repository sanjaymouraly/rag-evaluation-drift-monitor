"""Ingestion of documents and benchmark datasets.

Parsing is deliberately conservative: only plain text and structured text
formats are accepted, everything is size-limited, and the content of a
document is always treated as untrusted data (never as code or instructions).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from ..security import safe_join, sanitize_filename

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".log", ".text"}
DATA_SUFFIXES = {".json", ".jsonl", ".ndjson", ".csv", ".tsv"}


class IngestionError(ValueError):
    """Raised when a document or dataset cannot be parsed safely."""


def parse_document(filename: str, raw: bytes, max_bytes: int = 10 * 1024 * 1024) -> dict:
    """Parse an uploaded document into text.

    Returns ``{doc_id, title, text, source, metadata}``.
    """
    if len(raw) > max_bytes:
        raise IngestionError(f"file exceeds the {max_bytes} byte limit")
    safe_name = sanitize_filename(filename, "document")
    suffix = Path(safe_name).suffix.lower()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise IngestionError("file could not be decoded as text") from exc
    text = text.replace("\x00", "").strip()
    if not text:
        raise IngestionError("file is empty")
    if suffix in DATA_SUFFIXES:
        try:
            parsed = json.loads(text) if suffix == ".json" else None
        except json.JSONDecodeError as exc:
            raise IngestionError(f"invalid JSON: {exc}") from exc
        if isinstance(parsed, dict):
            body = parsed.get("text") or parsed.get("content") or ""
            if not isinstance(body, str):
                body = json.dumps(parsed, ensure_ascii=False, indent=2)
            text = body
        elif isinstance(parsed, list):
            text = "\n\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in parsed)
    return {
        "doc_id": Path(safe_name).stem or "document",
        "title": Path(safe_name).stem.replace("_", " ").replace("-", " ").strip() or safe_name,
        "text": text,
        "source": safe_name,
        "metadata": {"filename": safe_name, "bytes": len(raw)},
    }


def parse_dataset_file(filename: str, raw: bytes, max_bytes: int = 10 * 1024 * 1024) -> list[dict]:
    """Parse a benchmark file (CSV, JSONL or JSON array) into dataset items."""
    if len(raw) > max_bytes:
        raise IngestionError(f"file exceeds the {max_bytes} byte limit")
    safe_name = sanitize_filename(filename, "dataset")
    suffix = Path(safe_name).suffix.lower()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestionError("dataset file must be UTF-8 encoded") from exc
    text = text.strip()
    if not text:
        raise IngestionError("dataset file is empty")

    rows: list[dict] = []
    if suffix == ".csv":
        delimiter = "\t" if suffix == ".tsv" else ","
        for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
            rows.append(dict(row))
    elif suffix == ".json" or text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IngestionError(f"invalid JSON: {exc}") from exc
        if isinstance(data, dict):
            data = data.get("items", [])
        if not isinstance(data, list):
            raise IngestionError("JSON dataset must be an array of items")
        rows = [r for r in data if isinstance(r, dict)]
    else:  # jsonl / ndjson
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IngestionError(f"invalid JSON on line {number}: {exc}") from exc
            if not isinstance(row, dict):
                raise IngestionError(f"line {number} is not a JSON object")
            rows.append(row)

    items: list[dict] = []
    for index, row in enumerate(rows, 1):
        question = str(row.get("question") or row.get("prompt") or "").strip()
        if not question:
            raise IngestionError(f"item {index} has no question")
        items.append(
            {
                "question": question,
                "reference_answer": str(row.get("reference_answer") or row.get("answer") or ""),
                "aliases": _as_list(row.get("aliases")),
                "relevant_doc_ids": _as_list(row.get("relevant_doc_ids") or row.get("relevant_docs")),
                "relevance_grades": _as_grades(row.get("relevance_grades")),
                "expected_citations": _as_citations(row.get("expected_citations")),
                "category": str(row.get("category") or "factual"),
                "difficulty": str(row.get("difficulty") or "medium"),
                "answerable": _as_bool(row.get("answerable", True)),
                "language": str(row.get("language") or "en"),
                "topic": str(row.get("topic") or ""),
                "cohorts": _as_list(row.get("cohorts")),
                "notes": str(row.get("notes") or ""),
            }
        )
    return items


def _as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split("|") if v.strip()]


def _as_grades(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return {str(k): float(v) for k, v in value.items()}
    if isinstance(value, list):
        out = {}
        for entry in value:
            if isinstance(entry, dict):
                doc = entry.get("doc_id") or entry.get("document_id")
                if doc:
                    out[str(doc)] = float(entry.get("grade", entry.get("relevance", 1.0)))
        return out
    return {}


def _as_citations(value) -> list[dict]:
    if not value:
        return []
    if isinstance(value, list):
        out = []
        for entry in value:
            if isinstance(entry, dict):
                out.append(entry)
            elif isinstance(entry, str):
                out.append({"doc_id": entry})
        return out
    if isinstance(value, str):
        return [{"doc_id": v.strip()} for v in value.split("|") if v.strip()]
    return []


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() not in ("false", "0", "no", "n")


def read_upload(root: Path, filename: str) -> bytes:
    """Read an uploaded file from a bounded directory (path traversal safe)."""
    path = safe_join(root, filename)
    return path.read_bytes()
