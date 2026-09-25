"""Compatibility dispatch tables for provider-family round helpers.

The provider-specific request implementations remain in ``llm_round_helpers``
while this module owns only the selection of an already-normalized caller.
"""

from __future__ import annotations

from typing import Any, Callable

from ..llm_round_helpers import (
    _call_deepseek_round,
    _call_openai_azure_round,
    _call_novita_round,
    _call_together_round,
    _call_vercel_round,
    _call_zai_round,
    _inception_registry_enabled,
)
from .legacy_gemini_adapter import _call_gemini_round
from .legacy_claude_adapter import _call_claude_round

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


def _call_with_fallback_chat_span(
    *,
    provider: str,
    caller: Callable[..., Any],
    kwargs: dict[str, Any],
) -> Any:
    """Trace exactly one compatibility provider call, excluding post-processing."""

    from .observability.runtime import fallback_chat_span

    with fallback_chat_span(
        provider=provider,
        model=str(kwargs.get("depname") or ""),
        request_input=kwargs.get("call_messages") or (),
        core=kwargs.get("core"),
    ) as observability_span:
        result = caller(**kwargs)
        if isinstance(result, tuple) and result and isinstance(result[0], bool):
            if result[0]:
                observability_span.set_attribute("uag.status", "completed")
                observability_span.set_status("ok")
            else:
                observability_span.set_attribute("uag.status", "failed")
                observability_span.set_status("error", "provider round failed")
        return result


def call_legacy_gemini_round(*, provider: str, **kwargs: Any) -> Any:
    """Dispatch Gemini-family rounds through the compatibility registry."""
    try:
        caller = _LEGACY_GEMINI_ROUND_CALLERS[(provider or "").strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported Gemini provider: {provider}") from exc
    if caller is _call_gemini_round:
        from .. import llm_round_helpers

        kwargs.setdefault("gemini_chat_fn", llm_round_helpers.gemini_chat_with_tools)
    return _call_with_fallback_chat_span(
        provider=provider,
        caller=caller,
        kwargs=kwargs,
    )


def call_legacy_claude_round(**kwargs: Any) -> Any:
    """Dispatch Claude rounds through the compatibility registry."""
    from .. import llm_round_helpers

    kwargs.setdefault("claude_chat_fn", llm_round_helpers.claude_chat_with_tools)
    return _call_with_fallback_chat_span(
        provider="claude",
        caller=_call_claude_round,
        kwargs=kwargs,
    )


def call_legacy_openai_azure_round(**kwargs: Any) -> Any:
    """Dispatch OpenAI-compatible Chat/Responses rounds."""
    provider = str(kwargs.get("provider") or "").strip().lower()
    if (
        provider == "inception"
        and bool(kwargs.get("stream_responses"))
        and _inception_registry_enabled()
    ):
        # The Inception streaming compatibility path delegates this exact
        # provider request to RoundOrchestrator, which owns its canonical chat
        # span. Do not wrap that call in a second fallback chat span.
        return _call_openai_azure_round(**kwargs)
    return _call_with_fallback_chat_span(
        provider=provider,
        caller=_call_openai_azure_round,
        kwargs=kwargs,
    )


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
    kwargs = {
        "provider": provider,
        "client": client,
        "depname": depname,
        "call_messages": call_messages,
        "core": core,
        "make_client_fn": make_client_fn,
        "call_maybe_thread_fn": call_maybe_thread_fn,
        "stream_responses": stream_responses,
        "send_tools_this_round": send_tools_this_round,
        "max_retries_429": max_retries_429,
        "retry_base": retry_base,
        "retry_cap": retry_cap,
    }
    if use_responses_api and provider == "deepseek":
        kwargs.update(
            {
                "use_responses_api": use_responses_api,
                "messages": messages,
                "responses_state": responses_state,
            }
        )
        caller = _call_openai_azure_round
    else:
        caller = _call_deepseek_round
    return _call_with_fallback_chat_span(
        provider=provider,
        caller=caller,
        kwargs=kwargs,
    )


def call_legacy_reasoning_round(*, provider: str, **kwargs: Any) -> Any:
    """Dispatch shared reasoning-provider rounds through one registry."""
    try:
        caller = _LEGACY_REASONING_ROUND_CALLERS[(provider or "").strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported legacy reasoning provider: {provider}") from exc
    return _call_with_fallback_chat_span(
        provider=provider,
        caller=caller,
        kwargs=kwargs,
    )


__all__ = [
    "call_legacy_claude_round",
    "call_legacy_deepseek_round",
    "call_legacy_gemini_round",
    "call_legacy_openai_azure_round",
    "call_legacy_reasoning_round",
]
