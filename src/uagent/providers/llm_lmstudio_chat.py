"""LM Studio OpenAI-compatible Chat Completions transport."""

from __future__ import annotations

from typing import Any

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get
from .llm_lmstudio_responses import normalize_base_url


def make_client(core: Any) -> Any:
    """Create an OpenAI SDK client for LM Studio Chat Completions."""
    from openai import OpenAI

    getter = getattr(core, "get_env", None)

    def get(name: str, default: str = "") -> str:
        if callable(getter):
            return str(getter(name) or default)
        return str(env_get(name, default) or default)

    base_url = normalize_base_url(
        get("UAGENT_LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    )
    api_key = (
        get_provider_api_key(
            "LMSTUDIO",
            store=getattr(core, "credential_store", None),
            env_getter=getter if callable(getter) else None,
        )
        or "dummy"
    )
    try:
        from .util_providers import make_httpx_client

        return OpenAI(
            api_key=api_key, base_url=base_url, http_client=make_httpx_client()
        )
    except TypeError:
        return OpenAI(api_key=api_key, base_url=base_url)


def prepare_kwargs(kwargs: dict[str, Any]) -> None:
    """Remove fields that belong to the Responses API."""
    if kwargs.pop("_lmstudio_transport", None) != "chat":
        return
    for key in (
        "input",
        "instructions",
        "previous_response_id",
        "context_management",
        "max_output_tokens",
        "text",
        "reasoning",
    ):
        kwargs.pop(key, None)
