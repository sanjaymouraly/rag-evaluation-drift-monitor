"""Ollama provider — fully local, free, no API key."""

from __future__ import annotations

import time

import httpx

from .base import BaseProvider, ProviderError, ProviderResponse
from .pricing import estimate_cost


class OllamaProvider(BaseProvider):
    kind = "ollama"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_s, transport=self.transport)

    def list_models(self) -> list[str]:
        with self._client() as client:
            try:
                r = client.get(f"{self.base_url}/api/tags")
            except httpx.HTTPError as exc:
                raise ProviderError(
                    self._redact(f"cannot reach Ollama at {self.base_url}: {exc}"), retryable=True
                ) from exc
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        return sorted(str(m.get("name")) for m in data.get("models", []) if m.get("name"))

    def _call_once(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        t0 = time.perf_counter()
        with self._client() as client:
            try:
                r = client.post(f"{self.base_url}/api/chat", json=payload)
            except httpx.HTTPError as exc:
                raise ProviderError(self._redact(f"request failed: {exc}"), retryable=True) from exc
        latency = (time.perf_counter() - t0) * 1000
        if r.status_code >= 400:
            raise ProviderError(
                f"HTTP {r.status_code}: {r.text[:300]}",
                status_code=r.status_code,
                retryable=r.status_code in (408, 429, 500, 502, 503, 504),
            )
        data = r.json()
        text = (data.get("message") or {}).get("content", "") or ""
        in_tok = int(data.get("prompt_eval_count", 0) or 0)
        out_tok = int(data.get("eval_count", 0) or 0)
        _cost, is_est = estimate_cost(self.model, in_tok, out_tok, 0.0, 0.0)
        return ProviderResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            usage_exact=bool(out_tok),
            model=data.get("model", self.model),
            provider=self.kind,
            latency_ms=round(latency, 3),
            cost_usd=0.0,
            cost_is_estimate=is_est,
            raw={"total_duration": data.get("total_duration")},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._client() as client:
            r = client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts})
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:200]}")
        return list(r.json().get("embeddings", []))
