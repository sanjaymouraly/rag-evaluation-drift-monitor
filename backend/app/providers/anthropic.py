"""Anthropic Claude provider (Messages API)."""

from __future__ import annotations

import time

import httpx

from .base import BaseProvider, ProviderError, ProviderResponse
from .pricing import estimate_cost


class AnthropicProvider(BaseProvider):
    kind = "anthropic"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_s, transport=self.transport)

    def _headers(self) -> dict:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.options.get("api_version", "2023-06-01"),
            "content-type": "application/json",
        }
        for key, value in (self.options.get("extra_headers") or {}).items():
            headers[key] = value
        return headers

    def list_models(self) -> list[str]:
        with self._client() as client:
            try:
                r = client.get(f"{self.base_url}/v1/models", headers=self._headers())
            except httpx.HTTPError as exc:
                raise ProviderError(self._redact(f"model discovery failed: {exc}"), retryable=True) from exc
        if r.status_code >= 400:
            raise ProviderError(f"model discovery failed: HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        return sorted(str(m["id"]) for m in data.get("data", []) if isinstance(m, dict) and m.get("id"))

    def _call_once(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
        msgs = [m for m in messages if m.get("role") != "system"]
        payload: dict = {"model": self.model, "max_tokens": max_tokens, "messages": msgs}
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        t0 = time.perf_counter()
        with self._client() as client:
            try:
                r = client.post(f"{self.base_url}/v1/messages", headers=self._headers(), json=payload)
            except httpx.HTTPError as exc:
                raise ProviderError(self._redact(f"request failed: {exc}"), retryable=True) from exc
        latency = (time.perf_counter() - t0) * 1000
        if r.status_code >= 400:
            raise ProviderError(
                f"HTTP {r.status_code}: {r.text[:300]}",
                status_code=r.status_code,
                retryable=r.status_code in (408, 409, 429, 500, 502, 503, 504),
            )
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage") or {}
        in_tok = int(usage.get("input_tokens", 0) or 0)
        out_tok = int(usage.get("output_tokens", 0) or 0)
        cost, is_est = estimate_cost(self.model, in_tok, out_tok, self._price_in(), self._price_out())
        return ProviderResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            usage_exact=bool(usage),
            model=data.get("model", self.model),
            provider=self.kind,
            latency_ms=round(latency, 3),
            cost_usd=cost,
            cost_is_estimate=is_est,
            raw={"usage": usage, "stop_reason": data.get("stop_reason")},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderError(
            "Anthropic does not provide an embeddings endpoint; configure a separate embedding provider"
        )

    def _price_in(self) -> float | None:
        value = self.options.get("price_per_1k_input")
        return float(value) if value not in (None, "") else None

    def _price_out(self) -> float | None:
        value = self.options.get("price_per_1k_output")
        return float(value) if value not in (None, "") else None
