"""Gemini/Vertex compatibility adapter extracted from legacy round helpers."""

from __future__ import annotations

from typing import Any

from ..i18n import _
from ..llm_helpers import LLMWaitInterrupted, _maybe_print_certifi_where
from ..llm_message_helpers import _build_call_messages
from ..providers.llm_gemini import gemini_chat_with_tools
from .legacy_context_recovery import rollback_largest_recent_history
from .llm_error_classifier import is_context_overflow_error
from .retry_coordinator import RoundRetryCoordinator
from .stream_host import build_stream_callbacks


def _call_gemini_round(
    *,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    history_messages: list[dict[str, Any]] | None = None,
    gemini_cache_name: Any,
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    stream_responses: bool,
    force_thinking_level: str | None = None,
    send_tools: bool = True,
    provider: str = "gemini",
    gemini_chat_fn: Any = None,
    retry_coordinator: RoundRetryCoordinator | None = None,
) -> Any:
    retry_coordinator = retry_coordinator or RoundRetryCoordinator(max_retries_429)
    retry_coordinator.expose_budget(core)
    attempt_429 = 0
    gemini_content_dump: dict[str, Any] = {}
    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []
    turn_repair_attempted = False
    turn_hard_reset_attempted = False

    while True:
        try:
            assistant_text, tool_calls_list, gemini_content_dump = call_maybe_thread_fn(
                lambda: (gemini_chat_fn or gemini_chat_with_tools)(
                    client,
                    depname,
                    call_messages,
                    cached_content=gemini_cache_name,
                    stream=stream_responses,
                    core=core,
                    force_thinking_level=force_thinking_level,
                    send_tools=send_tools,
                    provider=provider,
                    callbacks=build_stream_callbacks(
                        print_delta_fn=(
                            None
                            if bool(getattr(core, "_is_web", False))
                            else (
                                getattr(core, "print_stream_delta", None)
                                or (
                                    lambda s: (
                                        print(s, end="", flush=True) if s else None
                                    )
                                )
                            )
                        ),
                        core=core,
                    ),
                )
            )
            break
        except LLMWaitInterrupted:
            return True, client, "", [], {}
        except Exception as e:
            error_text = str(e)
            if (
                not turn_repair_attempted
                and "requests ending with a model turn" in error_text.lower()
            ):
                turn_repair_attempted = True
                if history_messages:
                    call_messages[:] = _build_call_messages(
                        provider=provider,
                        messages=history_messages,
                        core=core,
                        depname=depname,
                        gemini_cache_name=None,
                    )
                call_messages.append({"role": "user", "content": "Continue."})
                gemini_cache_name = None
                try:
                    core._gemini_cache_needs_refresh = True
                except Exception:
                    pass
                continue
            if (
                not turn_hard_reset_attempted
                and "requests ending with a model turn" in error_text.lower()
            ):
                turn_hard_reset_attempted = True
                safe_messages: list[dict[str, Any]] = []
                source_messages = history_messages or call_messages
                for message in source_messages:
                    if not isinstance(message, dict):
                        continue
                    if message.get("role") == "system":
                        safe_messages.append(dict(message))
                latest_user = next(
                    (
                        dict(message)
                        for message in reversed(source_messages)
                        if isinstance(message, dict)
                        and message.get("role") == "user"
                        and str(message.get("content") or "").strip()
                    ),
                    {"role": "user", "content": "Continue."},
                )
                safe_messages.append(latest_user)
                call_messages[:] = safe_messages
                call_messages.append({"role": "user", "content": "Continue."})
                gemini_cache_name = None
                try:
                    core._gemini_cache_needs_refresh = True
                except Exception:
                    pass
                continue
            if is_context_overflow_error(e) and history_messages is not None:
                rollback = rollback_largest_recent_history(history_messages)
                if rollback is not None:
                    print(
                        _(
                            "context.rollback_user_notice",
                            default=(
                                "[INFO] Context limit exceeded; rolled back from the "
                                "largest message in the last %(lookback)d messages "
                                "(%(removed)d message(s) removed)."
                            ),
                            lookback=10,
                            removed=rollback["removed"],
                        ),
                        flush=True,
                    )
                    return False, client, "", [], {}
            attempt_429, new_client, action = retry_coordinator.rate_limit_step(
                exception=e,
                provider=provider,
                model=depname,
                attempt=attempt_429,
                max_retries=max_retries_429,
                base=retry_base,
                cap=retry_cap,
                recreate_client_fn=(lambda: make_client_fn(core)[1]),
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            if action == "give_up":
                print(
                    "[Claude Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(str(e))
                return False, client, "", [], {}
            msg = str(e)
            if force_thinking_level is None and (
                "Thinking level MINIMAL is not supported for this model" in msg
                or "thinking level minimal is not supported for this model"
                in msg.lower()
            ):
                try:
                    from ..util_tools import set_reasoning_mode

                    set_reasoning_mode("medium")
                except Exception:
                    pass
                force_thinking_level = "medium"
                try:
                    core.set_status(True, "LLM:medium")
                except Exception:
                    pass
                continue
            print(_("[Gemini Error] An error occurred while generating a response."))
            _maybe_print_certifi_where(e)
            print(str(e))
            return False, client, "", [], {}

    return True, client, assistant_text, tool_calls_list, gemini_content_dump


__all__ = ["_call_gemini_round"]
