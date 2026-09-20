"""Shared boundaries for legacy provider round adapters."""

from __future__ import annotations

from typing import Any, Callable

from .. import core as _core_module
from .logging_setup import log_event
from .telemetry import reconcile_usage


def consume_legacy_interrupt(
    *,
    messages: list[dict[str, Any]],
    core: Any,
    inject_stop_prompt_fn: Callable[[list[dict[str, Any]], Any], None],
) -> bool:
    """Consume a pending interrupt and inject the common stop prompt once."""
    with _core_module.interrupt_lock:
        if not _core_module.interrupt_requested:
            return False
        _core_module.interrupt_requested = False
    inject_stop_prompt_fn(messages, core)
    return True


def translate_and_append_legacy_assistant(
    *,
    assistant_text: str,
    tr_cfg: Any,
    use_responses_api: bool,
    stream_responses: bool,
    translate_assistant_fn: Callable[..., str],
    should_keep_assistant_message_fn: Callable[..., bool],
    append_assistant_message_fn: Callable[..., Any],
    append_kwargs: dict[str, Any],
) -> str:
    """Apply shared translation and assistant-message retention policy."""
    translated = translate_assistant_fn(
        assistant_text=assistant_text,
        tr_cfg=tr_cfg,
        use_responses_api=use_responses_api,
        stream_responses=stream_responses,
    )
    if should_keep_assistant_message_fn(
        translated, append_kwargs.get("tool_calls_list", ())
    ):
        append_assistant_message_fn(
            **append_kwargs,
            assistant_text=translated,
        )
    return translated


def append_legacy_reasoning_assistant(
    *,
    messages: list[dict[str, Any]],
    core: Any,
    assistant_text: str,
    tool_calls_list: list[dict[str, Any]],
    reasoning_content: str,
    build_assistant_message_fn: Callable[..., dict[str, Any]],
    streaming_enabled: bool,
    judgment_mode: bool,
    log_message: bool = True,
) -> dict[str, Any]:
    """Append a reasoning-provider assistant message and apply host logging."""
    message = build_assistant_message_fn(
        assistant_text=assistant_text,
        tool_calls_list=tool_calls_list,
        reasoning_content=reasoning_content,
    )
    messages.append(message)
    if (
        log_message
        and not (bool(getattr(core, "_is_web", False)) and streaming_enabled)
        and not judgment_mode
    ):
        core.log_message(message)
    return message


def finish_legacy_without_tools(
    *,
    tool_calls_list: list[dict[str, Any]],
    emit_final_answer_fn: Callable[..., Any],
    emit_final: bool,
    emit_kwargs: dict[str, Any],
    client: Any,
    cache_name: str | None,
    empty_no_tool_rounds: int,
    assistant_text: str,
) -> tuple[str, Any, str | None, int, str] | None:
    """Emit a completed legacy answer and return its shared result tuple."""
    if tool_calls_list:
        return None
    if emit_final:
        emit_final_answer_fn(**emit_kwargs)
    return (
        "break",
        client,
        cache_name,
        empty_no_tool_rounds,
        assistant_text,
    )


def resolve_legacy_empty_round(
    *,
    handle_empty_no_tool_fn: Callable[..., tuple[str, int]],
    assistant_text: str,
    tool_calls_list: list[dict[str, Any]],
    empty_no_tool_rounds: int,
    empty_no_tool_max: int,
    provider: str,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    client: Any,
    cache_name: str | None,
) -> tuple[tuple[str, Any, str | None, int, str] | None, int]:
    """Apply empty-tool recovery and normalize its early-return tuple."""
    action, updated_rounds = handle_empty_no_tool_fn(
        assistant_text=assistant_text,
        tool_calls_list=tool_calls_list,
        empty_no_tool_rounds=empty_no_tool_rounds,
        empty_no_tool_max=empty_no_tool_max,
        provider=provider,
        depname=depname,
        messages=messages,
        core=core,
    )
    if action in {"continue", "break"}:
        return (
            (
                action,
                client,
                cache_name,
                updated_rounds,
                assistant_text,
            ),
            updated_rounds,
        )
    return None, updated_rounds


def record_legacy_usage_telemetry(
    *,
    core: Any,
    provider: str,
    model: str,
    before: dict[str, Any],
    log_event_fn: Callable[..., Any] = log_event,
    reconcile_usage_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] = reconcile_usage,
) -> None:
    """Bridge provider usage retained on legacy core state into events."""
    after = getattr(core, "_last_responses_usage", None) if core is not None else None
    if not isinstance(after, dict) or not after or after == before:
        return
    usage_delta = reconcile_usage_fn(before, after)
    if not usage_delta:
        return
    log_event_fn(
        "llm.usage.reconciled",
        provider=provider,
        model=model,
        usage_source="legacy_core",
        **usage_delta,
    )


__all__ = [
    "append_legacy_reasoning_assistant",
    "consume_legacy_interrupt",
    "finish_legacy_without_tools",
    "record_legacy_usage_telemetry",
    "resolve_legacy_empty_round",
    "translate_and_append_legacy_assistant",
]
