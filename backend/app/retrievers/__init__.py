"""Retriever factory.

``build_retriever(kind, chunks, config)`` is the single place that maps a
configuration value to an implementation, so the retriever recorded in the run
snapshot is always the one that actually ran.
"""

from __future__ import annotations

from .base import (
    BM25Retriever,
    DegradedRetriever,
    HashEmbeddingRetriever,
    Retriever,
    TfidfRetriever,
)
from .chunking import chunk_document, chunk_statistics

RETRIEVER_KINDS = {
    "bm25": "Okapi BM25 (offline, deterministic, no dependencies)",
    "tfidf": "TF-IDF cosine similarity (offline, deterministic)",
    "embedding_hash": "Feature-hash vectors + cosine (offline; NOT a semantic model)",
    "degraded_keyword": "Deliberately broken retriever used to demo regression detection",
}


def build_retriever(kind: str, chunks: list[dict], config: dict | None = None) -> Retriever:
    config = config or {}
    kind = (kind or "bm25").lower()
    if kind == "tfidf":
        return TfidfRetriever(chunks)
    if kind in ("embedding_hash", "hashing"):
        return HashEmbeddingRetriever(chunks, int(config.get("embedding_dim", 256)))
    if kind == "degraded_keyword":
        return DegradedRetriever(BM25Retriever(chunks))
    return BM25Retriever(chunks, float(config.get("bm25_k1", 1.5)), float(config.get("bm25_b", 0.75)))


__all__ = [
    "RETRIEVER_KINDS",
    "BM25Retriever",
    "DegradedRetriever",
    "HashEmbeddingRetriever",
    "TfidfRetriever",
    "build_retriever",
    "chunk_document",
    "chunk_statistics",
]
