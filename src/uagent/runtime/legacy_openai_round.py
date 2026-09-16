"""Legacy OpenAI-compatible provider selection for one round."""

from __future__ import annotations

from typing import Any

from ..llm_grok_round import _call_grok_round
from .legacy_provider_dispatch import call_legacy_openai_azure_round

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


__all__ = ["RoundDispatchResult", "call_legacy_openai_compatible_round"]
