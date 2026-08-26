from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang
from .llmcapa_util import provider_allows_responses_api

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
    LLMWaitInterrupted,
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
    _call_together_round,
    _call_vercel_round,
)
from .llm_grok_round import _call_grok_round
from .providers.llm_deepseek import build_assistant_message_with_reasoning
from .llm_flow_helpers import (
    _append_assistant_message,
    _emit_final_answer_if_any,
    _handle_openai_empty_no_tool,
    _execute_tool_calls,
    _resolve_empty_no_tool_max,
    _should_keep_assistant_message,
    _consume_empty_no_tool_recovery,
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
from .tools.llm_tool_narrowing import (
    _is_gpt54_tool_search_target,
    _select_tool_specs_legacy as _select_tool_specs_for_gpt54,  # noqa: F401  (re-exported for tests)
)


def _inject_stop_prompt(
    messages: list[dict[str, Any]],
    core: Any,
) -> None:
    """Inject a stop command as a user message and log it."""
    # Cancel the server-side Response first when a streaming response ID is
    # available. The existing local interruption path remains the fallback.
    try:
        from .providers.responses_manager import cancel_active_response

        cancel_active_response(core)
    except Exception:
        pass

    # Interrupt leaves Responses API chains incomplete (especially mid-tool).
    # Drop previous_response_id so the next turn does not reuse a stale rid.
    try:
        clear_fn = getattr(_core_module, "clear_responses_continuation", None)
        if callable(clear_fn):
            clear_fn()
        else:
            state = getattr(core, "responses_state", None)
            if isinstance(state, dict):
                state.pop("previous_response_id", None)
                state.pop("_stale_rid_occurred", None)
    except Exception:
        pass
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
# Rounds that actually executed the tool postamble (RS_OK). Empty/no-tool
# continue rounds must not age auto-unload counters.
_PRODUCTIVE_ROUNDS: int = 0


def _productive_age(stamp: object, *, now: int | None = None) -> int | None:
    """Return age on the productive-round timeline.

    Stamps from the old TOTAL_ROUNDS timeline can be larger than the current
    productive clock; treat those as already expired by returning a huge age.
    """
    try:
        s = int(stamp)  # type: ignore[arg-type]
    except Exception:
        return None
    cur = _PRODUCTIVE_ROUNDS if now is None else int(now)
    if s > cur:
        return 10**9
    return cur - s


# Track repeated management-tool fingerprints to detect loops.
# Fingerprint is action + target (e.g. tool_load:file_grep), so loading
# several *different* tools in parallel is allowed. Only the same target
# repeated across rounds is treated as a loop (e.g. Grok reloading one tool).
# unload_tool(target) clears that target's tool_load counter so a later
# intentional reload is not counted as a continuation of the prior streak.
_TOOL_CALL_FINGERPRINTS: dict[str, int] = {}
# Count freshly executed tool calls across consecutive rounds, independently
# of tool name and arguments. This is a second, broader runaway guard.
_CONSECUTIVE_TOOL_CALL_COUNT = 0
_MGMT_TOOLS = frozenset({"tool_catalog", "tool_load", "unload_tool"})
_MGMT_LOOP_THRESHOLD = 4
# Same-args general tool loops (e.g. get_current_location xN) are also blocked.
# Keep this close to the management threshold so runaway tool spam stops early.
_GENERAL_TOOL_LOOP_THRESHOLD = 4
# Tools that may legitimately be called repeatedly with identical args in one
# session (polling/monitors). These stay on the management-only detector.
_GENERAL_LOOP_EXEMPT_TOOLS = frozenset(
    {
        "human_ask",
        "finish_skill",
        "tool_catalog",
        "tool_load",
        "unload_tool",
    }
)


def _parse_mgmt_tool_args(args_raw: Any) -> Any:
    try:
        if isinstance(args_raw, str):
            return json.loads(args_raw) if args_raw.strip() else {}
        return args_raw if args_raw is not None else {}
    except Exception:
        return {"_raw": args_raw}


def _mgmt_tool_target(name: str, args: Any) -> str:
    """Return the target tool name for load/unload, else empty."""
    if name not in ("tool_load", "unload_tool") or not isinstance(args, dict):
        return ""
    return str(args.get("name") or args.get("tool") or "")


def _mgmt_tool_fingerprint(name: str, args: Any) -> str:
    """Build a loop-detection key for a management tool call.

    tool_load/unload_tool are keyed by the *target* tool name so that
    parallel loads of different tools do not share a counter.
    """
    if not isinstance(args, dict):
        return f"{name}:{args!r}"
    if name in ("tool_load", "unload_tool"):
        target = _mgmt_tool_target(name, args)
        return f"{name}:{target}"
    if name == "tool_catalog":
        return (
            f"tool_catalog:query={args.get('query', '')}:all={args.get('all', False)}"
        )
    return f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def _general_tool_fingerprint(name: str, args: Any) -> str:
    """Build a loop-detection key for a general (non-management) tool call."""
    if not isinstance(args, dict):
        return f"tool:{name}:{args!r}"
    try:
        payload = json.dumps(args, sort_keys=True, ensure_ascii=False)
    except Exception:
        payload = repr(args)
    return f"tool:{name}:{payload}"


def _mgmt_tool_display(name: str, args: Any) -> str:
    if name in ("tool_load", "unload_tool") and isinstance(args, dict):
        target = _mgmt_tool_target(name, args)
        if target:
            return f"{name}({target})"
    return name


def clear_mgmt_load_streak(target: str) -> None:
    """Clear tool_load loop counters for *target* (auto or explicit unload).

    Auto-unload calls disable_single_tool directly and never emits unload_tool,
    so both paths must clear via this helper or the prior load streak would
    still count toward the loop threshold on the next tool_load.
    """
    name = str(target or "").strip()
    if not name:
        return
    _TOOL_CALL_FINGERPRINTS.pop(f"tool_load:{name}", None)
    # drop any stale unload fingerprint from older builds
    _TOOL_CALL_FINGERPRINTS.pop(f"unload_tool:{name}", None)


def clear_general_tool_loop_streaks() -> None:
    """Clear general-tool loop counters.

    tool_catalog is a re-planning boundary: once the model re-searches tools,
    previous same-args streaks (e.g. get_current_location x3) should not carry over.
    Management fingerprints (tool_load:/tool_catalog:...) are kept.
    """
    for key in list(_TOOL_CALL_FINGERPRINTS.keys()):
        if str(key).startswith("tool:"):
            _TOOL_CALL_FINGERPRINTS.pop(key, None)


def clear_consecutive_tool_call_streak() -> None:
    """Clear the cross-tool consecutive-call counter."""
    global _CONSECUTIVE_TOOL_CALL_COUNT
    _CONSECUTIVE_TOOL_CALL_COUNT = 0


def check_consecutive_tool_calls(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect too many consecutive freshly executed tool calls.

    This deliberately ignores both tool names and arguments. Only a round
    with no fresh tool calls resets the streak.
    """
    global _CONSECUTIVE_TOOL_CALL_COUNT
    raw_limit = env_get("UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT", "32")
    try:
        default_limit = max(1, int(raw_limit))
    except (TypeError, ValueError):
        default_limit = 32
    limit = default_limit if threshold is None else max(1, int(threshold))
    if not tool_calls_list:
        if record:
            _CONSECUTIVE_TOOL_CALL_COUNT = 0
        return False, "", 0
    total = _CONSECUTIVE_TOOL_CALL_COUNT + len(tool_calls_list)
    if record:
        _CONSECUTIVE_TOOL_CALL_COUNT = total
    return total >= limit, "consecutive tool calls", total


def _tool_calls_include_name(tool_calls_list: list[dict[str, Any]], name: str) -> bool:
    target = str(name or "").strip()
    if not target:
        return False
    for tc in tool_calls_list or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        if not isinstance(fn, dict):
            continue
        if str(fn.get("name") or "").strip() == target:
            return True
    return False


def check_mgmt_tool_loop(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect repeated same-target management tool calls.

    Returns (blocked, display_name, count). When record=False, only peeks
    without mutating counters (unused currently; kept for tests/callers).

    unload_tool(target) resets the tool_load counter for that target so a
    deliberate unload→reload cycle does not trip the loop detector.
    """
    if not tool_calls_list:
        return False, "", 0
    limit = _MGMT_LOOP_THRESHOLD if threshold is None else threshold

    round_counts: dict[str, int] = {}
    display: dict[str, str] = {}
    unload_targets: set[str] = set()
    for tc in tool_calls_list:
        fn = tc.get("function", {}) or {}
        name = fn.get("name", "") or ""
        if name not in _MGMT_TOOLS:
            continue
        args = _parse_mgmt_tool_args(fn.get("arguments", "{}"))
        if name == "unload_tool":
            target = _mgmt_tool_target(name, args)
            if target:
                unload_targets.add(target)
            # unload itself is not loop-counted; it only resets load streaks
            continue
        fp = _mgmt_tool_fingerprint(name, args)
        round_counts[fp] = round_counts.get(fp, 0) + 1
        display[fp] = _mgmt_tool_display(name, args)

    if record and unload_targets:
        for target in unload_targets:
            clear_mgmt_load_streak(target)

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


def check_general_tool_loop(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect repeated same-args general tool calls across rounds.

    Returns (blocked, display_name, count). Management tools are handled by
    check_mgmt_tool_loop and are ignored here.

    Counters are per fingerprint (tool + args). When a different fingerprint
    appears, other general-tool counters are reset so only the active streak
    is tracked.
    """
    if not tool_calls_list:
        return False, "", 0
    limit = _GENERAL_TOOL_LOOP_THRESHOLD if threshold is None else threshold

    round_counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for tc in tool_calls_list:
        fn = tc.get("function", {}) or {}
        name = str(fn.get("name", "") or "")
        if not name or name in _GENERAL_LOOP_EXEMPT_TOOLS:
            continue
        args = _parse_mgmt_tool_args(fn.get("arguments", "{}"))
        fp = _general_tool_fingerprint(name, args)
        round_counts[fp] = round_counts.get(fp, 0) + 1
        display[fp] = name

    if not round_counts:
        return False, "", 0

    if record:
        # Different fingerprint => previous general-tool streaks are stale.
        for key in list(_TOOL_CALL_FINGERPRINTS.keys()):
            if str(key).startswith("tool:") and key not in round_counts:
                _TOOL_CALL_FINGERPRINTS.pop(key, None)

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
    use_llm_thread: bool,
    judgment_mode: bool = False,
) -> tuple[str, Any, str | None, int, str]:
    """Run a single LLM round.

    Returns (status, client, gemini_cache_name, empty_no_tool_rounds, assistant_text).
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
        depname=depname,
    )
    # Responses API is only supported when provider/model allow it.
    if use_responses_api and not provider_allows_responses_api(provider, depname):
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
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=use_responses_api,
            stream_responses=stream_responses,
        )

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
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
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=use_responses_api,
            stream_responses=stream_responses,
        )

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
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
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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
                assistant_text,
            )

        empty_no_tool_rounds = 0

    elif provider in ("deepseek", "mimo"):
        if use_responses_api and provider == "deepseek":
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
                    assistant_text,
                )

        assistant_text = _translate_assistant_if_needed(
            assistant_text=assistant_text,
            tr_cfg=tr_cfg,
            use_responses_api=use_responses_api,
            stream_responses=stream_responses,
        )

        _ds_streaming = (
            env_get("UAGENT_STREAMING", "1") or ""
        ).strip().lower() not in ("0", "false", "no", "off")
        _deepseek_output_already_printed = (use_responses_api and stream_responses) or (
            not use_responses_api and _ds_streaming
        )

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
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
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                assistant_text,
            )

        if not tool_calls_list:
            if not judgment_mode:
                _emit_final_answer_if_any(
                    assistant_text=assistant_text,
                    use_responses_api=use_responses_api,
                    stream_responses=stream_responses,
                    append_result_to_outfile_fn=append_result_to_outfile_fn,
                    try_open_images_from_text_fn=try_open_images_from_text_fn,
                    reasoning_content=reasoning_content,
                    skip_print=_deepseek_output_already_printed,
                    core=core,
                    provider=provider,
                )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
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
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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
                assistant_text,
            )

        empty_no_tool_rounds = 0

    elif provider == "vercel":
        ok, client, assistant_text, reasoning_content, tool_calls_list = (
            _call_vercel_round(
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

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
            deepseek_msg = build_assistant_message_with_reasoning(
                assistant_text=assistant_text,
                reasoning_content=reasoning_content,
                tool_calls_list=tool_calls_list,
            )
            messages.append(deepseek_msg)
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
            assistant_text,
        )

        empty_no_tool_rounds = 0

    elif provider == "together":
        ok, client, assistant_text, reasoning_content, tool_calls_list = (
            _call_together_round(
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

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
            deepseek_msg = build_assistant_message_with_reasoning(
                assistant_text=assistant_text,
                reasoning_content=reasoning_content,
                tool_calls_list=tool_calls_list,
            )
            messages.append(deepseek_msg)
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

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
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
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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
                assistant_text,
            )

        # Preserve native Responses output items (including reasoning items)
        # for full-history fallback and tool-call continuation.
        responses_output_items = getattr(core, "_last_responses_output_items", None)

        # --- Interrupt check (OpenAI/Azure) ---
        confirmation_just_completed = bool(
            getattr(core, "computer_use_confirmation_just_completed", False)
        )
        if confirmation_just_completed:
            core.computer_use_confirmation_just_completed = False
        with _core_module.interrupt_lock:
            if _core_module.interrupt_requested and not confirmation_just_completed:
                _core_module.interrupt_requested = False
                _inject_stop_prompt(messages, core)
                return (
                    _RS_BREAK,
                    client,
                    gemini_cache_name,
                    empty_no_tool_rounds,
                    assistant_text,
                )

        if _should_keep_assistant_message(assistant_text, tool_calls_list):
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
                assistant_text,
            )
        if action == "break":
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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
            assistant_text,
        )

    executed_new_tool, fresh_tool_calls = _execute_tool_calls(
        tool_calls_list=tool_calls_list,
        messages=messages,
        core=core,
        cache_mgr=cache_mgr,
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

    # Detect repeated same-target management tool calls.
    # Parallel tool_load of different tools is allowed; only the same target
    # (e.g. tool_load(file_grep) x4) across rounds is treated as a loop.
    # unload_tool(target) clears that target's load streak first.
    if tool_calls_list and not judgment_mode:
        # Re-planning via tool_catalog starts a fresh general-tool streak.
        if _tool_calls_include_name(tool_calls_list, "tool_catalog"):
            clear_general_tool_loop_streaks()

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
                assistant_text,
            )
        # Count all freshly executed calls, regardless of tool name or args.
        # Cache-reuse replies ("Already called...") must not inflate the guard.
        blocked, blocked_name, blocked_count = check_consecutive_tool_calls(
            fresh_tool_calls
        )
        if blocked:
            print(
                "[WARN] %(n)d consecutive tool calls; aborting to prevent runaway execution."
                % {"n": blocked_count}
            )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                assistant_text,
            )
        # The narrower detector catches repeated calls with identical args.
        blocked, blocked_name, blocked_count = check_general_tool_loop(fresh_tool_calls)
        if blocked:
            print(
                "[WARN] Tool call '%(name)s' repeated %(n)d times with the same "
                "arguments; aborting to prevent loop."
                % {"name": blocked_name, "n": blocked_count}
            )
            return (
                _RS_BREAK,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                assistant_text,
            )

    return (
        _RS_OK,
        client,
        gemini_cache_name,
        empty_no_tool_rounds,
        assistant_text,
    )


def _observed_llm_rounds(fn: Any) -> Any:
    """Add structured lifecycle events around one LLM execution."""
    from functools import wraps
    import time
    from .runtime.logging_setup import log_event

    @wraps(fn)
    def wrapped(
        provider: str,
        client: Any,
        depname: str,
        messages: list[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> str | None:
        started = time.perf_counter()
        log_event("llm.started", provider=provider, model=depname, status="started")
        try:
            result = fn(provider, client, depname, messages, *args, **kwargs)
        except Exception as exc:
            log_event(
                "llm.failed",
                provider=provider,
                model=depname,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                status="error",
                error_type=type(exc).__name__,
            )
            raise
        log_event(
            "llm.completed",
            provider=provider,
            model=depname,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            status="ok",
        )
        return result

    return wrapped


def _maybe_navigate_computer_runtime(
    messages: list[dict[str, Any]], core: Any, policy: Any
) -> bool:
    from .runtime.logging_setup import log_event

    def debug(message: str) -> None:
        if (env_get("UAGENT_DEBUG_COMPUTER", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            print(f"[computer-debug] {message}", flush=True)

    log_event("computer.explicit_navigation.start")
    debug("explicit navigation: entered")
    """Do not navigate from the LLM thread.

    Navigation, including an initial or mid-task URL change, must be returned
    by the provider as a Computer Use ``navigate`` action and executed by the
    selected Runtime in the normal action loop.
    """
    runtime = getattr(core, "computer_use_runtime", None)
    if runtime is None:
        log_event("computer.explicit_navigation.no_runtime")
        return False
    latest = next(
        (
            item
            for item in reversed(messages)
            if isinstance(item, dict) and item.get("role") == "user"
        ),
        None,
    )
    content = (latest or {}).get("content")
    if isinstance(content, list):
        text = " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    else:
        text = str(content or "")
    urls = re.findall(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", text)
    if not urls:
        log_event("computer.explicit_navigation.no_url")
        return False
    url = urls[0].rstrip(".,。、;；)）]")
    from .computer_use.actions import ComputerAction
    from .computer_use.integration import _host_confirmation_callback
    from .computer_use.runtime import execute_action

    confirmation = getattr(core, "computer_use_confirmation", None)
    if not callable(confirmation):
        confirmation = _host_confirmation_callback(core)

    debug(f"explicit navigation: executing navigate url={url}")
    log_event("computer.explicit_navigation.action_start", url=url)
    result = execute_action(
        ComputerAction(
            action_id="explicit:navigate",
            action="navigate",
            provider="computer",
            text=url,
        ),
        policy=policy,
        runtime=runtime,
        confirm=confirmation,
        audit=None,
        session_id="computer-use",
        domain=urlparse(url).hostname,
    )
    debug(
        "explicit navigation: action result "
        f"success={result.success} error={result.error!r}"
    )
    if not result.success:
        log_event(
            "computer.explicit_navigation.failed",
            error=result.error or "navigation failed",
        )
        core.computer_use_diagnostic = result.error or "navigation failed"
        # Do not fall back to model-generated Ctrl+L/type/Enter actions after
        # an explicit bootstrap navigation failure.
        return True
    log_event("computer.explicit_navigation.done", url=url)
    debug("explicit navigation: execute_action returned success")
    return True


@_observed_llm_rounds
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
    global _TOTAL_ROUNDS, _PRODUCTIVE_ROUNDS, _TOOL_LAST_ROUND, _TOOL_AUTO_UNLOAD_ROUNDS, _TOOL_SPECS
    # Judgment mode: swap messages so all side effects go to judgment_messages
    if judgment_mode:
        if not judgment_messages:
            return ""
        messages = judgment_messages

    # Provider/model must be set before first LLM round (for save to file)
    if not judgment_mode:
        core.responses_state["provider"] = provider
        core.responses_state["model"] = depname

    direct_navigation_done = False

    # Install the shared Computer Use callback before the first round.
    # A missing Runtime is a diagnosable capability failure, not a process crash.
    if not judgment_mode:
        try:
            policy = core.get_computer_use_policy()
            if not policy.enabled:
                for name in (
                    "computer_use_runtime",
                    "computer_use_handler",
                    "computer_use_native_tool",
                    "computer_use_native_headers",
                    "computer_use_native_provider",
                ):
                    try:
                        setattr(core, name, None)
                    except Exception:
                        pass
            if policy.enabled:
                from .computer_use.integration import (
                    install_computer_use_handler,
                    make_unavailable_computer_use_handler,
                )

                try:
                    install_computer_use_handler(
                        core=core, provider=provider, model=depname, policy=policy
                    )
                    from .computer_use.native import prepare_native_computer_use

                    prepare_native_computer_use(
                        core=core, provider=provider, model=depname
                    )
                    # Create the selected runtime before applying an explicit
                    # URL. Native Computer Use must operate on the visible
                    # desktop surface, not a detached browser page.
                    current_runtime = getattr(core, "computer_use_runtime", None)
                    runtime_closed = False
                    page = getattr(current_runtime, "page", None)
                    is_closed = getattr(page, "is_closed", None)
                    if callable(is_closed):
                        try:
                            runtime_closed = bool(is_closed())
                        except Exception:
                            runtime_closed = True
                    if current_runtime is None or runtime_closed:
                        old_manager = getattr(
                            core, "computer_use_runtime_manager", None
                        )
                        if old_manager is not None and callable(
                            getattr(old_manager, "close", None)
                        ):
                            old_manager.close()
                        core.computer_use_runtime = None
                        from .computer_use.entrypoint_runtime import (
                            create_runtime_from_env,
                        )
                        from .computer_use.integration import _register_runtime_manager

                        manager = create_runtime_from_env(
                            force=True,
                            provider=provider,
                            environment=(
                                getattr(
                                    core,
                                    "computer_use_environment",
                                    (
                                        "browser"
                                        if provider
                                        in {
                                            "openai",
                                            "azure",
                                            "azure-openai",
                                            "azure_foundry",
                                            "azure-foundry",
                                            "gemini",
                                            "vertexai",
                                        }
                                        else "desktop"
                                    ),
                                )
                            ),
                        )
                        if manager is not None:
                            _register_runtime_manager(core, manager)
                    direct_navigation_done = _maybe_navigate_computer_runtime(
                        messages, core, policy
                    )
                except RuntimeError as exc:
                    core.computer_use_diagnostic = str(exc)
                    core.computer_use_handler = make_unavailable_computer_use_handler(
                        reason=str(exc)
                    )
        except AttributeError:
            pass

    if direct_navigation_done:
        diagnostic = str(getattr(core, "computer_use_diagnostic", "") or "")
        if (env_get("UAGENT_DEBUG_COMPUTER", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            print(
                "[computer-debug] run_llm_rounds: direct navigation return", flush=True
            )
        # The fast path returns before the normal LLM-loop finally block, so
        # release BUSY state explicitly.
        core.set_status(False, "")
        if diagnostic:
            return f"ブラウザーを開けませんでした: {diagnostic}"
        return "ブラウザーを開きました。"

    max_tool_rounds = 200
    round_count = 0

    empty_no_tool_rounds = 0

    # Some providers (Grok/xAI, OpenAI-compatible endpoints) may return empty
    # assistant messages after tool calls. Tolerate a few consecutive
    # empty/no-tool rounds, then abort with an explicit warning.
    # Default is provider-aware (grok/xai=5, others=2); override with
    # UAGENT_EMPTY_NO_TOOL_MAX.
    empty_no_tool_max = _resolve_empty_no_tool_max(provider)

    # Merge any deferred empty-no-tool recovery into the latest real user turn.
    if not judgment_mode:
        try:
            _consume_empty_no_tool_recovery(messages=messages, core=core)
        except Exception:
            pass

    cb = get_callbacks()
    prev_finish_skill = cb.finish_skill
    if not judgment_mode:
        cb.finish_skill = make_finish_skill_handler(messages, core)

    core.set_status(True, "LLM")

    use_llm_thread = _env_default_on("UAGENT_LLM_IN_THREAD")

    # Reset management tool call loop detection for this session
    _TOOL_CALL_FINGERPRINTS.clear()
    clear_consecutive_tool_call_streak()

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
            if not judgment_mode:
                core.computer_use_turn_id = str(round_count)

            (
                round_status,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
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
            # Age tools only on productive rounds (tool postamble / RS_OK).
            # Empty LLM continue rounds must not decrement/advance per-tool
            # disappearance counters.
            if round_status == _RS_OK:
                _PRODUCTIVE_ROUNDS += 1
                # Search backwards for the LAST assistant message with tool_calls.
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
                        _tname = (_tc.get("function") or {}).get("name", "")
                        if _tname:
                            _found_tool_names.add(str(_tname))
                    break

                for _tname in _found_tool_names:
                    _TOOL_LAST_ROUND[_tname] = _PRODUCTIVE_ROUNDS
                    _bump_threshold(_tname)
                    # tool_load(target) intentionally requested a target.
                    if _tname == "tool_load":
                        try:
                            for _m in reversed(messages):
                                if (
                                    not isinstance(_m, dict)
                                    or _m.get("role") != "assistant"
                                ):
                                    continue
                                _tcs = _m.get("tool_calls")
                                if not isinstance(_tcs, list) or not _tcs:
                                    continue
                                for _tc in _tcs:
                                    _fn = (
                                        (_tc.get("function") or {})
                                        if isinstance(_tc, dict)
                                        else {}
                                    )
                                    if str(_fn.get("name") or "") != "tool_load":
                                        continue
                                    _args = _parse_mgmt_tool_args(
                                        _fn.get("arguments") or "{}"
                                    )
                                    _target = ""
                                    if isinstance(_args, dict):
                                        _target = str(
                                            _args.get("name") or _args.get("tool") or ""
                                        ).strip()
                                    if _target:
                                        _TOOL_LAST_ROUND[_target] = _PRODUCTIVE_ROUNDS
                                break
                        except Exception:
                            pass
                    # tool_catalog may auto-load a tool; stamp single-loaded
                    # tools that still have no last-used marker.
                    if _tname == "tool_catalog":
                        try:
                            for _loaded_name in list(_LOADED_SINGLE_TOOLS):
                                if _loaded_name not in _TOOL_LAST_ROUND:
                                    _TOOL_LAST_ROUND[_loaded_name] = _PRODUCTIVE_ROUNDS
                        except Exception:
                            pass

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
                        if tname in ("tool_catalog", "tool_load", "unload_tool"):
                            continue
                        if tname not in _LOADED_SINGLE_TOOLS:
                            continue
                        if _is_tool_pinned(tname):
                            continue
                        threshold = _get_threshold(tname)
                        if threshold <= 0:
                            continue
                        last = _TOOL_LAST_ROUND.get(tname)
                        if last is None:
                            # Never used since load: grace starts at load round.
                            age = _productive_age(_LOADED_SINGLE_TOOLS.get(tname))
                            if age is not None and age >= threshold:
                                print(
                                    "[TOOLS auto-unload] "
                                    + _(
                                        "%(name)s (never used for %(n)d LLM rounds since load)"
                                    )
                                    % {"name": tname, "n": threshold},
                                    flush=True,
                                )
                                _disable_single_tool(tname)
                        else:
                            age = _productive_age(last)
                            if age is not None and age >= threshold:
                                print(
                                    "[TOOLS auto-unload] "
                                    + _("%(name)s (idle for %(n)d LLM rounds)")
                                    % {"name": tname, "n": threshold},
                                    flush=True,
                                )
                                _TOOL_LAST_ROUND.pop(tname, None)
                                _disable_single_tool(tname)
            # --- end auto-unload ---

            # Judgment mode: one round only
            if judgment_mode:
                break

    except LLMWaitInterrupted:
        # Normalize SDK wait interruptions for every provider at the common
        # round-loop boundary, then follow the normal stop-prompt path.
        with _core_module.interrupt_lock:
            _core_module.interrupt_requested = False
        _inject_stop_prompt(messages, core)

    finally:
        cb.finish_skill = prev_finish_skill
        # セッション中（プログラム終了まで）キャッシュを保持するため、ここでは削除しない。
        # クリーンアップは cli.py のメインループを抜けた際の finally で行う。
        core.set_status(False, "")

    if judgment_mode:
        return final_text or ""
    return None
