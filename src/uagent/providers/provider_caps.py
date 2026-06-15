"""Provider capability constants for uagent.

Centralises provider-level feature sets so that individual modules
do not need to maintain their own copies of the same lists.
"""

from __future__ import annotations

# Providers that support the OpenAI Responses API (/v1/responses).
RESPONSES_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "azure",
        "bedrock",
        "openrouter",
        "ollama",
        "alibaba",
    }
)
