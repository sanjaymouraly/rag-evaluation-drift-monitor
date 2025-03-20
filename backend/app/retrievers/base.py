"""Retriever interface and the offline implementations.

Every retriever exposes the same tiny interface::

    index.search(query, top_k) -> list[{chunk_id, doc_id, text, score}]

so a new retriever (a vector database, a hosted search service, an external
RAG system) only has to implement ``search``.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Protocol, runtime_checkable

from ..metrics.text import tokenize
from .hashing import HASH_EMBEDDING_DIM, hash_embedding


@runtime_checkable
class Retriever(Protocol):
    name: str

    def search(self, query: str, top_k: int = 5) -> list[dict]: ...


class BM25Retriever:
    """Okapi BM25 over chunks — deterministic, dependency-free, explainable."""

    name = "bm25"

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.doc_tokens = [tokenize(c["text"]) for c in chunks]
        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        self.tfs = [Counter(t) for t in self.doc_tokens]
        df: Counter = Counter()
        for toks in self.doc_tokens:
            for term in set(toks):
                df[term] += 1
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        q = tokenize(query)
        if not q or not self.chunks:
            return []
        scores = []
        for i, tf in enumerate(self.tfs):
            dl = self.doc_len[i] or 1
            s = 0.0
            for term in q:
                f = tf.get(term, 0)
                if f:
                    s += (
                        self.idf.get(term, 0.0)
                        * (f * (self.k1 + 1))
                        / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
                    )
            scores.append(s)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.chunks[i]["chunk_id"]))
        return [{**self.chunks[i], "score": round(scores[i], 6)} for i in order[:top_k]]


class TfidfRetriever:
    """TF-IDF cosine similarity."""

    name = "tfidf"

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        df: Counter = Counter()
        docs = [Counter(tokenize(c["text"])) for c in chunks]
        for d in docs:
            for t in d:
                df[t] += 1
        n = len(chunks) or 1
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self.vecs = []
        for d in docs:
            total = sum(d.values()) or 1
            self.vecs.append({t: (c / total) * self.idf[t] for t, c in d.items()})

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        qc = Counter(tokenize(query))
        if not qc:
            return []
        total = sum(qc.values())
        qv = {t: (c / total) * self.idf.get(t, 1.0) for t, c in qc.items()}
        qn = math.sqrt(sum(v * v for v in qv.values())) or 1.0
        scored = []
        for dv in self.vecs:
            dot = sum(qv.get(t, 0.0) * v for t, v in dv.items())
            dn = math.sqrt(sum(v * v for v in dv.values())) or 1.0
            scored.append(dot / (qn * dn))
        order = sorted(range(len(scored)), key=lambda i: (-scored[i], self.chunks[i]["chunk_id"]))
        return [{**self.chunks[i], "score": round(scored[i], 6)} for i in order[:top_k]]


class HashEmbeddingRetriever:
    """Cosine retrieval over deterministic feature-hash vectors (offline, not semantic)."""

    name = "embedding_hash"

    def __init__(self, chunks: list[dict], dim: int = HASH_EMBEDDING_DIM):
        self.chunks = chunks
        self.dim = dim
        self.vecs = [hash_embedding(c["text"], dim) for c in chunks]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not tokenize(query) or not self.chunks:
            return []
        qv = hash_embedding(query, self.dim)
        scored = [float(sum(a * b for a, b in zip(qv, v, strict=True))) for v in self.vecs]
        order = sorted(range(len(scored)), key=lambda i: (-scored[i], self.chunks[i]["chunk_id"]))
        return [{**self.chunks[i], "score": round(scored[i], 6)} for i in order[:top_k]]


class DegradedRetriever:
    """Deliberately broken retriever used to demonstrate regression detection.

    It only matches the *first* token of the query, so most multi-term questions
    retrieve the wrong document. It is a first-class, documented feature of the
    demo — not a bug.
    """

    name = "degraded_keyword"

    def __init__(self, inner: BM25Retriever):
        self.inner = inner

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        toks = tokenize(query)
        q = toks[0] if toks else query
        return self.inner.search(q, top_k=top_k)
