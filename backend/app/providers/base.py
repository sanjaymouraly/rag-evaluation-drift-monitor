"""Provider base classes and shared response type."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..security import redact_text


class ProviderError(RuntimeError):
    """Raised when a provider call fails after all retries."""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ProviderBudgetExceeded(ProviderError):
    """Raised when a hard spending limit is reached."""


@dataclass
class ProviderResponse:
    """Normalised response from any provider."""

    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    usage_exact: bool = False
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    cost_is_estimate: bool = True
    raw: dict = field(default_factory=dict)
    error: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BaseProvider:
    """Common interface implemented by every provider adapter.

    Subclasses implement :meth:`_call_once`; the base class adds retry with
    exponential backoff, redaction of secrets in error messages and a uniform
    :class:`ProviderResponse`.
    """

    kind = "base"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
        timeout_s: float = 30.0,
        retries: int = 2,
        transport=None,
        **options,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or ""
        self.timeout_s = float(timeout_s)
        self.retries = max(0, int(retries))
        self.transport = transport
        self.options = options

    # -- public API -----------------------------------------------------
    def chat(self, messages: list[dict], max_tokens: int = 512, temperature: float = 0.0) -> ProviderResponse:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._call_once(messages, max_tokens, temperature)
            except ProviderError as exc:
                last = exc
                if not exc.retryable or attempt >= self.retries:
                    break
                time.sleep(min(2**attempt * 0.5, 8.0))
            except Exception as exc:  # noqa: BLE001 - network/protocol errors are retryable
                last = exc
                if attempt >= self.retries:
                    break
                time.sleep(min(2**attempt * 0.5, 8.0))
        raise ProviderError(self._redact(f"provider call failed after {self.retries + 1} attempt(s): {last}"))

    def list_models(self) -> list[str]:
        raise ProviderError(f"{self.kind} provider does not support model discovery")

    def test_connection(self) -> dict:
        try:
            models = self.list_models()
        except Exception as exc:  # noqa: BLE001 - report honestly, never fake success
            return {"ok": False, "detail": self._redact(f"connection failed: {exc}"), "models": []}
        return {"ok": True, "detail": f"Connected. {len(models)} model(s) visible.", "models": models[:100]}

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderError(f"{self.kind} provider does not support embeddings")

    # -- internals ------------------------------------------------------
    def _call_once(self, messages: list[dict], max_tokens: int, temperature: float) -> ProviderResponse:
        raise NotImplementedError

    def _redact(self, text: str) -> str:
        return redact_text(text, [self.api_key] if self.api_key else [])
