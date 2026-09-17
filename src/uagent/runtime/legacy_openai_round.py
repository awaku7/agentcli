"""Legacy OpenAI-compatible provider selection for one round."""

from __future__ import annotations

from typing import Any

from ..llm_grok_round import _call_grok_round
from .legacy_provider_dispatch import call_legacy_openai_azure_round
from .legacy_round_registry import (
    LegacyRoundOutcome,
    RoundOutcomeCapabilities,
)

RoundDispatchResult = tuple[bool, Any, str, str, list[dict[str, Any]], bool]


def call_legacy_openai_compatible_round(
    *,
    provider: str,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    use_responses_api: bool,
    stream_responses: bool,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    messages: list[dict[str, Any]],
    responses_state: dict[str, Any],
    round_count: int,
) -> RoundDispatchResult:
    """Select Grok gRPC or the normalized OpenAI-compatible caller."""
    is_xai_grpc = False
    if provider == "grok":
        try:
            from xai_sdk import Client as _XAIClient

            is_xai_grpc = isinstance(client, _XAIClient)
        except Exception:
            is_xai_grpc = False

        if is_xai_grpc:
            ok, client, assistant_text, tool_calls_list = _call_grok_round(
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
            return ok, client, assistant_text, "", tool_calls_list, True

    ok, client, assistant_text, reasoning_content, tool_calls_list = (
        call_legacy_openai_azure_round(
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
            round_count=round_count,
        )
    )
    return ok, client, assistant_text, reasoning_content, tool_calls_list, False


def call_legacy_openai_compatible_outcome(
    **kwargs: Any,
) -> LegacyRoundOutcome:
    """Wrap the OpenAI-compatible tuple for the shared legacy boundary."""
    result = call_legacy_openai_compatible_round(**kwargs)
    ok, client, assistant_text, reasoning_text, tool_calls, is_xai_grpc = result
    return LegacyRoundOutcome(
        provider=str(kwargs.get("provider") or "").strip().lower(),
        status="ok" if ok else "return",
        assistant_text=str(assistant_text or ""),
        raw_result=result,
        client=client,
        reasoning_text=str(reasoning_text or ""),
        tool_calls=tuple(tool_calls or ()),
        is_xai_grpc=bool(is_xai_grpc),
        capabilities=RoundOutcomeCapabilities(
            host_rendered=bool(
                kwargs.get("stream_responses")
                and (is_xai_grpc or str(kwargs.get("provider") or "") == "inception")
            ),
            supports_tool_continuation=bool(tool_calls),
        ),
        flow="openai_compatible",
    )


__all__ = [
    "RoundDispatchResult",
    "call_legacy_openai_compatible_outcome",
    "call_legacy_openai_compatible_round",
]
