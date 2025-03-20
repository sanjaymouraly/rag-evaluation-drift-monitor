"""Chunking.

The chunker is deterministic and its parameters (``chunk_chars``,
``overlap_chars``) are part of the frozen run configuration, so a chunking
change is visible in the run snapshot and is a first-class drift signal.
"""

from __future__ import annotations

import re

_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def chunk_document(doc_id: str, text: str, chunk_chars: int = 600, overlap_chars: int = 80) -> list[dict]:
    """Split a document into overlapping chunks, preferring sentence boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    chunk_chars = max(100, int(chunk_chars))
    overlap_chars = max(0, min(int(overlap_chars), chunk_chars - 1))
    chunks: list[dict] = []
    start, idx = 0, 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind("\n"), window.rfind("? "), window.rfind("! "))
            if cut > chunk_chars // 2:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                {
                    "chunk_id": f"{doc_id}::c{idx}",
                    "doc_id": doc_id,
                    "text": piece,
                    "char_start": start,
                    "char_end": end,
                    "n_chars": len(piece),
                }
            )
            idx += 1
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def chunk_statistics(chunks: list[dict]) -> dict:
    """Summary statistics used for chunk-level drift detection."""
    if not chunks:
        return {"n_chunks": 0, "mean_chars": None, "median_chars": None, "min_chars": None, "max_chars": None}
    sizes = sorted(c.get("n_chars", len(c.get("text", ""))) for c in chunks)
    mid = len(sizes) // 2
    median = sizes[mid] if len(sizes) % 2 else (sizes[mid - 1] + sizes[mid]) / 2
    return {
        "n_chunks": len(chunks),
        "mean_chars": round(sum(sizes) / len(sizes), 2),
        "median_chars": median,
        "min_chars": sizes[0],
        "max_chars": sizes[-1],
    }
