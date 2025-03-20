"""Offline provider — no network, no key, zero cost.

The offline provider is what makes the "no-API-key demo" real: it produces a
deterministic, extractive answer from the retrieved context instead of calling
a hosted model. It is labelled as such everywhere it is used.
"""

from __future__ import annotations

import time

from .base import BaseProvider, ProviderResponse


class OfflineProvider(BaseProvider):
    kind = "offline"

    def _call_once(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        t0 = time.perf_counter()
        user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        system = " ".join(m.get("content", "") for m in messages if m.get("role") == "system")
        text = (
            f"[offline deterministic mode] No external model was called.\n"
            f"Received {len(user)} characters of instruction.\n"
            f"Context summary: {system[:400]}"
        )
        return ProviderResponse(
            text=text,
            input_tokens=max(1, len(user) // 4),
            output_tokens=max(1, len(text) // 4),
            usage_exact=False,
            model="offline-deterministic",
            provider=self.kind,
            latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            cost_usd=0.0,
            cost_is_estimate=True,
            raw={"offline": True},
        )

    def list_models(self) -> list[str]:
        return ["offline-deterministic"]

    def test_connection(self) -> dict:
        return {
            "ok": True,
            "detail": "Offline deterministic mode — no network call is made.",
            "models": ["offline-deterministic"],
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        from ..retrievers.hashing import hash_embedding

        return [hash_embedding(t) for t in texts]
