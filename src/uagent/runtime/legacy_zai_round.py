"""Legacy Z.AI/Novita round orchestration outside the main round loop."""

from __future__ import annotations

from typing import Any, Callable

from ..env_utils import env_get
from ..providers.llm_deepseek import build_assistant_message_with_reasoning
from .legacy_provider_dispatch import call_legacy_reasoning_round
from .legacy_round_support import (
    append_legacy_reasoning_assistant,
    consume_legacy_interrupt,
    finish_legacy_without_tools,
    resolve_legacy_empty_round,
)
from .legacy_tool_continuation import execute_legacy_tool_calls

RoundResult = tuple[str, Any, str | None, int, str]


def run_legacy_zai_round(
    *,
    provider: str,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    gemini_cache_name: str | None,
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
    empty_no_tool_rounds: int,
    empty_no_tool_max: int,
    tr_cfg: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    judgment_mode: bool,
    inject_stop_prompt_fn: Callable[[list[dict[str, Any]], Any], None],
    translate_assistant_fn: Callable[..., str],
    should_keep_assistant_message_fn: Callable[..., bool],
    handle_empty_no_tool_fn: Callable[..., tuple[str, int]],
    emit_final_answer_fn: Callable[..., Any],
    **_unused: Any,
) -> RoundResult:
    """Run Z.AI/Novita and preserve the legacy round-result contract."""
    ok, client, assistant_text, reasoning_content, tool_calls_list = (
        call_legacy_reasoning_round(
            provider=provider,
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
        )
    )
    if not ok:
        return (
            "return",
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )

    if consume_legacy_interrupt(
        messages=messages, core=core, inject_stop_prompt_fn=inject_stop_prompt_fn
    ):
        return (
            "break",
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )

    assistant_text = translate_assistant_fn(
        assistant_text=assistant_text,
        tr_cfg=tr_cfg,
        use_responses_api=False,
        stream_responses=False,
    )

    streaming_enabled = (
        env_get("UAGENT_STREAMING", "1") or ""
    ).strip().lower() not in ("0", "false", "no", "off")

    if should_keep_assistant_message_fn(assistant_text, tool_calls_list):
        append_legacy_reasoning_assistant(
            messages=messages,
            core=core,
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
            reasoning_content=reasoning_content,
            build_assistant_message_fn=build_assistant_message_with_reasoning,
            streaming_enabled=streaming_enabled,
            judgment_mode=judgment_mode,
        )

    empty_result, empty_no_tool_rounds = resolve_legacy_empty_round(
        handle_empty_no_tool_fn=handle_empty_no_tool_fn,
        assistant_text=assistant_text,
        tool_calls_list=tool_calls_list,
        empty_no_tool_rounds=empty_no_tool_rounds,
        empty_no_tool_max=empty_no_tool_max,
        provider=provider,
        depname=depname,
        messages=messages,
        core=core,
        client=client,
        cache_name=gemini_cache_name,
    )
    if empty_result is not None:
        return empty_result

    final_result = finish_legacy_without_tools(
        tool_calls_list=tool_calls_list,
        emit_final_answer_fn=emit_final_answer_fn,
        emit_final=not judgment_mode,
        emit_kwargs={
            "assistant_text": assistant_text,
            "use_responses_api": False,
            "stream_responses": False,
            "append_result_to_outfile_fn": append_result_to_outfile_fn,
            "try_open_images_from_text_fn": try_open_images_from_text_fn,
            "reasoning_content": reasoning_content,
            "skip_print": streaming_enabled,
            "core": core,
            "provider": provider,
        },
        client=client,
        cache_name=gemini_cache_name,
        empty_no_tool_rounds=empty_no_tool_rounds,
        assistant_text=assistant_text,
    )
    if final_result is not None:
        return final_result

    execute_legacy_tool_calls(
        tool_calls=tool_calls_list,
        messages=messages,
        core=core,
        cache_mgr=_unused.get("cache_mgr"),
        judgment_mode=judgment_mode,
    )

    return (
        "ok",
        client,
        gemini_cache_name,
        0,
        assistant_text,
    )


__all__ = ["RoundResult", "run_legacy_zai_round"]
