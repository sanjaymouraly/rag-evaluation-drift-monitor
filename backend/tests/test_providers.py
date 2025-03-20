"""Provider adapter tests.

The network is never touched: every test drives the adapters through a mock
transport so that failures, timeouts, rate limits and malformed responses can
be exercised deterministically.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.providers import BudgetGuard, FailoverProvider, ProviderConfig, build_provider
from app.providers.base import ProviderError
from app.providers.presets import PRESETS, get_preset
from app.providers.pricing import estimate_cost, price_per_1k


def _transport(handler):
    return httpx.MockTransport(handler)


def _json_response(payload, status_code=200):
    return httpx.Response(status_code, json=payload)


# ----------------------------------------------------------------- offline


def test_offline_provider_makes_no_network_call():
    provider = build_provider(ProviderConfig(kind="offline"))
    response = provider.chat([{"role": "user", "content": "hello"}])
    assert response.text
    assert response.cost_usd == 0.0
    assert response.provider == "offline"
    assert provider.test_connection()["ok"] is True


# ------------------------------------------------------------ openai wire


def test_openai_chat_completions_parses_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "gpt-6-luna"
        return _json_response(
            {
                "model": "gpt-6-luna",
                "choices": [{"message": {"content": "hello there"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            }
        )

    provider = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-6-luna",
            options={"api_style": "chat_completions"},
        )
    )
    provider.transport = _transport(handler)
    response = provider.chat([{"role": "user", "content": "hi"}])
    assert response.text == "hello there"
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert response.usage_exact is True
    # gpt-6-luna reference price is 0.1 / 0.5 USD per 1M tokens.
    assert response.cost_usd == pytest.approx(11 / 1000 * 0.0001 + 7 / 1000 * 0.0005)


def test_openai_responses_api_is_used_when_available():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/responses"):
            return _json_response(
                {
                    "model": "gpt-6-luna",
                    "output": [{"content": [{"type": "output_text", "text": "from responses"}]}],
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                }
            )
        raise AssertionError("should not reach chat/completions")

    provider = build_provider(
        ProviderConfig(kind="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-6-luna")
    )
    provider.transport = _transport(handler)
    response = provider.chat([{"role": "user", "content": "hi"}])
    assert response.text == "from responses"
    assert response.usage_exact is True


def test_openai_falls_back_to_chat_completions():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/responses"):
            return _json_response({"error": "not found"}, status_code=404)
        return _json_response(
            {"choices": [{"message": {"content": "fallback"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        )

    provider = build_provider(
        ProviderConfig(kind="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-6-luna")
    )
    provider.transport = _transport(handler)
    response = provider.chat([{"role": "user", "content": "hi"}])
    assert response.text == "fallback"


def test_openai_malformed_response_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"unexpected": "shape"})

    provider = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-6-luna",
            options={"api_style": "chat_completions"},
        )
    )
    provider.transport = _transport(handler)
    with pytest.raises(ProviderError):
        provider.chat([{"role": "user", "content": "hi"}])


def test_openai_rate_limit_is_retryable():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _json_response({"error": "slow down"}, status_code=429)
        return _json_response(
            {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        )

    provider = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-6-luna",
            retries=2,
            options={"api_style": "chat_completions"},
        )
    )
    provider.transport = _transport(handler)
    response = provider.chat([{"role": "user", "content": "hi"}])
    assert response.text == "ok"
    assert calls["n"] == 2


def test_openai_timeout_is_retried_then_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timed out", request=request)

    provider = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-6-luna",
            retries=1,
            options={"api_style": "chat_completions"},
        )
    )
    provider.transport = _transport(handler)
    with pytest.raises(ProviderError):
        provider.chat([{"role": "user", "content": "hi"}])
    assert calls["n"] == 2


def test_api_key_never_appears_in_an_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": "nope"}, status_code=401)

    provider = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-supersecretvalue",
            model="gpt-6-luna",
            retries=0,
            options={"api_style": "chat_completions"},
        )
    )
    provider.transport = _transport(handler)
    with pytest.raises(ProviderError) as excinfo:
        provider.chat([{"role": "user", "content": "hi"}])
    assert "sk-supersecretvalue" not in str(excinfo.value)


def test_model_discovery():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"data": [{"id": "gpt-6-luna"}, {"id": "gpt-6.1-sol"}]})

    provider = build_provider(
        ProviderConfig(kind="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-6-luna")
    )
    provider.transport = _transport(handler)
    assert provider.list_models() == sorted(["gpt-6-luna", "gpt-6.1-sol"])


# ------------------------------------------------------------ anthropic


def test_anthropic_messages_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/messages")
        assert request.headers["x-api-key"] == "sk-ant-test"
        return _json_response(
            {
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": "from claude"}],
                "usage": {"input_tokens": 4, "output_tokens": 2},
            }
        )

    provider = build_provider(
        ProviderConfig(
            kind="anthropic", base_url="https://api.anthropic.com", api_key="sk-ant-test", model="claude-haiku-5-5"
        )
    )
    provider.transport = _transport(handler)
    response = provider.chat([{"role": "user", "content": "hi"}])
    assert response.text == "from claude"
    assert response.input_tokens == 4
    assert response.usage_exact is True


def test_anthropic_model_discovery():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"data": [{"id": "claude-sonnet-5-5"}, {"id": "claude-haiku-5-5"}]})

    provider = build_provider(
        ProviderConfig(
            kind="anthropic", base_url="https://api.anthropic.com", api_key="sk-ant-test", model="claude-haiku-5-5"
        )
    )
    provider.transport = _transport(handler)
    assert provider.list_models() == ["claude-haiku-5-5", "claude-sonnet-5-5"]


# ---------------------------------------------------------------- ollama


def test_ollama_chat_and_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/tags"):
            return _json_response({"models": [{"name": "gemma3:270m"}]})
        return _json_response({"message": {"content": "local answer"}, "prompt_eval_count": 9, "eval_count": 4})

    provider = build_provider(ProviderConfig(kind="ollama", base_url="http://localhost:11434", model="gemma3:270m"))
    provider.transport = _transport(handler)
    assert provider.list_models() == ["gemma3:270m"]
    response = provider.chat([{"role": "user", "content": "hi"}])
    assert response.text == "local answer"
    assert response.cost_usd == 0.0


def test_ollama_unreachable_reports_honestly():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = build_provider(
        ProviderConfig(kind="ollama", base_url="http://localhost:11434", model="gemma3:270m", retries=0)
    )
    provider.transport = _transport(handler)
    result = provider.test_connection()
    assert result["ok"] is False
    assert "connection failed" in result["detail"]


# ---------------------------------------------------------- failover/budget


def test_failover_uses_the_next_provider():
    calls = {"a": 0, "b": 0}

    def failing(request: httpx.Request) -> httpx.Response:
        calls["a"] += 1
        return _json_response({"error": "boom"}, status_code=500)

    def working(request: httpx.Request) -> httpx.Response:
        calls["b"] += 1
        return _json_response(
            {
                "choices": [{"message": {"content": "second provider"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        )

    first = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://a.example/v1",
            api_key="k",
            model="m",
            retries=0,
            options={"api_style": "chat_completions"},
        )
    )
    first.transport = _transport(failing)
    second = build_provider(
        ProviderConfig(
            kind="openai",
            base_url="https://b.example/v1",
            api_key="k",
            model="m",
            retries=0,
            options={"api_style": "chat_completions"},
        )
    )
    second.transport = _transport(working)

    chain = FailoverProvider([first, second])
    response = chain.chat([{"role": "user", "content": "hi"}])
    assert response.text == "second provider"
    assert calls["a"] == 1 and calls["b"] == 1
    assert chain.attempts[0]["ok"] is False
    assert chain.attempts[1]["ok"] is True


def test_budget_guard_stops_at_the_limit():
    guard = BudgetGuard(1.0, label="test")
    guard.charge(0.6)
    guard.check(0.3)  # 0.6 + 0.3 <= 1.0 -> allowed
    with pytest.raises(Exception):
        guard.check(0.5)  # 0.6 + 0.5 > 1.0 -> blocked
    assert guard.snapshot()["spent_usd"] == pytest.approx(0.6)
    assert guard.snapshot()["remaining_usd"] == pytest.approx(0.4)


def test_unlimited_budget_never_blocks():
    guard = BudgetGuard(0.0)
    guard.charge(1000.0)
    guard.check(1000.0)
    assert guard.snapshot()["unlimited"] is True


# ------------------------------------------------------------- presets etc.


def test_every_preset_resolves_to_a_protocol_and_base_url():
    for key, preset in PRESETS.items():
        assert preset.protocol in ("openai", "anthropic", "ollama", "offline")
        if key not in ("custom", "offline", "azure_openai"):
            assert preset.base_url


def test_preset_lookup():
    assert get_preset("openai").protocol == "openai"
    assert get_preset("anthropic").protocol == "anthropic"
    assert get_preset("ollama").protocol == "ollama"
    assert get_preset("nope") is None


def test_reference_pricing():
    price_in, price_out, source = price_per_1k("gpt-6-luna")
    assert price_in == pytest.approx(0.0001)
    assert price_out == pytest.approx(0.0005)
    assert source == "reference"
    # Dated snapshots resolve through the longest-prefix match.
    assert price_per_1k("claude-haiku-5-5-20260101")[2] == "reference"
    # Unknown models are reported as unknown, never silently priced at zero.
    assert price_per_1k("some-unknown-model") == (0.0, 0.0, "unknown")


def test_estimate_cost_is_labelled_as_estimate():
    cost, is_estimate = estimate_cost("gpt-6-luna", 1000, 1000)
    assert is_estimate is True
    assert cost == pytest.approx(0.0001 + 0.0005)
    assert estimate_cost("unknown", 1000, 1000) == (0.0, True)
