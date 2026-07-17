from __future__ import annotations

import json

from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang
from .providers.provider_caps import RESPONSES_PROVIDERS

set_thread_lang(detect_lang())

from .translate import load_translate_config
from typing import Any

try:
    import certifi
except Exception:
    certifi = None

try:
    from google.genai import types as gemini_types
except ImportError:
    gemini_types = None

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    BadRequestError = None
    APIConnectionError = None

from .llm_message_helpers import (
    _build_call_messages,
    _init_gemini_cache,
    _maybe_auto_shrink_messages,
)
from .llm_helpers import (
    _call_maybe_thread,
    _env_default_on,
)
from .llm_round_helpers import (
    _translate_call_messages,
    _resolve_round_runtime_flags,
    _translate_assistant_if_needed,
    _call_gemini_round,
    _call_claude_round,
    _call_openai_azure_round,
    _call_deepseek_round,
    _call_zai_round,
    _call_novita_round,
)
from .llm_grok_round import _call_grok_round
from .providers.llm_deepseek import build_assistant_message_with_reasoning
from .llm_flow_helpers import (
    _append_assistant_message,
    _emit_final_answer_if_any,
    _handle_openai_empty_no_tool,
    _execute_tool_calls,
)
from . import core as _core_module
from .tools._genre_control_util import (
    _LOADED_SINGLE_TOOLS as _LOADED_SINGLE_TOOLS,
    disable_single_tool as _disable_single_tool,
    get_threshold as _get_threshold,
    bump_threshold as _bump_threshold,
    is_tool_pinned as _is_tool_pinned,
)
from .tools import TOOL_SPECS as _TOOL_SPECS
from .tools import _should_preload_lazy_specs
from .tools.context import get_callbacks
from .tools.skill_history import make_finish_skill_handler
from .tools.llm_tool_narrowing import _is_gpt54_tool_search_target


def _inject_stop_prompt(
    messages: list[dict[str, Any]],
    core: Any,
) -> None:
    """Inject a stop command as a user message and log it."""
    print("\n[INTERRUPT] " + _("Stopped by user. Sending stop command to LLM..."))
    user_msg = {"role": "user", "content": _("Stop")}
    messages.append(user_msg)
    core.log_message(user_msg)


# --- Tool usage tracking for auto-unload ---
_TOOL_LAST_ROUND: dict[str, int] = {}  # tool_name -> last round used
_TOOL_AUTO_UNLOAD_ROUNDS = int(
    env_get("UAGENT_AUTO_UNLOAD_ROUNDS", "10")
)  # unload after this many rounds without use
_TOTAL_ROUNDS: int = 0  # total rounds across all LLM calls, monotonically increasing

# Track repeated management-tool fingerprints to detect loops.
# Fingerprint is action + target (e.g. tool_load:file_grep), so loading
# several *different* tools in parallel is allowed. Only the same target
# repeated across rounds is treated as a loop (e.g. Grok reloading one tool).
_TOOL_CALL_FINGERPRINTS: dict[str, int] = {}
_MGMT_TOOLS = frozenset({"tool_catalog", "tool_load", "unload_tool"})
_MGMT_LOOP_THRESHOLD = 4


def _parse_mgmt_tool_args(args_raw: Any) -> Any:
    try:
        if isinstance(args_raw, str):
            return json.loads(args_raw) if args_raw.strip() else {}
        return args_raw if args_raw is not None else {}
    except Exception:
        return {"_raw": args_raw}


def _mgmt_tool_fingerprint(name: str, args: Any) -> str:
    """Build a loop-detection key for a management tool call.

    tool_load/unload_tool are keyed by the *target* tool name so that
    parallel loads of different tools do not share a counter.
    """
    if not isinstance(args, dict):
        return f"{name}:{args!r}"
    if name in ("tool_load", "unload_tool"):
        target = args.get("name") or args.get("tool") or ""
        return f"{name}:{target}"
    if name == "tool_catalog":
        return (
            f"tool_catalog:query={args.get('query', '')}:all={args.get('all', False)}"
        )
    return f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def _mgmt_tool_display(name: str, args: Any) -> str:
    if name in ("tool_load", "unload_tool") and isinstance(args, dict):
        target = args.get("name") or args.get("tool") or ""
        if target:
            return f"{name}({target})"
    return name


def check_mgmt_tool_loop(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect repeated same-target management tool calls.

    Returns (blocked, display_name, count). When record=False, only peeks
    without mutating counters (unused currently; kept for tests/callers).
    """
    if not tool_calls_list:
        return False, "", 0
    limit = _MGMT_LOOP_THRESHOLD if threshold is None else threshold

    round_counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for tc in tool_calls_list:
        fn = tc.get("function", {}) or {}
        name = fn.get("name", "") or ""
        if name not in _MGMT_TOOLS:
            continue
        args = _parse_mgmt_tool_args(fn.get("arguments", "{}"))
        fp = _mgmt_tool_fingerprint(name, args)
        round_counts[fp] = round_counts.get(fp, 0) + 1
        display[fp] = _mgmt_tool_display(name, args)

    if not round_counts:
        return False, "", 0

    blocked_name = ""
    blocked_count = 0
    for fp, n in round_counts.items():
        if record:
            total = _TOOL_CALL_FINGERPRINTS.get(fp, 0) + n
            _TOOL_CALL_FINGERPRINTS[fp] = total
        else:
            total = _TOOL_CALL_FINGERPRINTS.get(fp, 0) + n
        if total >= limit and total > blocked_count:
            blocked_name = display.get(fp, fp)
            blocked_count = total

    if blocked_count >= limit:
        return True, blocked_name, blocked_count
    return False, "", 0


# --- Round status constants (internal) ---
_RS_RETURN = "return"  # fatal error, caller must return
_RS_BREAK = "break"  # stop loop, exit normally
_RS_CONTINUE = "continue"  # skip postamble, continue loop
_RS_OK = "ok"  # execute postamble then continue loop


def _run_one_round(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    *,
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
    round_count: int,
    max_tool_rounds: int,
    empty_no_tool_rounds: int,
    empty_no_tool_max: int,
    cache_mgr: Any,
    gemini_cache_name: str | None,
    tool_result_cache: dict[str, str],
    use_tool_result_cache: bool,
    reuse_only_rounds: int,
    use_llm_thread: bool,
    judgment_mode: bool = False,
) -> tuple[str, Any, str | None, int, int, str]:
    """Run a single LLM round.

    Returns (status, client, gemini_cache_name, empty_no_tool_rounds, reuse_only_rounds, assistant_text).
    Caller dispatches on status:
      RS_RETURN   → return from run_llm_rounds
      RS_BREAK    → break while loop
      RS_CONTINUE → continue while loop (skip postamble)
      RS_OK       → execute postamble, then continue loop
    When judgment_mode=True, tool execution is suppressed and side effects
    (log, outfile, image open) are skipped. Only the assistant text is returned.
    """
    # ── Preamble ──────────────────────────────────────────────────

    # --- Interrupt check: per-round ---
    with _core_module.interrupt_lock:
        if _core_module.interrupt_requested:
            _core_module.interrupt_requested = False
            _inject_stop_prompt(messages, core)
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                "",
            )

    # Optional translation layer (off by default).
    tr_cfg = load_translate_config()
    if judgment_mode:
        tr_cfg = None  # judgment prompt is English; skip translate

    call_messages = _build_call_messages(
        provider=provider,
        messages=messages,
        core=core,
        depname=depname,
        gemini_cache_name=gemini_cache_name,
    )
    call_messages = _translate_call_messages(call_messages, tr_cfg)

    use_responses_api, stream_responses = _resolve_round_runtime_flags(
        tr_cfg=tr_cfg,
        core=core,
        provider=provider,
    )
    # Responses API is only supported on specific providers.
    if provider not in RESPONSES_PROVIDERS:
        use_responses_api = False

    def _call_maybe_thread_fn(fn: Any) -> Any:
        return _call_maybe_thread(fn, use_llm_thread=use_llm_thread)

    # Skip auto-shrink when using previous_response_id (server manages context)
    _using_prev_rid = bool(core.responses_state.get("previous_response_id"))
    if not judgment_mode and not _using_prev_rid:
        gemini_cache_name = _maybe_auto_shrink_messages(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
            core=core,
            cache_mgr=cache_mgr,
            gemini_cache_name=gemini_cache_name,
            call_maybe_thread_fn=_call_maybe_thread_fn,
            use_responses_api=use_responses_api,
        )

    if round_count > max_tool_rounds:
        print(
            _("[WARN] Tool rounds exceeded %(max)d; aborting.")
            % {"max": max_tool_rounds}
        )
        return (
            _RS_BREAK,
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            reuse_only_rounds,
            "",
        )

    send_tools_this_round = getattr(_core_module, "tools_enabled", True)
    if judgment_mode:
        send_tools_this_round = False
    max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
    retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
    retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

    tool_calls_list: list[dict[str, Any]] = []
    assistant_text: str = ""

    # ── Provider dispatch ─────────────────────────────────────────

    if provider in ("gemini", "vertexai"):
        (
            ok,
            client,
            assistant_text,
            tool_calls_list,
            gemini_content_dump,
        ) = _call_gemini_round(
            client=client,
            depname=depname,
            call_messages=call_messages,
            gemini_cache_name=gemini_cache_name,
            core=core,
            make_client_fn=make_client_fn,
            call_maybe_thread_fn=_call_maybe_thread_fn,
            max_retries_429=max_retries_429,
            retry_base=retry_base,
            retry_cap=retry_cap,
            stream_responses=stream_responses,
            send_tools=send_tools_this_round,
            provider=provider,
        )
        if not ok:
            return (
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        # --- Interrupt check (Gemini) ---
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    reuse_only_rounds,
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=use_responses_api,
            stream_responses=stream_responses,
        )

        _append_assistant_message(
            messages=messages,
            core=core,
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
            gemini_content_dump=gemini_content_dump,
            skip_log_when_web=True,
        )

        action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
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
                _RS_CONTINUE,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not (provider in ("gemini", "vertexai") and stream_responses):
                if not judgment_mode:
                    _emit_final_answer_if_any(
                        assistant_text=assistant_text,
                        use_responses_api=use_responses_api,
                        stream_responses=stream_responses,
                        append_result_to_outfile_fn=append_result_to_outfile_fn,
                        try_open_images_from_text_fn=try_open_images_from_text_fn,
                        core=core,
                        provider=provider,
                    )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        empty_no_tool_rounds = 0

    elif provider == "claude":
        ok, client, assistant_text, tool_calls_list = _call_claude_round(
            client=client,
            depname=depname,
            call_messages=call_messages,
            core=core,
            make_client_fn=make_client_fn,
            call_maybe_thread_fn=_call_maybe_thread_fn,
            max_retries_429=max_retries_429,
            retry_base=retry_base,
            retry_cap=retry_cap,
            send_tools=send_tools_this_round,
            provider=provider,
        )
        if not ok:
            return (
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        # --- Interrupt check ---
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    reuse_only_rounds,
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=use_responses_api,
            stream_responses=stream_responses,
        )

        _append_assistant_message(
            messages=messages,
            core=core,
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
        )

        action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
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
                _RS_CONTINUE,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not judgment_mode:
                _emit_final_answer_if_any(
                    assistant_text=assistant_text,
                    reasoning_content=locals().get("reasoning_content", ""),
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                    append_result_to_outfile_fn=append_result_to_outfile_fn,
                    try_open_images_from_text_fn=try_open_images_from_text_fn,
                    core=core,
                    provider=provider,
                )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        empty_no_tool_rounds = 0

    elif provider in ("deepseek", "mimo"):
        ok, client, assistant_text, reasoning_content, tool_calls_list = (
            _call_deepseek_round(
                client=client,
                depname=depname,
                call_messages=call_messages,
                core=core,
                make_client_fn=make_client_fn,
                call_maybe_thread_fn=_call_maybe_thread_fn,
                send_tools_this_round=send_tools_this_round,
                max_retries_429=max_retries_429,
                retry_base=retry_base,
                retry_cap=retry_cap,
                provider=provider,
            )
        )
        if not ok:
            return (
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        # --- Interrupt check ---
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    reuse_only_rounds,
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=False,
            stream_responses=False,
        )

        _ds_streaming = (
            env_get("UAGENT_STREAMING", "1") or ""
        ).strip().lower() not in ("0", "false", "no", "off")

        deepseek_msg = build_assistant_message_with_reasoning(
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
            reasoning_content=reasoning_content,
        )
        messages.append(deepseek_msg)
        if not (bool(getattr(core, "_is_web", False)) and _ds_streaming):
            if not judgment_mode:
                core.log_message(deepseek_msg)

        action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
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
                _RS_CONTINUE,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not judgment_mode:
                _emit_final_answer_if_any(
                    assistant_text=assistant_text,
                    use_responses_api=False,
                    stream_responses=False,
                    append_result_to_outfile_fn=append_result_to_outfile_fn,
                    try_open_images_from_text_fn=try_open_images_from_text_fn,
                    reasoning_content=reasoning_content,
                    skip_print=_ds_streaming,
                    core=core,
                    provider=provider,
                )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        empty_no_tool_rounds = 0

    elif provider == "zai":
        ok, client, assistant_text, reasoning_content, tool_calls_list = (
            _call_zai_round(
                client=client,
                depname=depname,
                call_messages=call_messages,
                core=core,
                make_client_fn=make_client_fn,
                call_maybe_thread_fn=_call_maybe_thread_fn,
                send_tools_this_round=send_tools_this_round,
                max_retries_429=max_retries_429,
                retry_base=retry_base,
                retry_cap=retry_cap,
            )
        )
        if not ok:
            return (
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        # --- Interrupt check ---
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    reuse_only_rounds,
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=False,
            stream_responses=False,
        )

        _ds_streaming = (
            env_get("UAGENT_STREAMING", "1") or ""
        ).strip().lower() not in ("0", "false", "no", "off")

        deepseek_msg = build_assistant_message_with_reasoning(
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
            reasoning_content=reasoning_content,
        )
        messages.append(deepseek_msg)
        if not (bool(getattr(core, "_is_web", False)) and _ds_streaming):
            if not judgment_mode:
                core.log_message(deepseek_msg)

        action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
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
                _RS_CONTINUE,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not judgment_mode:
                _emit_final_answer_if_any(
                    assistant_text=assistant_text,
                    use_responses_api=False,
                    stream_responses=False,
                    append_result_to_outfile_fn=append_result_to_outfile_fn,
                    try_open_images_from_text_fn=try_open_images_from_text_fn,
                    reasoning_content=reasoning_content,
                    skip_print=_ds_streaming,
                    core=core,
                    provider=provider,
                )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        empty_no_tool_rounds = 0

    elif provider == "novita":
        ok, client, assistant_text, reasoning_content, tool_calls_list = (
            _call_novita_round(
                client=client,
                depname=depname,
                call_messages=call_messages,
                core=core,
                make_client_fn=make_client_fn,
                call_maybe_thread_fn=_call_maybe_thread_fn,
                send_tools_this_round=send_tools_this_round,
                max_retries_429=max_retries_429,
                retry_base=retry_base,
                retry_cap=retry_cap,
            )
        )
        if not ok:
            return (
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        # --- Interrupt check ---
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    reuse_only_rounds,
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=False,
            stream_responses=False,
        )

        _ds_streaming = (
            env_get("UAGENT_STREAMING", "1") or ""
        ).strip().lower() not in ("0", "false", "no", "off")

        deepseek_msg = build_assistant_message_with_reasoning(
            assistant_text=assistant_text,
            tool_calls_list=tool_calls_list,
            reasoning_content=reasoning_content,
        )
        messages.append(deepseek_msg)
        if not (bool(getattr(core, "_is_web", False)) and _ds_streaming):
            if not judgment_mode:
                core.log_message(deepseek_msg)

        action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
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
                _RS_CONTINUE,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not judgment_mode:
                _emit_final_answer_if_any(
                    assistant_text=assistant_text,
                    use_responses_api=False,
                    stream_responses=False,
                    append_result_to_outfile_fn=append_result_to_outfile_fn,
                    try_open_images_from_text_fn=try_open_images_from_text_fn,
                    reasoning_content=reasoning_content,
                    skip_print=_ds_streaming,
                    core=core,
                    provider=provider,
                )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        empty_no_tool_rounds = 0

    else:  # OpenAI / Azure / Grok
        _is_xai_grpc = False
        if provider == "grok":
            # Use xai_sdk (gRPC) only when client is XAIClient; otherwise OpenAI SDK
            try:
                from xai_sdk import Client as _XAIClient

                _is_xai_grpc = isinstance(client, _XAIClient)
            except Exception:
                _is_xai_grpc = False

            if _is_xai_grpc:
                ok, client, assistant_text, tool_calls_list = _call_grok_round(
                    provider=provider,
                    client=client,
                    depname=depname,
                    call_messages=call_messages,
                    core=core,
                    make_client_fn=make_client_fn,
                    call_maybe_thread_fn=_call_maybe_thread_fn,
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                    send_tools_this_round=send_tools_this_round,
                    max_retries_429=max_retries_429,
                    retry_base=retry_base,
                    retry_cap=retry_cap,
                    messages=messages,
                    responses_state=core.responses_state,
                )
                reasoning_content = (
                    ""  # Grok does not return reasoning_content separately
                )
            else:
                ok, client, assistant_text, reasoning_content, tool_calls_list = (
                    _call_openai_azure_round(
                        provider=provider,
                        client=client,
                        depname=depname,
                        call_messages=call_messages,
                        core=core,
                        make_client_fn=make_client_fn,
                        call_maybe_thread_fn=_call_maybe_thread_fn,
                        use_responses_api=use_responses_api,
                        stream_responses=stream_responses,
                        send_tools_this_round=send_tools_this_round,
                        max_retries_429=max_retries_429,
                        retry_base=retry_base,
                        retry_cap=retry_cap,
                        messages=messages,
                        responses_state=core.responses_state,
                    )
                )
        else:
            ok, client, assistant_text, reasoning_content, tool_calls_list = (
                _call_openai_azure_round(
                    provider=provider,
                    client=client,
                    depname=depname,
                    call_messages=call_messages,
                    core=core,
                    make_client_fn=make_client_fn,
                    call_maybe_thread_fn=_call_maybe_thread_fn,
                    use_responses_api=use_responses_api,
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
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        # Preserve native Responses output items (including reasoning items)
        # for full-history fallback and tool-call continuation.
        responses_output_items = getattr(core, "_last_responses_output_items", None)

        # --- Interrupt check (OpenAI/Azure) ---
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    reuse_only_rounds,
                    assistant_text,
                )

        if reasoning_content:
            deepseek_msg = build_assistant_message_with_reasoning(
                assistant_text=assistant_text,
                tool_calls_list=tool_calls_list,
                reasoning_content=reasoning_content,
            )
            if isinstance(responses_output_items, list) and responses_output_items:
                deepseek_msg["_responses_output_items"] = responses_output_items
            messages.append(deepseek_msg)
            if not judgment_mode:
                core.log_message(deepseek_msg)
        else:
            _append_assistant_message(
                messages=messages,
                core=core,
                assistant_text=assistant_text,
                tool_calls_list=tool_calls_list,
                responses_output_items=responses_output_items,
            )

        action, empty_no_tool_rounds = _handle_openai_empty_no_tool(
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
                _RS_CONTINUE,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not judgment_mode:
                # Grok xai_sdk streaming already printed deltas in parse_xai_stream().
                _emit_final_answer_if_any(
                    assistant_text=assistant_text,
                    reasoning_content=locals().get("reasoning_content", ""),
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                    append_result_to_outfile_fn=append_result_to_outfile_fn,
                    try_open_images_from_text_fn=try_open_images_from_text_fn,
                    skip_print=bool(
                        provider == "grok" and stream_responses and _is_xai_grpc
                    ),
                    core=core,
                    provider=provider,
                )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

        empty_no_tool_rounds = 0

    # ── Postamble: tool execution ────────────────────────────────

    if judgment_mode:
        return (
            _RS_OK,
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            reuse_only_rounds,
            assistant_text,
        )

    executed_new_tool = _execute_tool_calls(
        tool_calls_list=tool_calls_list,
        messages=messages,
        core=core,
        cache_mgr=cache_mgr,
        tool_result_cache=tool_result_cache,
        use_tool_result_cache=use_tool_result_cache,
    )

    if any(
        isinstance(tc, dict)
        and (tc.get("function") or {}).get("name") == "generate_image"
        for tc in tool_calls_list
    ):
        return (
            _RS_BREAK,
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            reuse_only_rounds,
            assistant_text,
        )

    # Re-check before the next LLM call.
    # Skip auto-shrink when using previous_response_id (server manages context)
    _using_prev_rid = bool(core.responses_state.get("previous_response_id"))
    if not judgment_mode and not _using_prev_rid:
        gemini_cache_name = _maybe_auto_shrink_messages(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
            core=core,
            cache_mgr=cache_mgr,
            gemini_cache_name=gemini_cache_name,
            call_maybe_thread_fn=_call_maybe_thread_fn,
            use_responses_api=use_responses_api,
        )

    core.set_status(True, "LLM")

    if executed_new_tool:
        reuse_only_rounds = 0
    else:
        reuse_only_rounds += 1
        if reuse_only_rounds >= 3:
            print(
                "[WARN] The same tool result was reused for 3 consecutive rounds, so "
                "processing was stopped to prevent a loop."
            )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

    # Detect repeated same-target management tool calls.
    # Parallel tool_load of different tools is allowed; only the same target
    # (e.g. tool_load(file_grep) x4) across rounds is treated as a loop.
    if tool_calls_list and not judgment_mode:
        blocked, blocked_name, blocked_count = check_mgmt_tool_loop(tool_calls_list)
        if blocked:
            print(
                "[WARN] Management tool call '%(name)s' repeated %(n)d times; aborting to prevent loop."
                % {"name": blocked_name, "n": blocked_count}
            )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                assistant_text,
            )

    return (
        _RS_OK,
        client,
        gemini_cache_name,
        empty_no_tool_rounds,
        reuse_only_rounds,
        assistant_text,
    )


def run_llm_rounds(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    *,
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
    judgment_mode: bool = False,
    judgment_messages: list[dict[str, Any]] | None = None,
) -> str | None:
    global _TOTAL_ROUNDS, _TOOL_LAST_ROUND, _TOOL_AUTO_UNLOAD_ROUNDS, _TOOL_SPECS
    # Judgment mode: swap messages so all side effects go to judgment_messages
    if judgment_mode:
        if not judgment_messages:
            return ""
        messages = judgment_messages

    # Provider/model must be set before first LLM round (for save to file)
    if not judgment_mode:
        core.responses_state["provider"] = provider
        core.responses_state["model"] = depname

    max_tool_rounds = 200
    round_count = 0

    empty_no_tool_rounds = 0

    # Some OpenAI-compatible local providers may return empty assistant messages after tool calls.
    # Tolerate a few consecutive empty/no-tool rounds, then abort with an explicit warning.
    try:
        empty_no_tool_max = int(env_get("UAGENT_EMPTY_NO_TOOL_MAX", "2"))
    except Exception:
        empty_no_tool_max = 2
    if empty_no_tool_max < 0:
        empty_no_tool_max = 2

    cb = get_callbacks()
    prev_finish_skill = cb.finish_skill
    if not judgment_mode:
        cb.finish_skill = make_finish_skill_handler(messages, core)

    core.set_status(True, "LLM")

    use_llm_thread = _env_default_on("UAGENT_LLM_IN_THREAD")

    tool_result_cache: dict[str, str] = {}
    use_tool_result_cache = env_get(
        "UAGENT_TOOL_RESULT_CACHE", "0"
    ).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    reuse_only_rounds = 0

    # Reset management tool call loop detection for this session
    _TOOL_CALL_FINGERPRINTS.clear()

    if judgment_mode:
        cache_mgr, gemini_cache_name = None, None
    else:
        cache_mgr, gemini_cache_name = _init_gemini_cache(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
        )

    # Clear any stale interrupt flag from a previous session
    with _core_module.interrupt_lock:
        _core_module.interrupt_requested = False

    final_text: str | None = None

    try:
        while True:
            round_count += 1
            _TOTAL_ROUNDS += 1

            (
                round_status,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                reuse_only_rounds,
                _round_text,
            ) = _run_one_round(
                provider=provider,
                client=client,
                depname=depname,
                messages=messages,
                core=core,
                make_client_fn=make_client_fn,
                append_result_to_outfile_fn=append_result_to_outfile_fn,
                try_open_images_from_text_fn=try_open_images_from_text_fn,
                round_count=round_count,
                max_tool_rounds=max_tool_rounds,
                empty_no_tool_rounds=empty_no_tool_rounds,
                empty_no_tool_max=empty_no_tool_max,
                cache_mgr=cache_mgr,
                gemini_cache_name=gemini_cache_name,
                tool_result_cache=tool_result_cache,
                use_tool_result_cache=use_tool_result_cache,
                reuse_only_rounds=reuse_only_rounds,
                use_llm_thread=use_llm_thread,
                judgment_mode=judgment_mode,
            )

            if round_status == _RS_RETURN:
                if judgment_mode:
                    final_text = _round_text or ""
                break
            if round_status == _RS_BREAK:
                if judgment_mode:
                    final_text = _round_text or ""
                break
            # _RS_CONTINUE and _RS_OK: continue loop naturally

            # --- Auto-unload stale tools ---
            # Search backwards through messages to find the LAST assistant message with tool_calls
            # (messages[-1] may be a tool result after _execute_tool_calls, so we can't rely on it alone)
            _found_tool_names: set[str] = set()
            for _m in reversed(messages):
                if not isinstance(_m, dict):
                    continue
                if _m.get("role") != "assistant":
                    continue
                _tcs = _m.get("tool_calls")
                if not isinstance(_tcs, list) or not _tcs:
                    continue
                for _tc in _tcs:
                    _tname = _tc.get("function", {}).get("name", "")
                    if _tname:
                        _found_tool_names.add(_tname)
                break  # only the last assistant message matters
            for _tname in _found_tool_names:
                _TOOL_LAST_ROUND[_tname] = _TOTAL_ROUNDS
                _bump_threshold(_tname)

            # Skip auto-unload when server manages tool selection
            # (native GPT-5.4 tool_search mode only)
            if not (
                _should_preload_lazy_specs()
                or _is_gpt54_tool_search_target(
                    provider=provider,
                    depname=depname,
                    use_responses_api=True,
                )
            ):
                for spec in list(_TOOL_SPECS):
                    func_info = spec.get("function", {})
                    tname = func_info.get("name", "")
                    if not tname:
                        continue
                    # Skip core/management tools
                    if tname in ("tool_catalog", "tool_load", "unload_tool"):
                        continue
                    # Only auto-unload tools explicitly loaded by user (:tools load or tool_load)
                    if tname not in _LOADED_SINGLE_TOOLS:
                        continue
                    # Skip tools pinned against auto-unload (e.g. active browser sessions)
                    if _is_tool_pinned(tname):
                        continue
                    threshold = _get_threshold(tname)
                    if threshold <= 0:
                        continue
                    last = _TOOL_LAST_ROUND.get(tname)
                    if last is None:
                        # Never used: unload after threshold rounds
                        if _TOTAL_ROUNDS >= threshold:
                            _disable_single_tool(tname)
                    elif (_TOTAL_ROUNDS - last) >= threshold:
                        _TOOL_LAST_ROUND.pop(tname, None)
                        _disable_single_tool(tname)
            # --- end auto-unload ---

            # Judgment mode: one round only
            if judgment_mode:
                break

    finally:
        cb.finish_skill = prev_finish_skill
        # セッション中（プログラム終了まで）キャッシュを保持するため、ここでは削除しない。
        # クリーンアップは cli.py のメインループを抜けた際の finally で行う。
        core.set_status(False, "")

    if judgment_mode:
        return final_text or ""
    return None
