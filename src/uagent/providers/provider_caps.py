"""Provider capability constants for uagent.

Centralises provider-level feature sets so that individual modules
do not need to maintain their own copies of the same lists.
"""

from __future__ import annotations

# All known provider keys. Centralised here to avoid duplication across files.
ALL_PROVIDERS: frozenset[str] = frozenset(
    {
        "azure",
        "openai",
        "bedrock",
        "openrouter",
        "ollama",
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
    }
)

# Providers that support the OpenAI Responses API (/v1/responses).
RESPONSES_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "azure",
        "bedrock",
        "openrouter",
        "ollama",
        "alibaba",
        "lmstudio",
        "sakana",
    }
)


# Providers that can accept image inputs on the main chat path without
# requiring the OpenAI Responses API.  Each has provider-layer conversion:
# - openai/azure/openrouter: Chat Completions `image_url` parts
# - grok: `build_xai_messages` (`input_image` / `image_url`)
# - claude: Anthropic `image` base64 blocks from `image_url` data URLs
# - gemini/vertexai: `attachments` → Gemini image Parts
#
# Responses-only providers (bedrock, alibaba, ollama, lmstudio, sakana, …)
# remain gated by UAGENT_RESPONSES + RESPONSES_PROVIDERS at the call site.
CHAT_VISION_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "azure",
        "openrouter",
        "grok",
        "claude",
        "gemini",
        "vertexai",
    }
)


# Providers that support Fill-in-the-Middle (FIM) code completion.
FIM_SUPPORTED_PROVIDERS: frozenset[str] = frozenset(
    {
        "ollama",
        "deepseek",
    }
)
