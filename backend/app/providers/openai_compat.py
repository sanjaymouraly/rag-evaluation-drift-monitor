"""OpenAI-compatible provider.

Covers the OpenAI API itself, OpenRouter, Azure OpenAI, and any custom service
that exposes ``/chat/completions`` (vLLM, LM Studio, llama.cpp server, Groq,
Mistral, DeepSeek, Together...).

The OpenAI API is called through the Responses API when available and falls
back to Chat Completions, so the adapter works with both current and older
deployments.
"""

from __future__ import annotations

import time

import httpx

from .base import BaseProvider, ProviderError, ProviderResponse
from .pricing import estimate_cost


class OpenAICompatibleProvider(BaseProvider):
    kind = "openai"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_s, transport=self.transport)

    def _headers(self) -> dict:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.options.get("api_key_header"):
            headers = {"content-type": "application/json", self.options["api_key_header"]: self.api_key}
        for key, value in (self.options.get("extra_headers") or {}).items():
            headers[key] = value
        return headers

    # -- models ---------------------------------------------------------
    def list_models(self) -> list[str]:
        url = f"{self.base_url}/models"
        with self._client() as client:
            try:
                r = client.get(url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise ProviderError(self._redact(f"model discovery failed: {exc}"), retryable=True) from exc
            if r.status_code >= 400:
                raise ProviderError(f"model discovery failed: HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
        items = data.get("data", data if isinstance(data, list) else [])
        out = []
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
        return sorted(out)

    # -- chat -----------------------------------------------------------
    def _call_once(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        """One attempt. The retry/backoff logic lives in the base class.

        The OpenAI API is called through the Responses API when it is
        available and falls back to Chat Completions otherwise, so the adapter
        works with both current and older deployments.
        """
        style = self.options.get("api_style", "auto")
        if style in ("auto", "responses"):
            try:
                return self._chat_responses(messages, max_tokens, temperature)
            except ProviderError as exc:
                if style == "responses" or exc.status_code not in (404, 405, 501):
                    raise
                # The deployment does not expose /responses -> use chat/completions.
        return self._chat_completions(messages, max_tokens, temperature)

    def _chat_responses(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        system = " ".join(m["content"] for m in messages if m.get("role") == "system")
        rest = [m for m in messages if m.get("role") != "system"]
        payload: dict = {"model": self.model, "input": rest, "max_output_tokens": max_tokens}
        if system:
            payload["instructions"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        t0 = time.perf_counter()
        with self._client() as client:
            try:
                r = client.post(f"{self.base_url}/responses", headers=self._headers(), json=payload)
            except httpx.HTTPError as exc:
                raise ProviderError(self._redact(f"request failed: {exc}"), retryable=True) from exc
        latency = (time.perf_counter() - t0) * 1000
        if r.status_code in (404, 405, 501):
            raise ProviderError(f"Responses API unavailable (HTTP {r.status_code})", status_code=r.status_code)
        if r.status_code >= 400:
            raise ProviderError(
                f"HTTP {r.status_code}: {r.text[:300]}",
                status_code=r.status_code,
                retryable=r.status_code in (408, 409, 429, 500, 502, 503, 504),
            )
        data = r.json()
        text = _extract_responses_text(data)
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
            raw={"usage": usage},
        )

    def _chat_completions(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        payload: dict = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if temperature is not None:
            payload["temperature"] = temperature
        t0 = time.perf_counter()
        with self._client() as client:
            try:
                r = client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
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
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"malformed response from provider: {str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens", 0) or 0)
        out_tok = int(usage.get("completion_tokens", 0) or 0)
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
            raw={"usage": usage},
        )

    # -- embeddings -----------------------------------------------------
    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.options.get("embedding_model", self.model) or "text-embedding-3-small", "input": texts}
        with self._client() as client:
            try:
                r = client.post(f"{self.base_url}/embeddings", headers=self._headers(), json=payload)
            except httpx.HTTPError as exc:
                raise ProviderError(self._redact(f"embedding request failed: {exc}"), retryable=True) from exc
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:300]}", status_code=r.status_code)
        data = r.json()
        return [item["embedding"] for item in data.get("data", [])]

    def _price_in(self) -> float | None:
        value = self.options.get("price_per_1k_input")
        return float(value) if value not in (None, "") else None

    def _price_out(self) -> float | None:
        value = self.options.get("price_per_1k_output")
        return float(value) if value not in (None, "") else None


def _extract_responses_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output", []) or []:
        for block in item.get("content", []) or []:
            if block.get("type") in (None, "output_text") and isinstance(block.get("text"), str):
                chunks.append(block["text"])
    return "".join(chunks)
