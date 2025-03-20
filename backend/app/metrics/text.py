"""Text normalisation helpers shared by every metric.

These are intentionally boring, deterministic and well tested: every metric in
the platform is built on top of them, so their behaviour defines the meaning of
"token F1" and "normalised match" across the whole product.
"""

from __future__ import annotations

import re
import unicodedata

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WS_RE = re.compile(r"\s+")
_ARTICLES_RE = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]")

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "and",
        "or",
        "as",
        "at",
        "by",
        "from",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "do",
        "does",
        "did",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "can",
        "could",
        "should",
        "would",
        "there",
        "their",
        "they",
    }
)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """Lower-case alphanumeric tokenisation (deterministic, language-agnostic)."""
    return _TOKEN_RE.findall(strip_accents(text or "").lower())


def content_tokens(text: str) -> list[str]:
    """Tokens with stopwords removed — used by support/overlap heuristics."""
    return [t for t in tokenize(text) if t not in STOPWORDS]


def normalize_answer(text: str) -> str:
    """SQuAD-style normalisation: lower-case, strip punctuation/articles/spaces."""
    text = strip_accents(text or "").lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _ARTICLES_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def normalize_soft(text: str) -> str:
    """Normalisation that keeps articles (used for a second 'soft' match)."""
    text = strip_accents(text or "").lower()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def sentences(text: str) -> list[str]:
    """Split text into sentences (deterministic, abbreviation-agnostic)."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p and p.strip()]


def numbers_in(text: str) -> list[str]:
    """All numeric literals in a text, normalised (e.g. '1,000' -> '1000')."""
    out = []
    for raw in re.findall(r"[-+]?\d[\d,]*\.?\d*", text or ""):
        cleaned = raw.replace(",", "").rstrip(".")
        if cleaned in ("", "-", "."):
            continue
        try:
            out.append(f"{float(cleaned):g}")
        except ValueError:  # pragma: no cover - defensive
            out.append(cleaned)
    return out
