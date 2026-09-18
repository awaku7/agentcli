"""Legacy Claude round orchestration kept outside the main round loop."""

from __future__ import annotations

from typing import Any, Callable

from .. import core as _core_module
from .legacy_provider_dispatch import call_legacy_claude_round
from .legacy_tool_continuation import execute_legacy_tool_calls

RoundResult = tuple[str, Any, str | None, int, str]


def run_legacy_claude_round(
    *,
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
    append_assistant_message_fn: Callable[..., Any],
    handle_empty_no_tool_fn: Callable[..., tuple[str, int]],
    emit_final_answer_fn: Callable[..., Any],
    **_unused: Any,
) -> RoundResult:
    """Run Claude's compatibility round and its provider-neutral postprocess.

    The tuple contract intentionally matches ``uagent_llm._run_one_round``.
    All UI and loop callbacks are injected so this module does not import the
    main round loop or own persistent conversation state.
    """
    ok, client, assistant_text, tool_calls_list = call_legacy_claude_round(
        client=client,
        depname=depname,
        call_messages=call_messages,
        core=core,
        make_client_fn=make_client_fn,
        call_maybe_thread_fn=call_maybe_thread_fn,
        max_retries_429=max_retries_429,
        retry_base=retry_base,
        retry_cap=retry_cap,
        send_tools=send_tools_this_round,
        provider="claude",
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
                None,
                empty_no_tool_rounds,
                assistant_text,
            )

    assistant_text = translate_assistant_fn(
        assistant_text=assistant_text,
        tr_cfg=tr_cfg,
        use_responses_api=use_responses_api,
        stream_responses=stream_responses,
    )

    if should_keep_assistant_message_fn(assistant_text, tool_calls_list):
        append_assistant_message_fn(
            messages=messages,
            core=core,
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
        )

    action, empty_no_tool_rounds = handle_empty_no_tool_fn(
        assistant_text=assistant_text,
        tool_calls_list=tool_calls_list,
        empty_no_tool_rounds=empty_no_tool_rounds,
        empty_no_tool_max=empty_no_tool_max,
        provider="claude",
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
                reasoning_content="",
                use_responses_api=use_responses_api,
                stream_responses=stream_responses,
                append_result_to_outfile_fn=append_result_to_outfile_fn,
                try_open_images_from_text_fn=try_open_images_from_text_fn,
                core=core,
                provider="claude",
            )
        return (
            "break",
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )

    # Claude's legacy adapter owns the post-processing boundary, so execute
    # its tool calls here before returning ``RS_OK`` to the outer round loop.
    # The OpenAI/Gemini paths do this in their respective round handlers; if
    # Claude only returned the tuple, the loop would continue without ever
    # appending tool results and the same tool call would be repeated.
    execute_legacy_tool_calls(
        tool_calls=tool_calls_list,
        messages=messages,
        core=core,
        cache_mgr=_unused.get("cache_mgr"),
        responses_api_continuation=use_responses_api,
        judgment_mode=judgment_mode,
    )

    return (
        "ok",
        client,
        None,
        0,
        assistant_text,
    )


__all__ = ["RoundResult", "run_legacy_claude_round"]
