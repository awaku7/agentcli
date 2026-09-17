from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urlparse

from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang
from .llmcapa_util import provider_allows_responses_api

set_thread_lang(detect_lang())

from .translate import load_translate_config, translate_text
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
    _build_auto_shrink_projection,
    _get_shrink_max_tokens,
    _init_gemini_cache,
)
from .runtime.context_budget import ContextBudget
from .runtime.context_manager import ContextManager
from .runtime.context_plan_builder import build_context_plan
from .runtime.context_policy import ContextPolicy
from .runtime.message_transform import MessageTransformPipeline
from .runtime.provider_context import project_messages_for_provider
from .runtime.provider_cache import plan_provider_cache
from .llm_helpers import (
    _call_maybe_thread,
    _env_default_on,
    _auto_low_quality,
    _bump_effort,
    LLMWaitInterrupted,
)
from .llm_round_helpers import (
    _resolve_round_runtime_flags,
    _translate_assistant_if_needed,
)
from .runtime.legacy_openai_round import call_legacy_openai_compatible_round
from .runtime.legacy_round_registry import run_legacy_provider_round
from .providers.llm_deepseek import build_assistant_message_with_reasoning
from .providers.provider_caps import supports_generate_image_continuation
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
from .runtime.spinner import stop_quietly as _spinner_stop_quietly
from .tools.context import get_callbacks
from .tools.skill_history import make_finish_skill_handler
from .tools.llm_tool_narrowing import (
    _is_gpt54_tool_search_target,  # noqa: F401  (re-exported for tests)
    resolve_tool_discovery,
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
        runtime = getattr(core, "responses_runtime", None)
        interrupt = getattr(runtime, "interrupt", None)
        if callable(interrupt):
            interrupt()
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
    # An interrupt can leave a Gemini/Vertex cache associated with an
    # incomplete assistant tool turn. Force the next round to rebuild it
    # instead of combining the stale cache with a new user message.
    try:
        core._gemini_cache_needs_refresh = True
    except Exception:
        pass
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
# Count freshly executed calls of the same tool across consecutive rounds.
# This is a second, broader runaway guard than the same-args detector.
_CONSECUTIVE_TOOL_CALL_COUNT = 0
_CONSECUTIVE_TOOL_CALL_NAME = ""
_MGMT_TOOLS = frozenset({"tool_catalog", "tool_load", "unload_tool"})
_MGMT_LOOP_THRESHOLD = 4
# Same-args general tool loops (e.g. get_current_location xN) are also blocked.
# Keep this close to the management threshold so runaway tool spam stops early.
_GENERAL_TOOL_LOOP_THRESHOLD = 4


# Tools that may legitimately be called repeatedly with identical args in one
# session (polling/monitors). These stay on the management-only detector.
def _debug_tool_loop(event: str, **fields: Any) -> None:
    """Suppress verbose tool-loop diagnostics."""
    return


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


def _mgmt_tool_targets(name: str, args: Any) -> list[str]:
    """Return target tool names for load/unload (batch-aware)."""
    if name not in ("tool_load", "unload_tool") or not isinstance(args, dict):
        return []
    import re as _re

    def _split(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                out.extend(_split(item))
            return out
        text = str(value).strip()
        if not text:
            return []
        return [p for p in _re.split(r"[,\s;]+", text) if p]

    collected: list[str] = []
    collected.extend(_split(args.get("names")))
    collected.extend(_split(args.get("name")))
    collected.extend(_split(args.get("tool")))
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in collected:
        if entry not in seen:
            seen.add(entry)
            ordered.append(entry)
    return ordered


def _mgmt_tool_target(name: str, args: Any) -> str:
    """Return the target tool name for load/unload, else empty."""
    targets = _mgmt_tool_targets(name, args)
    return targets[0] if targets else ""


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
        targets = _mgmt_tool_targets(name, args)
        if targets:
            if len(targets) == 1:
                return f"{name}({targets[0]})"
            return f"{name}({','.join(targets)})"
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
    """Clear the consecutive same-tool call counter."""
    global _CONSECUTIVE_TOOL_CALL_COUNT, _CONSECUTIVE_TOOL_CALL_NAME
    _CONSECUTIVE_TOOL_CALL_COUNT = 0
    _CONSECUTIVE_TOOL_CALL_NAME = ""


def check_consecutive_tool_calls(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect too many consecutive calls of the same tool.

    A different tool starts a new streak. Arguments are intentionally ignored,
    so calls of the same tool with different arguments still count together.
    """
    global _CONSECUTIVE_TOOL_CALL_COUNT, _CONSECUTIVE_TOOL_CALL_NAME
    raw_limit = env_get("UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT", "100")
    try:
        default_limit = max(1, int(raw_limit))
    except (TypeError, ValueError):
        default_limit = 100
    limit = default_limit if threshold is None else max(1, int(threshold))
    if not tool_calls_list:
        if record:
            clear_consecutive_tool_call_streak()
        return False, "", 0

    count = _CONSECUTIVE_TOOL_CALL_COUNT
    name = _CONSECUTIVE_TOOL_CALL_NAME
    for tool_call in tool_calls_list:
        function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        current_name = (
            str(function.get("name", "")).strip() if isinstance(function, dict) else ""
        )
        if not current_name:
            continue
        if current_name == name:
            count += 1
        else:
            name = current_name
            count = 1

    if record:
        _CONSECUTIVE_TOOL_CALL_NAME = name
        _CONSECUTIVE_TOOL_CALL_COUNT = count
    return count >= limit, _("consecutive tool calls"), count


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
            for target in _mgmt_tool_targets(name, args):
                unload_targets.add(target)
            # unload itself is not loop-counted; it only resets load streaks
            continue
        if name == "tool_load":
            # Batch loads fan out per target so reloads of one tool do not
            # inherit the counter of an unrelated batch.
            for target in _mgmt_tool_targets(name, args) or [""]:
                fp = f"tool_load:{target}"
                round_counts[fp] = round_counts.get(fp, 0) + 1
                display.setdefault(fp, f"tool_load({target})" if target else name)
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


def _build_round_context_plan(
    *,
    provider: str,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    workspace_id: str,
    tool_specs: Any = (),
    key_provider: Any = None,
    telemetry: dict[str, Any] | None = None,
    history_revision: str = "",
    schema_revision: str = "1",
) -> Any:
    """Build a round plan through ContextManager when available.

    The fallback keeps the registry path usable by lightweight test cores and
    embedded callers that predate the context manager boundary.
    """
    decisions = getattr(core, "context_tool_decisions", None) or ()
    manager = getattr(core, "context_manager", None)
    builder = getattr(manager, "build_context_plan", None)
    if callable(builder):
        return builder(
            workspace_id=workspace_id,
            messages=call_messages,
            tool_specs=tool_specs,
            decisions=decisions,
            telemetry=telemetry or {},
            key_provider=key_provider,
            history_revision=history_revision,
            schema_revision=schema_revision,
            provider=provider,
            model=depname,
        )
    return build_context_plan(
        workspace_id=workspace_id,
        messages=call_messages,
        tool_specs=tool_specs,
        decisions=decisions,
        policy={"provider": provider, "model": depname},
        telemetry=telemetry or {},
        key_provider=key_provider,
        history_revision=history_revision,
        schema_revision=schema_revision,
    )


def _record_round_context_plan(
    *, provider: str, depname: str, call_messages: list[dict[str, Any]], core: Any
) -> Any | None:
    """Build and return the provider-neutral plan for this round."""
    if not _env_default_on("UAGENT_ROUND_CONTRACTS"):
        return None
    workspace_id = str(getattr(core, "workdir", "") or os.getcwd())
    tool_specs = getattr(core, "context_tool_specs", None) or ()
    try:
        core.context_plan = _build_round_context_plan(
            provider=provider,
            depname=depname,
            call_messages=call_messages,
            core=core,
            workspace_id=workspace_id,
            tool_specs=tool_specs,
            telemetry={"round_contracts": True},
        )
        return core.context_plan
    except Exception:
        # The feature flag is observational until the new orchestration path
        # owns dispatch, so a plan failure must not alter existing execution.
        core.context_plan = None
    return None


def _apply_semantic_message_transforms(
    call_messages: list[dict[str, Any]], tr_cfg: Any
) -> list[dict[str, Any]]:
    """Apply provider-neutral transforms before provider message projection."""
    translator = None
    if tr_cfg is not None:

        def translator(text: str) -> str:
            return translate_text(text, direction="to_llm", src_lang="", cfg=tr_cfg)[0]

    try:
        result = MessageTransformPipeline().apply(call_messages, translator=translator)
        return [dict(message) for message in result.messages]
    except Exception:
        # Translation is optional and transformations must not interrupt the
        # established request path while the new boundary is introduced.
        return call_messages


def _begin_responses_runtime(
    *, core: Any, provider: str, model: str, enabled: bool
) -> Any | None:
    """Synchronize the new continuation state machine with legacy state.

    This is deliberately a compatibility bridge: ``responses_state`` remains
    the persisted source until the round orchestrator owns session restore.
    A bridge failure must never change the established request path.
    """
    if not enabled:
        return None
    try:
        from .providers.responses_runtime import ResponsesRuntime

        runtime = getattr(core, "responses_runtime", None)
        if not isinstance(runtime, ResponsesRuntime):
            runtime = ResponsesRuntime(provider=provider, model=model)
            setattr(core, "responses_runtime", runtime)
        else:
            runtime.switch_provider(provider, model)

        state = getattr(core, "responses_state", {})
        previous_id = (
            state.get("previous_response_id") if isinstance(state, dict) else None
        )
        if isinstance(previous_id, str) and previous_id.startswith("resp_"):
            if runtime.previous_response_id != previous_id:
                runtime.restore_continuation(
                    previous_id,
                    session_generation=runtime.session_generation,
                    provider=provider,
                    model=model,
                )
            runtime.begin_request(previous_response_id=previous_id)
        else:
            runtime.begin_request()
        return runtime
    except Exception:
        return None


def _record_responses_runtime_response(
    *, core: Any, enabled: bool, tool_calls: list[dict[str, Any]]
) -> None:
    """Record the completed Responses result for tool-output invariants."""
    if not enabled:
        return
    runtime = getattr(core, "responses_runtime", None)
    state = getattr(core, "responses_state", {})
    response_id = state.get("previous_response_id") if isinstance(state, dict) else None
    if runtime is None or not isinstance(response_id, str) or not response_id:
        return
    try:
        runtime.record_response(response_id, tool_calls=tool_calls)
    except Exception:
        # The legacy path retains its error/retry behaviour during migration.
        pass


def _apply_remote_recovery_update(core: Any, update: Any) -> bool:
    """Synchronize a provider-owned recovery result without mutating history."""
    state = getattr(core, "responses_state", None)
    if not isinstance(state, dict):
        return False
    context_plan = getattr(core, "context_plan", None)
    expected_metadata = {
        "plan_id": getattr(context_plan, "plan_id", ""),
        "input_fingerprint": getattr(context_plan, "input_fingerprint", ""),
        "history_revision": getattr(context_plan, "history_revision", ""),
        "schema_revision": getattr(context_plan, "schema_revision", ""),
        "projection_id": getattr(core, "context_projection_id", ""),
    }
    for name, expected in expected_metadata.items():
        actual = str(getattr(update, name, "") or "")
        if expected and actual and str(expected) != actual:
            state.pop("previous_response_id", None)
            return False
    if getattr(update, "remote_mutation_status", "") != "applied" or not getattr(
        update, "continuation_allowed", False
    ):
        state.pop("previous_response_id", None)
        return False
    response_id = getattr(update, "compacted_response_id", None)
    if not isinstance(response_id, str) or not response_id:
        return False
    state["previous_response_id"] = response_id
    state["session_generation"] = int(getattr(update, "session_generation", 0))
    runtime = getattr(core, "responses_runtime", None)
    if runtime is not None:
        try:
            fingerprint = str(getattr(update, "input_fingerprint", "") or "")
            expected_fingerprint = (
                fingerprint if expected_metadata["input_fingerprint"] else None
            )
            runtime.restore_continuation(
                response_id,
                session_generation=state["session_generation"],
                provider=state.get("provider"),
                model=state.get("model"),
                expected_input_fingerprint=expected_fingerprint,
                input_fingerprint_status=(
                    "valid" if expected_fingerprint else "not_checked"
                ),
            )
        except Exception:
            state.pop("previous_response_id", None)
            return False
    return True


def _try_responses_remote_recovery(core: Any, client: Any, recovery_plan: Any) -> bool:
    """Run provider-owned compaction and adopt it only on a valid update."""
    try:
        from .providers.responses_manager import ResponsesManager
        from .providers.responses_recovery_port import ResponsesRecoveryPort

        state = getattr(core, "responses_state", None)
        if not isinstance(state, dict):
            return False
        manager = ResponsesManager(
            client,
            provider=str(state.get("provider") or "openai"),
            model=str(state.get("model") or ""),
        )
        generation = int(state.get("session_generation", 0) or 0)
        update = ResponsesRecoveryPort(manager).apply(
            recovery_plan,
            state,
            expected_session_generation=generation,
        )
        core.last_recovery_update = {
            "recovery_id": recovery_plan.recovery_id,
            "strategy": recovery_plan.strategy,
            "status": update.remote_mutation_status,
            "session_generation": update.session_generation,
            "journal_entry_id": update.journal_entry_id,
            "input_fingerprint": getattr(update, "input_fingerprint", ""),
            "plan_id": getattr(update, "plan_id", ""),
            "projection_id": getattr(update, "projection_id", None),
            "history_revision": getattr(update, "history_revision", ""),
            "schema_revision": getattr(update, "schema_revision", "1"),
        }
        try:
            from .runtime.logging_setup import log_event

            log_event(
                "recovery.remote",
                status=update.remote_mutation_status,
                strategy=recovery_plan.strategy,
                recovery_id=recovery_plan.recovery_id,
            )
        except Exception:
            pass
        return _apply_remote_recovery_update(core, update)
    except Exception:
        return False


def _sync_registry_responses_terminal(core: Any, status: str) -> None:
    """Mirror a non-successful registry terminal state into persisted state."""
    if status == "completed":
        return
    state = getattr(core, "responses_state", None)
    if not isinstance(state, dict):
        return
    state.pop("previous_response_id", None)
    state.pop("active_response_id", None)
    state.pop("_stale_rid_occurred", None)
    state["last_response_status"] = status


def _try_registry_simple_chat_round(
    *,
    provider: str,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    use_responses_api: bool,
    stream_responses: bool,
    send_tools_this_round: bool,
    round_count: int,
) -> tuple[bool, str, str, list[dict[str, Any]]] | None:
    """Run the default-on registry path for OpenAI-compatible rounds.

    Explicit ``off`` values restore the legacy path. Unsupported providers and
    intentionally deferred modes also retain their established fallback.
    """
    enabled = (env_get("UAGENT_PROVIDER_REGISTRY", "") or "").strip().lower()
    enabled_providers = {item.strip() for item in enabled.split(",") if item.strip()}
    if provider not in {"openai", "azure"}:
        return None
    if enabled in {"0", "false", "no", "off"}:
        return None
    if enabled and provider not in enabled_providers and "all" not in enabled_providers:
        return None
    if use_responses_api and not _env_default_on("UAGENT_PROVIDER_REGISTRY_RESPONSES"):
        return None
    if use_responses_api:
        discovery = resolve_tool_discovery(
            provider=provider,
            depname=depname,
            use_responses_api=True,
        )
        if discovery.uses_legacy_catalog:
            # Legacy client-side tool narrowing must remain on the established
            # path until the registry adapter owns tool delivery decisions.
            return None
    if send_tools_this_round and not _env_default_on("UAGENT_PROVIDER_REGISTRY_TOOLS"):
        return None
    if send_tools_this_round and not getattr(core, "context_tool_specs", None):
        # The registry adapter requires a prepared context/tool projection.
        # Defer to the established path when no selection was supplied.
        return None
    try:
        from .providers.runtime_registry import build_provider_runtime_registry
        from .runtime.round_contracts import RoundIdentifiers
        from .runtime.round_identity import (
            CredentialStoreWorkspaceKeyProvider,
            RoundIdentityFactory,
        )
        from .runtime.round_orchestrator import RoundOrchestrator

        marker = f"registry-{provider}-{round_count}-{id(core)}"
        identifiers = RoundIdentifiers(
            turn_id=marker,
            round_id=marker,
            attempt_id=marker,
            request_id=marker,
            stream_id=marker,
            session_generation=0,
        )
        workspace_id = str(getattr(core, "workdir", "") or os.getcwd())
        key_provider = CredentialStoreWorkspaceKeyProvider()
        identity_factory = RoundIdentityFactory(workspace_id, key_provider)
        tool_specs = getattr(core, "context_tool_specs", None) or ()
        if send_tools_this_round and not tool_specs:
            from . import tools as _tools

            tool_specs = tuple(_tools.get_tool_specs() or ())
        if send_tools_this_round and round_count <= 1:
            discovery = resolve_tool_discovery(
                provider=provider,
                depname=depname,
                # Bootstrap selection is based on the GPT-5.4 capability;
                # the registry route may still be Chat Completions.
                use_responses_api=True,
            )
            if discovery.uses_legacy_catalog or (
                discovery.uses_native_search and not use_responses_api
            ):
                management_specs = tuple(
                    spec
                    for spec in tool_specs
                    if isinstance(spec, dict)
                    and (spec.get("function") or {}).get("name") in _MGMT_TOOLS
                )
                if management_specs:
                    tool_specs = management_specs
        if send_tools_this_round and not use_responses_api:
            from .llm_round_helpers import _limit_chat_completion_tools
            from . import tools as _tools

            tool_specs = tuple(
                _limit_chat_completion_tools(list(tool_specs), call_messages)
            )
            _tools.log_tools_being_sent(tool_specs, where="registry_chatcompletions")
        plan = _build_round_context_plan(
            provider=provider,
            depname=depname,
            call_messages=call_messages,
            core=core,
            workspace_id=workspace_id,
            tool_specs=tool_specs if send_tools_this_round else (),
            key_provider=key_provider,
            history_revision=str(getattr(core, "history_revision", "") or ""),
            schema_revision=str(getattr(core, "context_schema_revision", "1") or "1"),
        )
        core.context_plan = plan
        transport = "responses" if use_responses_api else "chat_completions"
        from .providers.openai_projection_policy import build_openai_projection

        projection = build_openai_projection(
            provider=provider,
            model=depname,
            transport=transport,
            messages=call_messages,
            send_tools=send_tools_this_round,
            compaction_threshold=_get_shrink_max_tokens(depname),
        )
        options = projection.options
        reasoning = projection.reasoning
        auto_user_text = projection.auto_user_text
        effort_used = projection.effort_used
        if use_responses_api:
            state = getattr(core, "responses_state", {})
            previous_id = (
                state.get("previous_response_id") if isinstance(state, dict) else None
            )
            if isinstance(previous_id, str) and previous_id.startswith("resp_"):
                options["previous_response_id"] = previous_id
        registry = build_provider_runtime_registry(
            provider=provider,
            client=client,
            model=depname,
            identifiers=identifiers,
            transport=transport,
            streaming=stream_responses,
            options=options,
        )
        cancellation = getattr(core, "cancellation_token", None)
        if cancellation is None:
            cancellation = type(
                "NoCancellation",
                (),
                {"is_cancelled": lambda self: False},
            )()
        result = (
            RoundOrchestrator(registry)
            .run(
                plan,
                provider=provider,
                session={
                    "identity_factory": identity_factory,
                    "responses_runtime": getattr(core, "responses_runtime", None),
                    "recovery_hint": getattr(core, "last_recovery_update", None),
                },
                cancellation=cancellation,
            )
            .result
        )
        if (
            reasoning == "auto"
            and effort_used is not None
            and result.status == "completed"
            and not result.tool_calls
            and _auto_low_quality(auto_user_text, result.assistant_text)
        ):
            from dataclasses import replace

            from .runtime.round_runtime import RoundAttemptBudget, RetryRequest

            next_effort = _bump_effort(effort_used)
            retry_budget = RoundAttemptBudget(
                total_limit=1, reason_limits={"feature_fallback": 1}
            )
            if next_effort and retry_budget.try_consume(
                RetryRequest("feature_fallback", "reasoning auto quality retry")
            ):
                retry_options = dict(options)
                if use_responses_api:
                    retry_options["reasoning"] = {"effort": next_effort}
                else:
                    retry_options["reasoning_effort"] = next_effort
                retry_identifiers = replace(
                    identifiers,
                    attempt_id=f"{identifiers.attempt_id}-auto-retry",
                    request_id=f"{identifiers.request_id}-auto-retry",
                    stream_id=f"{identifiers.stream_id}-auto-retry",
                )
                retry_registry = build_provider_runtime_registry(
                    provider=provider,
                    client=client,
                    model=depname,
                    identifiers=retry_identifiers,
                    transport=transport,
                    streaming=stream_responses,
                    options=retry_options,
                )
                result = (
                    RoundOrchestrator(retry_registry)
                    .run(
                        plan,
                        provider=provider,
                        session={
                            "identity_factory": identity_factory,
                            "responses_runtime": getattr(
                                core, "responses_runtime", None
                            ),
                            "recovery_hint": getattr(
                                core, "last_recovery_update", None
                            ),
                        },
                        cancellation=cancellation,
                    )
                    .result
                )
                core.round_attempt_budget = retry_budget
                core.last_auto_reasoning_retry = {
                    "initial_effort": effort_used,
                    "retry_effort": next_effort,
                }
        if result.status == "failed":
            core.context_projection_id = result.projection_id
            from .runtime.context_recovery import ContextRecoveryManager
            from .runtime.llm_error_classifier import LLMErrorClassifier
            from .runtime.round_runtime import RoundAttemptBudget, RetryRequest

            error_text = str((result.error or {}).get("message") or "")
            if (
                LLMErrorClassifier().classify(RuntimeError(error_text)).kind
                == "context_overflow"
            ):
                budget = RoundAttemptBudget(total_limit=1)
                if budget.try_consume(
                    RetryRequest("context_overflow", "registry local recovery")
                ):
                    recovery = ContextRecoveryManager().plan(
                        context_plan=plan,
                        projection_id=result.projection_id,
                        error_text=error_text,
                        attempt_id=identifiers.attempt_id,
                    )
                    if use_responses_api:
                        from dataclasses import replace

                        remote_plan = replace(
                            recovery,
                            strategy="provider_compact",
                            remote_session_mutation=True,
                        )
                        if _try_responses_remote_recovery(core, client, remote_plan):
                            return None
                    recovery_hint = {
                        "recovery_id": recovery.recovery_id,
                        "strategy": recovery.strategy,
                        "omitted_message_indexes": recovery.omitted_message_indexes,
                        "omitted_message_ids": recovery.omitted_message_ids,
                        "source_plan_id": recovery.plan_id,
                    }
                    core.last_recovery_plan = recovery
                    result = (
                        RoundOrchestrator(registry)
                        .run(
                            plan,
                            provider=provider,
                            session={
                                "identity_factory": identity_factory,
                                "responses_runtime": getattr(
                                    core, "responses_runtime", None
                                ),
                                "recovery_hint": recovery_hint,
                            },
                            cancellation=cancellation,
                        )
                        .result
                    )
                    core.context_projection_id = result.projection_id
        # A non-completed registry response is not a usable assistant turn.
        # Let the established provider path handle the request so registry
        # adapter failures do not silently terminate the user operation.
        if result.status != "completed":
            if use_responses_api:
                _sync_registry_responses_terminal(core, result.status)
            try:
                from .runtime.logging_setup import log_event

                log_event(
                    "llm.registry_fallback",
                    provider=provider,
                    model=depname,
                    registry_status=result.status,
                )
            except Exception:
                pass
            return None

        # A completed registry response without text or tool calls is not a
        # usable assistant turn. Let the established provider path retry it
        # rather than treating an empty response as a successful final answer.
        if (
            not result.assistant_text
            and not result.tool_calls
            and not result.continuation_update
        ):
            return None
        if result.continuation_update and isinstance(
            getattr(core, "responses_state", None), dict
        ):
            core.responses_state["previous_response_id"] = result.continuation_update[
                "response_id"
            ]
        elif use_responses_api:
            _sync_registry_responses_terminal(core, result.status)
        normalized_tool_calls: list[dict[str, Any]] = []
        for call in result.tool_calls:
            item = dict(call)
            function = item.get("function")
            if not isinstance(function, dict):
                function = {
                    "name": str(item.get("name") or ""),
                    "arguments": str(item.get("arguments") or "{}"),
                }
                item["function"] = function
            item.setdefault(
                "id", str(item.get("tool_call_id") or item.get("call_id") or "")
            )
            item.setdefault("type", "function")
            normalized_tool_calls.append(item)
        return (
            result.status == "completed",
            result.assistant_text,
            result.reasoning_text,
            normalized_tool_calls,
        )
    except Exception:
        return None


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
    if not judgment_mode:
        context_manager = getattr(core, "context_manager", None)
        build_message_context = getattr(context_manager, "build_message_context", None)
        if callable(build_message_context):
            active_context = build_message_context(call_messages)
            core.active_context = active_context
            _persist_context_decision_log(active_context, core)
            call_messages = active_context.messages
    if not judgment_mode:
        round_plan = _record_round_context_plan(
            provider=provider, depname=depname, call_messages=call_messages, core=core
        )
        if round_plan is not None:
            call_messages = [dict(message) for message in round_plan.messages]
    call_messages = _apply_semantic_message_transforms(call_messages, tr_cfg)
    call_messages = project_messages_for_provider(
        call_messages, provider=provider, model=depname
    )

    use_responses_api, stream_responses = _resolve_round_runtime_flags(
        tr_cfg=tr_cfg,
        core=core,
        provider=provider,
        depname=depname,
    )
    # Responses API is only supported when provider/model allow it.
    if (
        provider != "meta"
        and use_responses_api
        and not provider_allows_responses_api(provider, depname)
    ):
        use_responses_api = False
    _begin_responses_runtime(
        core=core,
        provider=provider,
        model=depname,
        enabled=use_responses_api and not judgment_mode,
    )

    def _call_maybe_thread_fn(fn: Any) -> Any:
        return _call_maybe_thread(fn, use_llm_thread=use_llm_thread)

    # Build an optional LLM-summary projection without mutating persistent
    # conversation history. The provider receives the projection only for
    # this request; the full history remains available for later retrieval.
    _using_prev_rid = bool(core.responses_state.get("previous_response_id"))
    projection_changed = False
    if not judgment_mode and not _using_prev_rid:
        projected_cache, projected_messages = _build_auto_shrink_projection(
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
        if projected_messages != messages:
            projection_changed = True
            gemini_cache_name = projected_cache
            call_messages = _build_call_messages(
                provider=provider,
                messages=projected_messages,
                core=core,
                depname=depname,
                gemini_cache_name=gemini_cache_name,
            )
            context_manager = getattr(core, "context_manager", None)
            build_message_context = getattr(
                context_manager, "build_message_context", None
            )
            if callable(build_message_context):
                active_context = build_message_context(call_messages)
                core.active_context = active_context
                _persist_context_decision_log(active_context, core)
                call_messages = active_context.messages
            call_messages = _apply_semantic_message_transforms(call_messages, tr_cfg)
            call_messages = project_messages_for_provider(
                call_messages, provider=provider, model=depname
            )
            if not judgment_mode:
                _record_round_context_plan(
                    provider=provider,
                    depname=depname,
                    call_messages=call_messages,
                    core=core,
                )

    cache_plan = plan_provider_cache(
        provider=provider,
        model=depname,
        projection_changed=projection_changed,
        previous_response_id=_using_prev_rid,
    )
    try:
        core.provider_cache_plan = cache_plan.to_dict()
    except Exception:
        pass

    if round_count > max_tool_rounds:
        # A hard tool-round stop can leave the provider cache paired with the
        # last assistant tool turn. Rebuild Gemini/Vertex cache state before a
        # later user continuation rather than reusing that stale turn.
        if provider in ("gemini", "vertexai"):
            try:
                core._gemini_cache_needs_refresh = True
            except Exception:
                pass
        _spinner_stop_quietly()
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
    # The isolated LM Studio SDK adapter can reuse the normal uagent tool
    # executor without importing this module at provider-import time.
    try:
        core._lmstudio_sdk_messages = messages
        core._lmstudio_sdk_cache_mgr = cache_mgr
    except Exception:
        pass
    if judgment_mode:
        send_tools_this_round = False
    max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
    retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
    retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

    tool_calls_list: list[dict[str, Any]] = []
    assistant_text: str = ""

    from .runtime.provider_round_dispatcher import dispatch_provider_round

    dispatch = dispatch_provider_round(
        registry_runner=None if judgment_mode else _try_registry_simple_chat_round,
        legacy_runner=run_legacy_provider_round,
        openai_runner=call_legacy_openai_compatible_round,
        registry_kwargs={
            "provider": provider,
            "client": client,
            "depname": depname,
            "call_messages": call_messages,
            "core": core,
            "use_responses_api": use_responses_api,
            "stream_responses": stream_responses,
            "send_tools_this_round": bool(send_tools_this_round),
            "round_count": round_count,
        },
        legacy_kwargs={
            "provider": provider,
            "client": client,
            "depname": depname,
            "call_messages": call_messages,
            "messages": messages,
            "gemini_cache_name": gemini_cache_name,
            "cache_mgr": cache_mgr,
            "core": core,
            "make_client_fn": make_client_fn,
            "call_maybe_thread_fn": _call_maybe_thread_fn,
            "append_result_to_outfile_fn": append_result_to_outfile_fn,
            "try_open_images_from_text_fn": try_open_images_from_text_fn,
            "empty_no_tool_rounds": empty_no_tool_rounds,
            "empty_no_tool_max": empty_no_tool_max,
            "tr_cfg": tr_cfg,
            "use_responses_api": use_responses_api,
            "stream_responses": stream_responses,
            "send_tools_this_round": send_tools_this_round,
            "max_retries_429": max_retries_429,
            "retry_base": retry_base,
            "retry_cap": retry_cap,
            "judgment_mode": judgment_mode,
            "inject_stop_prompt_fn": _inject_stop_prompt,
            "translate_assistant_fn": _translate_assistant_if_needed,
            "should_keep_assistant_message_fn": _should_keep_assistant_message,
            "append_assistant_message_fn": _append_assistant_message,
            "handle_empty_no_tool_fn": _handle_openai_empty_no_tool,
            "emit_final_answer_fn": _emit_final_answer_if_any,
        },
        openai_kwargs={
            "provider": provider,
            "client": client,
            "depname": depname,
            "call_messages": call_messages,
            "core": core,
            "make_client_fn": make_client_fn,
            "call_maybe_thread_fn": _call_maybe_thread_fn,
            "use_responses_api": use_responses_api,
            "stream_responses": stream_responses,
            "send_tools_this_round": send_tools_this_round,
            "max_retries_429": max_retries_429,
            "retry_base": retry_base,
            "retry_cap": retry_cap,
            "messages": messages,
            "responses_state": core.responses_state,
            "round_count": round_count,
        },
    )
    registry_simple_result = dispatch.result if dispatch.source == "registry" else None
    if registry_simple_result is not None:
        ok, assistant_text, reasoning_content, tool_calls_list = registry_simple_result
        if not ok:
            return (
                _RS_RETURN,
                client,
                gemini_cache_name,
                empty_no_tool_rounds,
                assistant_text,
            )
        if not tool_calls_list:
            assistant_text = _translate_assistant_if_needed(
                assistant_text=assistant_text,
                tr_cfg=tr_cfg,
                use_responses_api=use_responses_api,
                stream_responses=stream_responses,
                stream_output_rendered=False,
            )
            _emit_final_answer_if_any(
                assistant_text=assistant_text,
                use_responses_api=use_responses_api,
                stream_responses=stream_responses,
                append_result_to_outfile_fn=append_result_to_outfile_fn,
                try_open_images_from_text_fn=try_open_images_from_text_fn,
                reasoning_content=reasoning_content,
                skip_print=False,
                stream_output_rendered=False,
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
        if _should_keep_assistant_message(assistant_text, tool_calls_list):
            _append_assistant_message(
                messages=messages,
                core=core,
                assistant_text=assistant_text,
                tool_calls_list=tool_calls_list,
            )
        empty_no_tool_rounds = 0

    # ── Provider dispatch ─────────────────────────────────────────

    if registry_simple_result is not None:
        pass
    else:
        legacy_round_result = dispatch.result if dispatch.source == "legacy" else None
        if legacy_round_result is not None:
            return legacy_round_result
        (
            ok,
            client,
            assistant_text,
            reasoning_content,
            tool_calls_list,
            _is_xai_grpc,
        ) = dispatch.result
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
                        (provider == "grok" and stream_responses and _is_xai_grpc)
                        or (provider == "inception" and stream_responses)
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

    _debug_tool_loop(
        "received",
        provider=provider,
        count=len(tool_calls_list),
        calls=[
            {
                "id": tc.get("id"),
                "name": (tc.get("function") or {}).get("name"),
                "args_sha256": hashlib.sha256(
                    str((tc.get("function") or {}).get("arguments", "")).encode(
                        "utf-8", "replace"
                    )
                ).hexdigest()[:12],
            }
            for tc in tool_calls_list
            if isinstance(tc, dict)
        ],
    )
    _record_responses_runtime_response(
        core=core,
        enabled=use_responses_api,
        tool_calls=tool_calls_list,
    )
    executed_new_tool, fresh_tool_calls = _execute_tool_calls(
        tool_calls_list=tool_calls_list,
        messages=messages,
        core=core,
        cache_mgr=cache_mgr,
        responses_api_continuation=use_responses_api,
        responses_runtime=getattr(core, "responses_runtime", None),
    )
    if provider in ("gemini", "vertexai") and any(
        isinstance(tc, dict)
        and (tc.get("function") or {}).get("name") == "tool_catalog"
        for tc in fresh_tool_calls
    ):
        # Only a successful catalog call completes the Gemini discovery
        # boundary. Other tool calls must not silently skip discovery later.
        core._gemini_tool_catalog_ready = True
    # Record actual execution, not only the assistant message shape. Some
    # providers normalize tool calls differently, which previously caused a
    # genuinely used tool to look idle to the auto-unloader.
    next_productive_round = _PRODUCTIVE_ROUNDS + 1
    for _tc in fresh_tool_calls:
        if not isinstance(_tc, dict):
            continue
        _name = str((_tc.get("function") or {}).get("name") or "").strip()
        if _name:
            _TOOL_LAST_ROUND[_name] = next_productive_round
    _debug_tool_loop(
        "executed",
        fresh_count=len(fresh_tool_calls),
        executed_new_tool=executed_new_tool,
        fresh_names=[
            (tc.get("function") or {}).get("name")
            for tc in fresh_tool_calls
            if isinstance(tc, dict)
        ],
    )

    if not supports_generate_image_continuation(provider) and any(
        isinstance(tc, dict)
        and (tc.get("function") or {}).get("name") == "generate_image"
        for tc in tool_calls_list
    ):
        # This path intentionally terminates the Responses tool continuation:
        # the provider cannot safely continue after generate_image. Clear the
        # server-side response id here, at the orchestration boundary, so the
        # next user turn starts from the local history instead of reusing an
        # incomplete response chain.
        try:
            clear_continuation = getattr(core, "clear_responses_continuation", None)
            if callable(clear_continuation):
                clear_continuation()
        except Exception:
            pass
        return (
            _RS_BREAK,
            client,
            gemini_cache_name,
            empty_no_tool_rounds,
            assistant_text,
        )

    # Re-check before the next LLM call.

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
            _debug_tool_loop("blocked", name=blocked_name, count=blocked_count)
            _spinner_stop_quietly()
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
            _debug_tool_loop("blocked", name=blocked_name, count=blocked_count)
            _spinner_stop_quietly()
            print(
                _(
                    "[WARN] %(n)d consecutive tool calls; aborting to prevent runaway execution."
                )
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
            _debug_tool_loop("blocked", name=blocked_name, count=blocked_count)
            _spinner_stop_quietly()
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


def _apply_context_budget(messages: list[dict[str, Any]], core: Any) -> bool:
    """Bound older tool-result messages without breaking tool-call pairing."""
    policy = getattr(core, "context_policy", ContextPolicy.from_environment())
    if not policy.budget_enabled or policy.budget_unlimited:
        return False
    try:
        total_limit = max(1, int(policy.budget_chars))
    except (TypeError, ValueError):
        total_limit = 100_000
    budget = ContextBudget(total_chars=total_limit)
    total = sum(len(str(message.get("content") or "")) for message in messages)
    if total <= budget.total_chars:
        return False
    tool_records: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if message.get("role") != "tool":
            continue
        content = str(message.get("content") or "")
        tool_records.append(
            {
                "message_index": index,
                "size_bytes": len(content),
                "importance": "normal",
                "evictable": True,
                "created_at": str(index),
            }
        )
    if not tool_records:
        return False
    # Keep the newest tool output intact so the active continuation remains
    # useful; older outputs can be restored from their artifact references.
    newest_index = max(item["message_index"] for item in tool_records)
    for item in tool_records:
        if item["message_index"] == newest_index:
            item["evictable"] = False
    non_tool_total = total - sum(item["size_bytes"] for item in tool_records)
    target_tool_chars = max(0, budget.total_chars - non_tool_total)
    selected = budget.select_evictable(tool_records, target_chars=target_tool_chars)
    changed = False
    for item in selected:
        message = messages[item["message_index"]]
        content = str(message.get("content") or "")
        artifact_ref = next(
            (
                line.partition(":")[2].strip()
                for line in content.splitlines()
                if line.startswith("artifact_ref:")
            ),
            "",
        )
        suffix = f"\nartifact_ref: {artifact_ref}" if artifact_ref else ""
        message["content"] = "[tool result evicted by ContextBudget]" + suffix
        changed = True
    return changed


def _record_context_telemetry(
    messages: list[dict[str, Any]], core: Any, raw_chars: int
) -> dict[str, Any]:
    """Record message-preserving active-context projection metrics."""
    sections: dict[str, dict[str, int]] = {}
    active_chars = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown")
        chars = len(str(message.get("content") or ""))
        active_chars += chars
        stats = sections.setdefault(role, {"message_count": 0, "active_chars": 0})
        stats["message_count"] += 1
        stats["active_chars"] += chars

    raw_chars = max(0, int(raw_chars))
    saved_chars = raw_chars - active_chars
    budget = getattr(getattr(core, "context_manager", None), "budget", None)
    report: dict[str, Any] = {
        "raw_chars": raw_chars,
        "active_chars": active_chars,
        "saved_chars": saved_chars,
        "saved_ratio": saved_chars / raw_chars if raw_chars else 0.0,
        "sections": sections,
    }
    if isinstance(budget, ContextBudget):
        report["budget"] = budget.usage(
            system=sections.get("system", {}).get("active_chars", 0),
            user=sections.get("user", {}).get("active_chars", 0),
            assistant=sections.get("assistant", {}).get("active_chars", 0),
            tool=sections.get("tool", {}).get("active_chars", 0),
        )
    try:
        core.context_report = report
    except Exception:
        pass
    return report


def _persist_context_decision_log(active_context: Any, core: Any) -> bool:
    """Persist one active-context decision log when session storage is active."""
    store = getattr(core, "session_store", None)
    session_id = getattr(core, "_session_store_active_id", None) or getattr(
        core, "session_id", None
    )
    recorder = getattr(store, "record_context_decisions", None)
    decisions = getattr(active_context, "decision_log", None)
    if not decisions:
        decisions = getattr(core, "context_tool_decisions", None)
    if not callable(recorder) or not session_id or not decisions:
        return False
    normalized_decisions = [
        item.to_dict() if hasattr(item, "to_dict") else item for item in decisions
    ]
    try:
        recorder(str(session_id), normalized_decisions)
        return True
    except Exception:
        return False


def _format_agent_state_context(
    state: dict[str, Any], *, max_chars: int | None = None
) -> str:
    """Render agent state with stable priorities and optional section budget."""
    completed = state.get("completed_steps") or []
    if not isinstance(completed, list):
        completed = list(completed) if isinstance(completed, tuple) else []
    lines = [
        "[agent state]",
        f"goal: {str(state.get('goal') or '')[-1000:]}",
        f"current_step: {str(state.get('current_step') or '')[-500:]}",
        f"completed_steps: {', '.join(str(item) for item in completed[-20:])}",
        f"next_action: {str(state.get('next_action') or '')[-1000:]}",
    ]
    # Preserve structured state fields when a state store provides them. The
    # core execution fields above remain first so compaction keeps the task
    # identity and next step readable.
    for key in (
        "known_facts",
        "pending_tasks",
        "decisions",
        "constraints",
        "errors",
        "dependencies",
    ):
        value = state.get(key)
        if value:
            rendered = (
                value
                if isinstance(value, str)
                else ", ".join(str(item) for item in value)
            )
            lines.append(f"{key}: {rendered}")
    text = chr(10).join(lines)
    if max_chars is not None and len(text) > max_chars:
        suffix = chr(10) + "[agent state compacted]"
        text = text[: max(0, max_chars - len(suffix))] + suffix
    return text


def _inject_agent_state_context(messages: list[dict[str, Any]], core: Any) -> bool:
    """Inject recovered structured state into the current user turn."""
    policy = getattr(core, "context_policy", ContextPolicy.from_environment())
    if not policy.auto_state:
        return False
    get_state = getattr(core, "get_agent_state", None)
    if not callable(get_state):
        return False
    user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], dict)
            and messages[index].get("role") == "user"
        ),
        None,
    )
    if user_index is None:
        return False
    user_message = messages[user_index]
    content = user_message.get("content")
    if not isinstance(content, str) or not content.strip():
        return False
    if "[agent state]" in content:
        return False
    try:
        state = get_state()
    except Exception:
        return False
    if not isinstance(state, dict) or not any(state.values()):
        return False
    rendered_state = _format_agent_state_context(
        state,
        max_chars=(
            None
            if getattr(policy, "budget_unlimited", True)
            else min(10_000, int(getattr(policy, "budget_chars", 10_000)))
        ),
    )
    messages[user_index] = {
        **user_message,
        "content": rendered_state + chr(10) + chr(10) + content,
    }
    return True


def _update_agent_state_for_turn(messages: list[dict[str, Any]], core: Any) -> bool:
    """Persist the current user goal and active LLM step when available."""
    update = getattr(core, "update_agent_state", None)
    if not callable(update):
        return False
    user_message = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, dict) and message.get("role") == "user"
        ),
        None,
    )
    content = user_message.get("content") if user_message else ""
    if not isinstance(content, str) or not content.strip():
        return False
    try:
        current = getattr(core, "get_agent_state", lambda: None)() or {}
        changes: dict[str, Any] = {"current_step": "llm_round"}
        if not current.get("goal"):
            changes["goal"] = content[-4000:]
        update(**changes)
        return True
    except Exception:
        return False


def _inject_retrieved_tool_context(messages: list[dict[str, Any]], core: Any) -> bool:
    """Inject relevant persisted Tool Results into the current user turn."""
    policy = getattr(core, "context_policy", ContextPolicy.from_environment())
    if not policy.auto_retrieve:
        return False
    retrieve = getattr(core, "retrieve_tool_context", None)
    if not callable(retrieve):
        return False
    user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], dict)
            and messages[index].get("role") == "user"
        ),
        None,
    )
    if user_index is None:
        return False
    user_message = messages[user_index]
    content = user_message.get("content")
    if not isinstance(content, str) or not content.strip():
        return False
    if "[retrieved tool results]" in content:
        return False
    try:
        context = retrieve(content[-4000:], limit=5, max_chars=8000)
    except Exception:
        return False
    if not isinstance(context, str) or not context.strip():
        return False
    messages[user_index] = {
        **user_message,
        "content": f"{context}\n\n{content}",
    }
    return True


def _refresh_context_tool_specs(messages: list[dict[str, Any]], core: Any) -> None:
    """Refresh budgeted tool definitions after tool_load/unload operations."""
    context_manager = getattr(core, "context_manager", None)
    if context_manager is None:
        return
    try:
        from . import tools as _tools

        task_text = next(
            (
                str(message.get("content") or "")
                for message in reversed(messages)
                if isinstance(message, dict) and message.get("role") == "user"
            ),
            "",
        )
        tool_selection = context_manager.optimize_tool_definitions(
            _tools.get_tool_specs(),
            task=task_text,
        )
        core.context_tool_specs = tool_selection.specs
        core.context_tool_decisions = tool_selection.decisions
        core.context_tool_report = {
            "raw_chars": tool_selection.raw_chars,
            "active_chars": tool_selection.active_chars,
        }
        signature = hashlib.sha256(
            json.dumps(
                tool_selection.specs,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        previous_signature = getattr(core, "_context_tool_specs_signature", None)
        if previous_signature and previous_signature != signature:
            core._gemini_cache_needs_refresh = True
        core._context_tool_specs_signature = signature
    except Exception:
        core.context_tool_specs = None


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
    preserve_tool_loop_state: bool = False,
) -> str | None:
    global _TOTAL_ROUNDS, _PRODUCTIVE_ROUNDS, _TOOL_LAST_ROUND, _TOOL_AUTO_UNLOAD_ROUNDS, _TOOL_SPECS
    # Judgment mode: swap messages so all side effects go to judgment_messages
    if judgment_mode:
        if not judgment_messages:
            return ""
        messages = judgment_messages

    if not judgment_mode:
        core.context_policy = ContextPolicy.from_environment(
            provider=provider, model=depname
        )
        core.context_manager = ContextManager(policy=core.context_policy)
        try:
            raw_context_chars = sum(
                len(str(message.get("content") or ""))
                for message in messages
                if isinstance(message, dict)
            )
            _inject_agent_state_context(messages, core)
            _inject_retrieved_tool_context(messages, core)
            _update_agent_state_for_turn(messages, core)
            # Apply the budget after state/retrieval injection so recovered
            # context is governed by the same policy as the conversation.
            _apply_context_budget(messages, core)
            # Keep a provider-neutral snapshot as the single context
            # hand-off, without compacting a second time or changing tool
            # metadata/call pairing.
            active_context = core.context_manager.build_message_context(
                messages,
                budget=ContextBudget(
                    total_chars=max(
                        1,
                        sum(
                            len(str(message.get("content") or ""))
                            for message in messages
                            if isinstance(message, dict)
                        ),
                    )
                ),
            )
            core.active_context = active_context
            _record_context_telemetry(messages, core, raw_context_chars)
            if core.context_manager is not None:
                try:
                    from . import tools as _tools

                    task_text = next(
                        (
                            str(message.get("content") or "")
                            for message in reversed(messages)
                            if isinstance(message, dict)
                            and message.get("role") == "user"
                        ),
                        "",
                    )
                    tool_selection = core.context_manager.optimize_tool_definitions(
                        _TOOL_SPECS or _tools.get_tool_specs(),
                        task=task_text,
                    )
                    core.context_tool_specs = tool_selection.specs
                    core.context_tool_decisions = tool_selection.decisions
                    core.context_tool_report = {
                        "raw_chars": tool_selection.raw_chars,
                        "active_chars": tool_selection.active_chars,
                    }
                except Exception:
                    core.context_tool_specs = None
        except Exception:
            pass

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

    # A runaway model can otherwise spend a very long time issuing tool calls.
    # Keep the safety cap conservative, while allowing explicit override for
    # genuinely long workflows.
    try:
        max_tool_rounds = max(1, int(env_get("UAGENT_MAX_TOOL_ROUNDS", "200")))
    except (TypeError, ValueError):
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

    # Reset loop detection for a new user operation. Auto-Pilot invokes this
    # function once for each follow-up round, so those calls must preserve the
    # counters or a repeated tool_load can evade the runaway guard forever.
    if not preserve_tool_loop_state:
        _TOOL_CALL_FINGERPRINTS.clear()
        clear_consecutive_tool_call_streak()
        if provider in ("gemini", "vertexai"):
            core._gemini_tool_catalog_ready = False

    if judgment_mode:
        cache_mgr, gemini_cache_name = None, None
    else:
        cache_mgr, gemini_cache_name = _init_gemini_cache(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
            core=core,
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
                # Tool loading/unloading changes the active registry. Refresh
                # the provider tool surface before every request so a newly
                # loaded tool is available on the very next round.
                _refresh_context_tool_specs(messages, core)
                if provider in ("gemini", "vertexai") and getattr(
                    core, "_gemini_cache_needs_refresh", False
                ):
                    try:
                        if cache_mgr is not None:
                            cache_mgr.clear_cache(client)
                    except Exception:
                        pass
                    cache_mgr, gemini_cache_name = _init_gemini_cache(
                        provider=provider,
                        client=client,
                        depname=depname,
                        messages=messages,
                        core=core,
                    )
                    core._gemini_cache_needs_refresh = False

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
                    or resolve_tool_discovery(
                        provider=provider,
                        depname=depname,
                        use_responses_api=True,
                    ).uses_native_search
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
                            # An explicitly loaded tool is retained until it is
                            # used or explicitly unloaded. Unloading a tool
                            # that was never called makes tool_load appear to
                            # succeed while the next round silently removes it.
                            continue
                        age = _productive_age(last)
                        if age is not None and age >= threshold:
                            _spinner_stop_quietly()
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
