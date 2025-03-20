"""Reference model pricing.

Prices are **per 1M tokens** as published by the providers and are stored
internally as *per 1k tokens*. They are a convenience for estimating spend; the
platform always labels monetary values as estimates, and a user can override the
price on every provider profile.

Sources (as of the versions listed in ``CHANGELOG.md``):
* OpenAI — platform.openai.com/docs/models
* Anthropic — platform.claude.com/docs/en/models/overview
"""

from __future__ import annotations

# model-id prefix -> (input USD / 1M tokens, output USD / 1M tokens)
REFERENCE_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-6-astra": (10.0, 50.0),
    "gpt-6.1-sol": (2.0, 10.0),
    "gpt-6-luna": (0.1, 0.5),
    "gpt-6": (2.0, 10.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "o3": (2.0, 8.0),
    "o4-mini": (1.1, 4.4),
    # Anthropic
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.1, 0.5),
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-3-5-haiku": (0.8, 4.0),
    # Embeddings
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def price_per_1k(model: str) -> tuple[float, float, str]:
    """Return ``(input_per_1k, output_per_1k, source)`` for a model id.

    ``source`` is ``"reference"`` when a published list price was found and
    ``"unknown"`` otherwise — the caller must not present unknown prices as
    facts.
    """
    name = (model or "").strip()
    if not name:
        return 0.0, 0.0, "unknown"
    if name in REFERENCE_PRICES_PER_MTOK:
        i, o = REFERENCE_PRICES_PER_MTOK[name]
        return i / 1000.0, o / 1000.0, "reference"
    # Longest-prefix match so dated snapshots (claude-haiku-5-5-20260101) work.
    best: tuple[str, tuple[float, float]] | None = None
    for key, prices in REFERENCE_PRICES_PER_MTOK.items():
        if name.startswith(key) and (best is None or len(key) > len(best[0])):
            best = (key, prices)
    if best:
        i, o = best[1]
        return i / 1000.0, o / 1000.0, "reference"
    return 0.0, 0.0, "unknown"


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int, price_in: float | None = None, price_out: float | None = None
) -> tuple[float, bool]:
    """Estimate the USD cost of a call.

    Returns ``(cost_usd, is_estimate)``. When no price is configured the cost
    is ``0.0`` and the caller must present it as *unknown*, not as *free*.
    """
    if price_in is None or price_out is None:
        ref_in, ref_out, _ = price_per_1k(model)
        price_in = ref_in if price_in is None else price_in
        price_out = ref_out if price_out is None else price_out
    if not price_in and not price_out:
        return 0.0, True
    return (input_tokens / 1000.0 * price_in) + (output_tokens / 1000.0 * price_out), True
