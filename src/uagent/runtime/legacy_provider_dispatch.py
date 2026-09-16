"""Compatibility dispatch tables for provider-family round helpers.

The provider-specific request implementations remain in ``llm_round_helpers``
while this module owns only the selection of an already-normalized caller.
"""

from __future__ import annotations

from typing import Any

from ..llm_round_helpers import (
    _call_claude_round,
    _call_deepseek_round,
    _call_openai_azure_round,
    _call_novita_round,
    _call_together_round,
    _call_vercel_round,
    _call_zai_round,
)
from .legacy_gemini_adapter import _call_gemini_round

_LEGACY_REASONING_ROUND_CALLERS = {
    "zai": _call_zai_round,
    "vercel": _call_vercel_round,
    "together": _call_together_round,
    "novita": _call_novita_round,
}

_LEGACY_GEMINI_ROUND_CALLERS = {
    "gemini": _call_gemini_round,
    "vertexai": _call_gemini_round,
}


def call_legacy_gemini_round(*, provider: str, **kwargs: Any) -> Any:
    """Dispatch Gemini-family rounds through the compatibility registry."""
    try:
        caller = _LEGACY_GEMINI_ROUND_CALLERS[(provider or "").strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported Gemini provider: {provider}") from exc
    if caller is _call_gemini_round:
        from .. import llm_round_helpers

        kwargs.setdefault("gemini_chat_fn", llm_round_helpers.gemini_chat_with_tools)
    return caller(**kwargs)


def call_legacy_claude_round(**kwargs: Any) -> Any:
    """Dispatch Claude rounds through the compatibility registry."""
    return _call_claude_round(**kwargs)


def call_legacy_openai_azure_round(**kwargs: Any) -> Any:
    """Dispatch OpenAI-compatible Chat/Responses rounds."""
    return _call_openai_azure_round(**kwargs)


def call_legacy_deepseek_round(
    *,
    provider: str,
    use_responses_api: bool,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    stream_responses: bool,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    messages: list[dict[str, Any]],
    responses_state: dict[str, Any],
) -> Any:
    """Dispatch DeepSeek's Responses compatibility route or chat route."""
    if use_responses_api and provider == "deepseek":
        return _call_openai_azure_round(
            provider=provider,
            client=client,
            depname=depname,
            call_messages=call_messages,
            core=core,
            make_client_fn=make_client_fn,
            call_maybe_thread_fn=call_maybe_thread_fn,
            use_responses_api=use_responses_api,
            stream_responses=stream_responses,
            send_tools_this_round=send_tools_this_round,
            max_retries_429=max_retries_429,
            retry_base=retry_base,
            retry_cap=retry_cap,
            messages=messages,
            responses_state=responses_state,
        )
    return _call_deepseek_round(
        client=client,
        depname=depname,
        call_messages=call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        send_tools_this_round=send_tools_this_round,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        provider=provider,
    )


def call_legacy_reasoning_round(*, provider: str, **kwargs: Any) -> Any:
    """Dispatch shared reasoning-provider rounds through one registry."""
    try:
        caller = _LEGACY_REASONING_ROUND_CALLERS[(provider or "").strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported legacy reasoning provider: {provider}") from exc
    return caller(**kwargs)


__all__ = [
    "call_legacy_claude_round",
    "call_legacy_deepseek_round",
    "call_legacy_gemini_round",
    "call_legacy_openai_azure_round",
    "call_legacy_reasoning_round",
]
