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
