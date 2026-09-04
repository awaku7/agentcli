"""Provider capability constants for uagent.

Centralises provider-level feature sets so that individual modules
do not need to maintain their own copies of the same lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# All known provider keys. Centralised here to avoid duplication across files.
ALL_PROVIDERS: frozenset[str] = frozenset(
    {
        "azure",
        "openai",
        "meta",
        "bedrock",
        "openrouter",
        "ollama",
        "llama_cpp",
        "gemini",
        "vertexai",
        "grok",
        "claude",
        "nvidia",
        "deepseek",
        "zai",
        "alibaba",
        "moonshot",
        "mimo",
        "lmstudio",
        "minimax",
        "hf",
        "sakana",
        "sakura",
        "novita",
        "together",
        "vercel",
        "pfn",
    }
)

# Providers that support the OpenAI Responses API (/v1/responses).
RESPONSES_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "meta",
        "azure",
        "bedrock",
        "openrouter",
        "ollama",
        "alibaba",
        "lmstudio",
        "sakana",
        "deepseek",
    }
)


def supports_responses_output_item_replay(provider: str) -> bool:
    """Return whether prior Responses output items may be replayed."""
    return (provider or "").strip().lower() != "meta"


# Provider-specific sampling overrides are metadata, not orchestration logic.
# Keep the environment-variable mapping here so the round runner does not
# need a provider-name if/elif chain.
_TEMPERATURE_ENV_NAMES: dict[str, str] = {
    name: f"UAGENT_{name.upper()}_TEMPERATURE"
    for name in (
        "openai",
        "pfn",
        "azure",
        "openrouter",
        "bedrock",
        "nvidia",
        "grok",
        "zai",
        "sakana",
        "sakura",
        "novita",
        "together",
        "vercel",
    )
}


def temperature_env_name(provider: str) -> str | None:
    """Return the provider-specific temperature environment variable."""
    return _TEMPERATURE_ENV_NAMES.get((provider or "").strip().lower())


# Providers that can accept image inputs on the main chat path without
# requiring the OpenAI Responses API.  Each has provider-layer conversion:
# - openai/azure/openrouter: Chat Completions `image_url` parts
# - grok: `build_xai_messages` (`input_image` / `image_url`)
# - claude: Anthropic `image` base64 blocks from `image_url` data URLs
# - gemini/vertexai: `attachments` → Gemini image Parts
# - deepseek: DeepSeek Chat Completions `image_url` parts (vision model only)
#
# Responses-only providers (bedrock, alibaba, ollama, lmstudio, sakana, …)
# remain gated by UAGENT_RESPONSES + RESPONSES_PROVIDERS at the call site.
_CHAT_VISION_FORMATS: dict[str, str] = {
    "openai": "image_url",
    "azure": "image_url",
    "openrouter": "image_url",
    "grok": "image_url",
    "claude": "image_url",
    "gemini": "attachments",
    "vertexai": "attachments",
    "deepseek": "image_url",
    "llama_cpp": "image_url",
}


# Providers that support Fill-in-the-Middle (FIM) code completion.
LOCAL_ENDPOINT_PROVIDERS: frozenset[str] = frozenset(
    {"ollama", "llama_cpp", "lmstudio"}
)

CLOUD_CREDENTIAL_PROVIDERS: frozenset[str] = frozenset({"bedrock", "vertexai"})


# Providers that support Fill-in-the-Middle (FIM) code completion.
FIM_SUPPORTED_PROVIDERS: frozenset[str] = frozenset(
    {
        "ollama",
        "deepseek",
    }
)


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    capabilities: frozenset[str]
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool
    chat_vision_format: str | None = None
    credential_sources: tuple[str, ...] = ()
    cost_hint: str | None = None
    context_limit: int | None = None
    routing_policy: str = "default"
    auth_requirement: str = "api_key"


class ProviderRegistry(Protocol):
    def resolve(self, provider: str, model: str | None = None) -> ProviderSpec: ...

    def list(self) -> tuple[ProviderSpec, ...]: ...


class StaticProviderRegistry:
    """Deterministic provider capability lookup used by runtime and UI code."""

    def resolve(self, provider: str, model: str | None = None) -> ProviderSpec:
        name = (provider or "").strip().lower()
        if name not in ALL_PROVIDERS:
            return ProviderSpec(
                name=name or "unknown",
                capabilities=frozenset({"unknown"}),
                supports_tools=False,
                supports_streaming=False,
                supports_vision=False,
                auth_requirement="unknown",
            )
        capabilities = {"chat", "streaming"}
        if name in LOCAL_ENDPOINT_PROVIDERS:
            auth_requirement = "local_endpoint"
        elif name in CLOUD_CREDENTIAL_PROVIDERS:
            auth_requirement = "cloud_credentials"
        else:
            auth_requirement = "api_key"
        if name in RESPONSES_PROVIDERS:
            capabilities.add("responses")
        chat_vision_format = _CHAT_VISION_FORMATS.get(name)
        if chat_vision_format is not None:
            capabilities.add("vision")
        if name in FIM_SUPPORTED_PROVIDERS:
            capabilities.add("fim")
        if name != "hf":
            capabilities.add("tools")
        return ProviderSpec(
            name=name,
            capabilities=frozenset(capabilities),
            supports_tools="tools" in capabilities,
            supports_streaming=True,
            supports_vision="vision" in capabilities,
            chat_vision_format=chat_vision_format,
            credential_sources=("credential_store", "environment"),
            auth_requirement=auth_requirement,
        )

    def list(self) -> tuple[ProviderSpec, ...]:
        """Return all known provider specifications in deterministic order."""
        return tuple(self.resolve(name) for name in sorted(ALL_PROVIDERS))


DEFAULT_PROVIDER_REGISTRY = StaticProviderRegistry()
