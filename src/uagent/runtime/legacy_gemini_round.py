"""Legacy Gemini/Vertex round orchestration outside the main round loop."""

from __future__ import annotations

import json
from typing import Any, Callable

from .. import core as _core_module
from .legacy_provider_dispatch import call_legacy_gemini_round

RoundResult = tuple[str, Any, str | None, int, str]


def run_legacy_gemini_round(
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
    append_assistant_message_fn: Callable[..., Any],
    handle_empty_no_tool_fn: Callable[..., tuple[str, int]],
    emit_final_answer_fn: Callable[..., Any],
    **_unused: Any,
) -> RoundResult:
    """Run Gemini/Vertex and preserve the legacy round-result contract."""
    ok, client, assistant_text, tool_calls_list, content_dump = (
        call_legacy_gemini_round(
            provider=provider,
            client=client,
            depname=depname,
            call_messages=call_messages,
            history_messages=messages,
            gemini_cache_name=gemini_cache_name,
            core=core,
            make_client_fn=make_client_fn,
            call_maybe_thread_fn=call_maybe_thread_fn,
            max_retries_429=max_retries_429,
            retry_base=retry_base,
            retry_cap=retry_cap,
            stream_responses=stream_responses,
            send_tools=send_tools_this_round,
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

    # Some Vertex/Gemini models emit only thought parts even when ANY/tool
    # selection is requested. Complete the discovery boundary host-side rather
    # than retrying the same thought-only request indefinitely.
    if (
        provider in ("gemini", "vertexai")
        and not judgment_mode
        and not tool_calls_list
        and not getattr(core, "_gemini_tool_catalog_ready", False)
    ):
        discovery_specs = getattr(core, "context_tool_specs", None)
        has_catalog = isinstance(discovery_specs, list) and any(
            isinstance(spec, dict)
            and (spec.get("function") or {}).get("name") == "tool_catalog"
            for spec in discovery_specs
        )
        if has_catalog:
            query = next(
                (
                    str(message.get("content") or "")[-4000:]
                    for message in reversed(messages)
                    if isinstance(message, dict) and message.get("role") == "user"
                ),
                "",
            )
            tool_calls_list = [
                {
                    "id": f"gemini_discovery_{len(messages)}",
                    "type": "function",
                    "function": {
                        "name": "tool_catalog",
                        "arguments": json.dumps(
                            {"query": query}, ensure_ascii=False
                        ),
                    },
                }
            ]

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
            gemini_content_dump=content_dump,
            skip_log_when_web=True,
        )

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
        if not stream_responses and not judgment_mode:
            emit_final_answer_fn(
                assistant_text=assistant_text,
                use_responses_api=use_responses_api,
                stream_responses=stream_responses,
                append_result_to_outfile_fn=append_result_to_outfile_fn,
                try_open_images_from_text_fn=try_open_images_from_text_fn,
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


__all__ = ["RoundResult", "run_legacy_gemini_round"]
