"""Provider presets.

The UI is built from this table so a user can pick "Anthropic Claude" and get a
pre-filled base URL without copying URLs from documentation. Every preset states
honestly what it needs (an API key, a local server, ...) so nobody assumes a
ChatGPT subscription includes API credits.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderPreset:
    key: str
    label: str
    protocol: str  # openai | anthropic | ollama | offline
    base_url: str
    default_model: str
    requires_key: bool = True
    notes: str = ""
    models_endpoint: str = "/models"
    extra: dict = field(default_factory=dict)


PRESETS: dict[str, ProviderPreset] = {
    "offline": ProviderPreset(
        key="offline",
        label="Offline deterministic (no API key)",
        protocol="offline",
        base_url="",
        default_model="deterministic-metrics",
        requires_key=False,
        notes="Free, no network access. Uses only deterministic and heuristic metrics.",
    ),
    "openai": ProviderPreset(
        key="openai",
        label="OpenAI API",
        protocol="openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-6-luna",
        notes=(
            "Uses the OpenAI API (api.openai.com). A ChatGPT Plus/Pro subscription "
            "does NOT include API credits — a separate API key with billing is required."
        ),
    ),
    "anthropic": ProviderPreset(
        key="anthropic",
        label="Anthropic Claude API",
        protocol="anthropic",
        base_url="https://api.anthropic.com",
        default_model="claude-haiku-5-5",
        notes="Uses the Anthropic Messages API. Requires an Anthropic API key.",
    ),
    "openrouter": ProviderPreset(
        key="openrouter",
        label="OpenRouter",
        protocol="openai",
        base_url="https://openrouter.ai/api/v1",
        default_model="",
        notes="Aggregator: one key, many models. Models and prices are listed by OpenRouter.",
    ),
    "ollama": ProviderPreset(
        key="ollama",
        label="Ollama (local, free)",
        protocol="ollama",
        base_url="http://localhost:11434",
        default_model="",
        requires_key=False,
        notes="Runs locally, no key and no cost. Start Ollama and pull a model first.",
        models_endpoint="/api/tags",
    ),
    "custom": ProviderPreset(
        key="custom",
        label="Custom OpenAI-compatible endpoint",
        protocol="openai",
        base_url="",
        default_model="",
        notes="Any service exposing /chat/completions (vLLM, LM Studio, llama.cpp server, Groq, Mistral, DeepSeek...).",
    ),
    "azure_openai": ProviderPreset(
        key="azure_openai",
        label="Azure OpenAI",
        protocol="openai",
        base_url="",
        default_model="",
        notes="Set the resource endpoint; use api-key or api-version query parameters as documented by Azure.",
    ),
    "together": ProviderPreset(
        key="together",
        label="Together AI",
        protocol="openai",
        base_url="https://api.together.xyz/v1",
        default_model="",
    ),
    "groq": ProviderPreset(
        key="groq",
        label="Groq",
        protocol="openai",
        base_url="https://api.groq.com/openai/v1",
        default_model="",
    ),
    "deepseek": ProviderPreset(
        key="deepseek",
        label="DeepSeek",
        protocol="openai",
        base_url="https://api.deepseek.com/v1",
        default_model="",
    ),
    "mistral": ProviderPreset(
        key="mistral",
        label="Mistral AI",
        protocol="openai",
        base_url="https://api.mistral.ai/v1",
        default_model="",
    ),
    "lmstudio": ProviderPreset(
        key="lmstudio",
        label="LM Studio (local)",
        protocol="openai",
        base_url="http://localhost:1234/v1",
        default_model="",
        requires_key=False,
    ),
    "vllm": ProviderPreset(
        key="vllm",
        label="vLLM (local)",
        protocol="openai",
        base_url="http://localhost:8000/v1",
        default_model="",
        requires_key=False,
    ),
}

# Roles a profile can play.
ROLES = {
    "generation": "Answer generation for the RAG under test",
    "embedding": "Embedding model for semantic similarity metrics",
    "judge": "LLM-as-a-judge for faithfulness / correctness opinions",
}


def preset_list() -> list[dict]:
    return [
        {
            "key": p.key,
            "label": p.label,
            "protocol": p.protocol,
            "base_url": p.base_url,
            "default_model": p.default_model,
            "requires_key": p.requires_key,
            "notes": p.notes,
        }
        for p in PRESETS.values()
    ]


def get_preset(kind: str) -> ProviderPreset | None:
    return PRESETS.get((kind or "").lower())
