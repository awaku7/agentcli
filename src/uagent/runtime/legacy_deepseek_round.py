"""Legacy DeepSeek/MiMo round orchestration outside the main round loop."""

from __future__ import annotations

from typing import Any, Callable

from .. import core as _core_module
from ..env_utils import env_get
from ..providers.llm_deepseek import build_assistant_message_with_reasoning
from .legacy_provider_dispatch import call_legacy_deepseek_round

RoundResult = tuple[str, Any, str | None, int, str]


def run_legacy_deepseek_round(
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
    use_responses_api: bool,
    stream_responses: bool,
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
) -> RoundResult:
    """Run DeepSeek/MiMo and preserve the legacy round-result contract."""
    ok, client, assistant_text, reasoning_content, tool_calls_list = (
        call_legacy_deepseek_round(
            provider=provider,
            use_responses_api=use_responses_api,
            client=client,
            depname=depname,
            call_messages=call_messages,
            core=core,
            make_client_fn=make_client_fn,
            call_maybe_thread_fn=call_maybe_thread_fn,
            stream_responses=stream_responses,
            send_tools_this_round=send_tools_this_round,
            max_retries_429=max_retries_429,
            retry_base=retry_base,
            retry_cap=retry_cap,
            messages=messages,
            responses_state=core.responses_state,
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

    with _core_module.interrupt_lock:
        if _core_module.interrupt_requested:
            _core_module.interrupt_requested = False
            inject_stop_prompt_fn(messages, core)
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
        use_responses_api=use_responses_api,
        stream_responses=stream_responses,
    )

    streaming_enabled = (
        env_get("UAGENT_STREAMING", "1") or ""
    ).strip().lower() not in ("0", "false", "no", "off")
    output_already_printed = (use_responses_api and stream_responses) or (
        not use_responses_api and streaming_enabled
    )

    if should_keep_assistant_message_fn(assistant_text, tool_calls_list):
        deepseek_message = build_assistant_message_with_reasoning(
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
            reasoning_content=reasoning_content,
        )
        messages.append(deepseek_message)
        if not (bool(getattr(core, "_is_web", False)) and streaming_enabled):
            if not judgment_mode:
                core.log_message(deepseek_message)

    action, empty_no_tool_rounds = handle_empty_no_tool_fn(
        assistant_text=assistant_text,
        tool_calls_list=tool_calls_list,
        empty_no_tool_rounds=empty_no_tool_rounds,
        empty_no_tool_max=empty_no_tool_max,
        provider=provider,
        depname=depname,
        messages=messages,
        core=core,
    )
    if action == "continue":
        return (
            "continue",
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )
    if action == "break":
        return (
            "break",
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )

    if not tool_calls_list:
        if not judgment_mode:
            emit_final_answer_fn(
                assistant_text=assistant_text,
                use_responses_api=use_responses_api,
                stream_responses=stream_responses,
                append_result_to_outfile_fn=append_result_to_outfile_fn,
                try_open_images_from_text_fn=try_open_images_from_text_fn,
                reasoning_content=reasoning_content,
                skip_print=output_already_printed,
                core=core,
                provider=provider,
            )
        return (
            "break",
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )

    return (
        "ok",
        client,
        gemini_cache_name,
        0,
        assistant_text,
    )


__all__ = ["RoundResult", "run_legacy_deepseek_round"]
