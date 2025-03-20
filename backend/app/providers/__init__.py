"""Provider factory, failover chain and budget guard."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .anthropic import AnthropicProvider
from .base import BaseProvider, ProviderBudgetExceeded, ProviderError, ProviderResponse
from .offline import OfflineProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatibleProvider
from .presets import PRESETS, get_preset

_PROTOCOL_FOR_KIND = {
    "offline": "offline",
    "openai": "openai",
    "openrouter": "openai",
    "custom": "openai",
    "azure_openai": "openai",
    "together": "openai",
    "groq": "openai",
    "deepseek": "openai",
    "mistral": "openai",
    "lmstudio": "openai",
    "vllm": "openai",
    "anthropic": "anthropic",
    "ollama": "ollama",
}


def protocol_for(kind: str) -> str:
    """Map a profile kind to its wire protocol."""
    kind = (kind or "offline").lower()
    if kind in _PROTOCOL_FOR_KIND:
        return _PROTOCOL_FOR_KIND[kind]
    preset = get_preset(kind)
    if preset:
        return preset.protocol
    return "openai"


def default_base_url(kind: str) -> str:
    preset = get_preset(kind)
    if preset:
        return preset.base_url
    return ""


@dataclass
class ProviderConfig:
    """Transport-level configuration of one provider profile."""

    name: str = ""
    kind: str = "offline"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_s: float = 30.0
    retries: int = 2
    price_per_1k_input: float = 0.0
    price_per_1k_output: float = 0.0
    max_concurrency: int = 4
    options: dict = field(default_factory=dict)

    @classmethod
    def from_profile(cls, profile) -> ProviderConfig:
        return cls(
            name=getattr(profile, "name", "") or "",
            kind=getattr(profile, "kind", "offline") or "offline",
            base_url=getattr(profile, "base_url", "") or default_base_url(getattr(profile, "kind", "offline")),
            api_key=getattr(profile, "api_key", "") or "",
            model=getattr(profile, "model", "") or "",
            timeout_s=float(getattr(profile, "timeout_s", 30.0) or 30.0),
            retries=int(getattr(profile, "retries", 2) or 0),
            price_per_1k_input=float(getattr(profile, "price_per_1k_input", 0.0) or 0.0),
            price_per_1k_output=float(getattr(profile, "price_per_1k_output", 0.0) or 0.0),
            max_concurrency=int(getattr(profile, "max_concurrency", 4) or 4),
        )

    @classmethod
    def from_mapping(cls, data: dict) -> ProviderConfig:
        return cls(
            name=data.get("name", "") or "",
            kind=data.get("kind", "offline") or "offline",
            base_url=data.get("base_url", "") or default_base_url(data.get("kind", "offline")),
            api_key=data.get("api_key", "") or "",
            model=data.get("model", "") or "",
            timeout_s=float(data.get("timeout_s", 30.0) or 30.0),
            retries=int(data.get("retries", 2) or 0),
            price_per_1k_input=float(data.get("price_per_1k_input", 0.0) or 0.0),
            price_per_1k_output=float(data.get("price_per_1k_output", 0.0) or 0.0),
            max_concurrency=int(data.get("max_concurrency", 4) or 4),
            options=dict(data.get("options") or {}),
        )


def build_provider(config: ProviderConfig) -> BaseProvider:
    """Instantiate the adapter for a provider configuration."""
    protocol = protocol_for(config.kind)
    base_url = config.base_url or default_base_url(config.kind)
    options = dict(config.options)
    if config.price_per_1k_input:
        options.setdefault("price_per_1k_input", config.price_per_1k_input)
    if config.price_per_1k_output:
        options.setdefault("price_per_1k_output", config.price_per_1k_output)
    if protocol == "offline":
        return OfflineProvider(
            base_url=base_url,
            api_key=config.api_key,
            model=config.model or "offline-deterministic",
            timeout_s=config.timeout_s,
            retries=config.retries,
            **options,
        )
    if protocol == "anthropic":
        return AnthropicProvider(
            base_url=base_url or "https://api.anthropic.com",
            api_key=config.api_key,
            model=config.model,
            timeout_s=config.timeout_s,
            retries=config.retries,
            **options,
        )
    if protocol == "ollama":
        return OllamaProvider(
            base_url=base_url or "http://localhost:11434",
            api_key=config.api_key,
            model=config.model,
            timeout_s=config.timeout_s,
            retries=config.retries,
            **options,
        )
    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=config.api_key,
        model=config.model,
        timeout_s=config.timeout_s,
        retries=config.retries,
        **options,
    )


class FailoverProvider(BaseProvider):
    """Tries a list of providers in order until one succeeds.

    Only *provider errors* trigger a failover. A budget violation is a hard
    stop: failing over would just spend more money.
    """

    kind = "failover"

    def __init__(self, providers: list[BaseProvider]):
        super().__init__()
        self.providers = providers
        self.attempts: list[dict] = []

    def chat(self, messages: list[dict], max_tokens: int = 512, temperature: float = 0.0) -> ProviderResponse:
        self.attempts = []
        last: Exception | None = None
        for provider in self.providers:
            try:
                response = provider.chat(messages, max_tokens, temperature)
                self.attempts.append({"provider": provider.kind, "ok": True})
                return response
            except ProviderBudgetExceeded:
                raise
            except Exception as exc:  # noqa: BLE001 - failover is the whole point
                last = exc
                self.attempts.append({"provider": provider.kind, "ok": False, "error": str(exc)[:200]})
        raise ProviderError(f"all providers failed: {last}")

    def list_models(self) -> list[str]:
        models: list[str] = []
        for provider in self.providers:
            try:
                models.extend(provider.list_models())
            except Exception:  # noqa: BLE001
                continue
        return sorted(set(models))

    def test_connection(self) -> dict:
        results = []
        for provider in self.providers:
            result = provider.test_connection()
            results.append({"provider": provider.kind, **result})
        return {
            "ok": any(r.get("ok") for r in results),
            "detail": "; ".join(
                f"{r['provider']}: {'ok' if r.get('ok') else r.get('detail', 'failed')}" for r in results
            ),
            "models": self.list_models()[:100],
            "attempts": results,
        }


class BudgetGuard:
    """Hard spending limit with thread-safe accounting.

    ``limit_usd <= 0`` means "no limit" and is reported as such.
    """

    def __init__(self, limit_usd: float = 0.0, label: str = "run"):
        self.limit_usd = float(limit_usd or 0.0)
        self.label = label
        self.spent_usd = 0.0
        self.calls = 0
        self._lock = threading.Lock()

    @property
    def unlimited(self) -> bool:
        return self.limit_usd <= 0

    def remaining(self) -> float:
        if self.unlimited:
            return float("inf")
        return max(0.0, self.limit_usd - self.spent_usd)

    def check(self, estimated_next: float = 0.0) -> None:
        if self.unlimited:
            return
        if self.spent_usd + estimated_next > self.limit_usd:
            raise ProviderBudgetExceeded(
                f"{self.label} budget exhausted: spent ${self.spent_usd:.4f} of ${self.limit_usd:.4f}"
            )

    def charge(self, cost_usd: float) -> None:
        with self._lock:
            self.spent_usd += float(cost_usd or 0.0)
            self.calls += 1

    def snapshot(self) -> dict:
        return {
            "label": self.label,
            "limit_usd": self.limit_usd if not self.unlimited else None,
            "unlimited": self.unlimited,
            "spent_usd": round(self.spent_usd, 6),
            "remaining_usd": None if self.unlimited else round(self.remaining(), 6),
            "calls": self.calls,
        }


__all__ = [
    "PRESETS",
    "BudgetGuard",
    "FailoverProvider",
    "ProviderBudgetExceeded",
    "ProviderConfig",
    "ProviderError",
    "build_provider",
    "default_base_url",
    "protocol_for",
]
