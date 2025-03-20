"""Deterministic offline embedding baseline (feature hashing).

This is **not** a semantic model: it hashes tokens into a fixed vector, so two
sentences only match when they share surface tokens. It exists so that the
platform can demonstrate the embedding-based code path with zero cost and zero
dependencies. Any metric computed with it is labelled ``embedding_based`` and
the report states that the vectors are hashed, not semantic.
"""

from __future__ import annotations

import hashlib
import math

from ..metrics.text import tokenize

HASH_EMBEDDING_DIM = 256


def hash_embedding(text: str, dim: int = HASH_EMBEDDING_DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
