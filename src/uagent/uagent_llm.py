from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import sys
import time

from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from .translate import load_translate_config, translate_text
from typing import Any

try:
    import certifi
except Exception:
    certifi = None

from .llm_message_helpers import (
    _build_call_messages,
    build_auto_shrink_projection,
    build_structured_auto_shrink_projection,
    _init_gemini_cache,
)
from .runtime.context_manager import ContextManager
from .runtime.context_policy import ContextPolicy
from .runtime.sub_agent_receipt_context import ephemeral_receipt_context_round
from .runtime.memory_projection import (
    apply_memory_projection,
    memory_projection_access_is_current,
)
from .runtime.message_transform import MessageTransformPipeline
from .runtime.provider_context import project_messages_for_provider
from .runtime.provider_cache import plan_provider_cache
from .runtime.round_contracts import RoundSummary, RoundTransportSelection
from .llm_helpers import (
    _call_maybe_thread,
    _env_default_on,
    LLMWaitInterrupted,
)
from .llm_round_helpers import (
    _reconcile_system_prompt_for_route,
    _resolve_round_runtime_flags,
    _translate_assistant_if_needed,
)
from .providers.responses_runtime import (  # noqa: F401  (re-exported for tests)
    _responses_session_generation,
)
from .runtime.legacy_openai_round import call_legacy_openai_compatible_outcome
from .runtime.legacy_round_registry import run_legacy_provider_outcome
from .runtime.legacy_tool_continuation import execute_tool_continuation
from .providers.llm_deepseek import build_assistant_message_with_reasoning
from .providers.provider_caps import supports_generate_image_continuation
from .llm_flow_helpers import (
    _append_assistant_message,
    _emit_final_answer_if_any,
    _handle_openai_empty_no_tool,
    _resolve_empty_no_tool_max,
    _should_keep_assistant_message,
    _consume_empty_no_tool_recovery,
)
from . import core as _core_module
from .tools._tool_load_util import (
    _LOADED_SINGLE_TOOLS as _LOADED_SINGLE_TOOLS,
    disable_single_tool as _disable_single_tool,
    get_threshold as _get_threshold,
    bump_threshold as _bump_threshold,
    is_tool_pinned as _is_tool_pinned,
)
from .tools import TOOL_SPECS as _TOOL_SPECS
from .tools import _should_preload_lazy_specs
from .runtime.spinner import stop_quietly as _spinner_stop_quietly
from .runtime.telemetry import reconcile_usage
from .tools.context import get_callbacks
from .tools.skill_history import make_finish_skill_handler
from .tools.llm_tool_narrowing import (
    _is_gpt54_tool_search_target,  # noqa: F401  (re-exported for tests)
    resolve_tool_discovery,
    _select_tool_specs_legacy as _select_tool_specs_for_gpt54,  # noqa: F401  (re-exported for tests)
)

# Split-out parts of the round loop (re-exported for callers and tests).
from .llm_loop_guards import (  # noqa: F401
    _GENERAL_TOOL_LOOP_THRESHOLD,
    _MGMT_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
    _TOOL_ROUND_HISTORY_SIZE,
    _block_tool_loop,
    _clear_responses_after_tool_loop,
    _debug_tool_loop,
    _loop_guard_state,
    _parse_mgmt_tool_args,
    _tool_calls_include_name,
    begin_loop_guard_turn,
    check_consecutive_tool_calls,
    check_general_tool_loop,
    check_mgmt_tool_loop,
    check_repeating_tool_round_cycle,
    clear_consecutive_tool_call_streak,
    clear_general_tool_loop_streaks,
    clear_mgmt_load_streak,
)
from .llm_responses_runtime import (  # noqa: F401
    _apply_remote_recovery_update,
    _begin_responses_runtime,
    _record_responses_runtime_response,
    _sync_registry_responses_terminal,
    _sync_responses_runtime_completed,
)
from .llm_registry_round import (  # noqa: F401
    _select_registry_tool_specs,
    _try_registry_simple_chat_round,
)
from .llm_computer_use_nav import (  # noqa: F401
    _computer_use_enabled_for_current_execution,
    _maybe_navigate_computer_runtime,
)
from .llm_turn_context import (  # noqa: F401
    _apply_context_budget,
    _build_round_context_plan,
    _format_agent_state_context,
    _inject_agent_state_context,
    _inject_retrieved_tool_context,
    _persist_context_decision_log,
    _prepare_turn_context,
    _record_context_telemetry,
    _refresh_context_tool_specs,
    _resolve_max_tool_rounds,
    _update_agent_state_for_turn,
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


def _consume_post_response_interrupt(
    messages: list[dict[str, Any]],
    core: Any,
) -> bool:
    """Honour an interrupt that arrived while the provider call was running.

    Called after a provider response is collected and before its assistant
    message is stored or its tool calls run, so an interrupted round never
    executes tools or leaves unanswered tool calls in history. A Computer Use
    confirmation that just completed consumes the pending flag once (the
    confirmation dialog itself raised it).
    """
    confirmation_just_completed = bool(
        getattr(core, "computer_use_confirmation_just_completed", False)
    )
    if confirmation_just_completed:
        core.computer_use_confirmation_just_completed = False
    with _core_module.interrupt_lock:
        if not _core_module.interrupt_requested or confirmation_just_completed:
            return False
        _core_module.interrupt_requested = False
    core._last_round_reason = "interrupted"
    _inject_stop_prompt(messages, core)
    return True


def _interrupt_pending() -> bool:
    """Whether a Stop/F12 interrupt is waiting to be handled (not consumed)."""
    with _core_module.interrupt_lock:
        return bool(_core_module.interrupt_requested)


# --- Tool usage tracking for auto-unload ---
_TOOL_AUTO_UNLOAD_ROUNDS = int(
    env_get("UAGENT_AUTO_UNLOAD_ROUNDS", "10")
)  # unload after this many rounds without use


# The counters live in a ContextVar: each thread/copied context (e.g. one
# A2A task) tracks its own rounds, so parallel sessions cannot age each
# other's tools. Helpers that run tools via ``submit_with_current_context``
# share the current session's counters.
@dataclass
class _AutoUnloadState:
    last_round: dict[str, int] = field(
        default_factory=dict
    )  # tool_name -> last round used
    total_rounds: int = 0  # total rounds across all LLM calls, monotonically increasing
    # Rounds that actually executed the tool postamble (RS_OK). Empty/no-tool
    # continue rounds must not age auto-unload counters.
    productive_rounds: int = 0


_AUTO_UNLOAD_STATE: ContextVar[_AutoUnloadState | None] = ContextVar(
    "uagent_auto_unload_state", default=None
)


def _auto_unload_state() -> _AutoUnloadState:
    """Return the current conversation's auto-unload counters, creating them once."""
    state = _AUTO_UNLOAD_STATE.get()
    if state is None:
        state = _AutoUnloadState()
        _AUTO_UNLOAD_STATE.set(state)
    return state


def _owner_auto_unload_state(owner: object) -> _AutoUnloadState:
    """Return the auto-unload counters carried by ``owner``.

    On first sight the current context's state is adopted and stored on
    the owner, which also keeps processes that serve one conversation
    per context (CLI, pooled Web workers) on their ongoing state.
    """
    state = getattr(owner, "_auto_unload_state", None)
    if state is None:
        state = _auto_unload_state()
        try:
            owner._auto_unload_state = state  # type: ignore[attr-defined]
        except Exception:
            pass
    return state


def _bind_auto_unload_state(owner: object) -> _AutoUnloadState:
    """Bind the auto-unload counters carried by ``owner`` to this context.

    Web turns run in a fresh thread per message, which would otherwise
    reset the counters every turn. The room object outlives its turns,
    so it carries the state and each turn rebinds the stored object.
    """
    state = _owner_auto_unload_state(owner)
    _AUTO_UNLOAD_STATE.set(state)
    return state


@contextmanager
def _bound_auto_unload_state(owner: object) -> Iterator[_AutoUnloadState]:
    """Bind ``owner``'s auto-unload counters for the duration of the block.

    Web command handlers (e.g. ``:tools list``) run outside the worker
    thread that binds the room's state per turn; wrap them so they read
    the same counters the auto-unloader uses.
    """
    token = _AUTO_UNLOAD_STATE.set(_owner_auto_unload_state(owner))
    try:
        yield _AUTO_UNLOAD_STATE.get()
    finally:
        _AUTO_UNLOAD_STATE.reset(token)


def _productive_age(stamp: object, *, now: int | None = None) -> int | None:
    """Return age on the productive-round timeline.

    Stamps from the old TOTAL_ROUNDS timeline can be larger than the current
    productive clock; treat those as already expired by returning a huge age.
    """
    try:
        s = int(stamp)  # type: ignore[arg-type]
    except Exception:
        return None
    cur = _auto_unload_state().productive_rounds if now is None else int(now)
    if s > cur:
        return 10**9
    return cur - s


# Track repeated management-tool fingerprints to detect loops.
# Fingerprint is action + target (e.g. tool_load:file_grep), so loading
# several *different* tools in parallel is allowed. Only the same target
# repeated across rounds is treated as a loop (e.g. Grok reloading one tool).
# unload_tool(target) clears that target's tool_load counter so a later
# intentional reload is not counted as a continuation of the prior streak.
#
# Loop-guard state belongs to one conversation, not to the process. A2A runs
# concurrent Tasks as threads in a single process, so a module-global counter
# would let one Task trip (or reset) another Task's guard. The state therefore
# lives in a ContextVar: each thread/copied context sees its own object, while
# helpers that run tools via ``submit_with_current_context`` share it.


# --- Round status constants (internal) ---
_RS_RETURN = "return"  # fatal error, caller must return
_RS_BREAK = "break"  # stop loop, exit normally
_RS_CONTINUE = "continue"  # skip postamble, continue loop
_RS_OK = "ok"  # execute postamble then continue loop


def _public_round_status(
    round_status: str,
    *,
    reason: str,
    assistant_text: str,
) -> str:
    """Map internal loop control to the stable host-visible status vocabulary."""
    if reason in {"cancelled", "interrupted"}:
        return reason
    if reason in {"loop_guard", "max_tool_rounds", "error"}:
        return "failed"
    if round_status == _RS_RETURN:
        return "completed"
    if round_status == _RS_BREAK and assistant_text.strip():
        return "completed"
    if round_status in {_RS_CONTINUE, _RS_OK}:
        return "continue"
    return "failed"


def _completion_regex_matches(text: Any, pattern: Any) -> bool:
    """Return whether a configured completion regex matches assistant text."""
    raw_pattern = str(pattern or "").strip()
    if not raw_pattern:
        return False
    try:
        return re.search(raw_pattern, str(text or ""), flags=re.MULTILINE) is not None
    except re.error as exc:
        print(f"[WARN] Invalid --complete-regex: {exc}", file=sys.stderr, flush=True)
        return False


def _responses_tool_search_history_locked(
    *,
    provider: str,
    model_name: str,
    use_responses_api: bool,
    core: Any,
    messages: list[dict[str, Any]],
) -> bool:
    """Whether local context projection could invalidate deferred-search state."""
    provider_name = str(provider or "").strip().lower()
    if not use_responses_api or provider_name not in {"openrouter", "deepseek"}:
        return False
    if getattr(core, "_responses_tool_search_history_provider", None) == provider_name:
        return True

    if provider_name == "openrouter":
        try:
            from .runtime.tool_discovery import openrouter_responses_tool_search_variant

            if (
                openrouter_responses_tool_search_variant(provider_name, model_name)
                is None
            ):
                return False
        except Exception:
            return False
        return any(
            isinstance(message, dict)
            and message.get("role") == "assistant"
            and bool(message.get("tool_calls"))
            and isinstance(message.get("_responses_output_items"), list)
            and bool(message.get("_responses_output_items"))
            for message in messages
        )

    return any(
        isinstance(message, dict)
        and message.get("role") == "assistant"
        and any(
            isinstance(item, dict) and item.get("type") == "tool_search_call"
            for item in (message.get("_responses_output_items") or [])
        )
        for message in messages
    )


def _record_round_context_plan(
    *, provider: str, depname: str, call_messages: list[dict[str, Any]], core: Any
) -> Any | None:
    """Build and return the provider-neutral plan for this round."""
    if not _env_default_on("UAGENT_ROUND_CONTRACTS") and not isinstance(
        getattr(core, "context_manager", None), ContextManager
    ):
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


@dataclass(frozen=True)
class _RoundOutcome:
    """Terminal outcome of one LLM round.

    status is one of the _RS_* constants; the caller (run_llm_rounds)
    dispatches on it. client / gemini_cache_name / empty_no_tool_rounds
    carry the round's updated values back to the caller's loop state.
    """

    status: str
    client: Any
    gemini_cache_name: str | None
    empty_no_tool_rounds: int
    assistant_text: str


@dataclass
class _RoundContext:
    """Inputs and cross-phase state for one LLM round.

    _run_one_round is split into _prepare_round (preamble),
    _dispatch_round (provider dispatch) and _execute_round_tools
    (postamble: tool execution). Values that only one phase uses stay
    local to that phase; everything the phases share lives here.
    """

    provider: str
    client: Any
    depname: str
    messages: list[dict[str, Any]]
    core: Any
    make_client_fn: Any
    append_result_to_outfile_fn: Any
    try_open_images_from_text_fn: Any
    round_count: int
    max_tool_rounds: int
    empty_no_tool_rounds: int
    empty_no_tool_max: int
    cache_mgr: Any
    gemini_cache_name: str | None
    use_llm_thread: bool
    judgment_mode: bool = False
    tool_round_history: deque[tuple[tuple[str, str], ...]] | None = None
    consecutive_tool_streak: dict[str, Any] | None = None
    # Cross-phase state, filled in by _prepare_round / _dispatch_round.
    assistant_text: str = ""
    reasoning_content: str = ""
    tool_calls_list: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = False
    dispatch: Any = None
    registry_simple_result: Any = None
    stream_responses: bool = False
    use_responses_api: bool = False
    round_supports_tool_continuation: bool = False
    clear_continuation: Any = None


def _round_outcome(
    ctx: _RoundContext, status: str, assistant_text: str
) -> _RoundOutcome:
    return _RoundOutcome(
        status=status,
        client=ctx.client,
        gemini_cache_name=ctx.gemini_cache_name,
        empty_no_tool_rounds=ctx.empty_no_tool_rounds,
        assistant_text=assistant_text,
    )


def _prepare_round(ctx: _RoundContext) -> _RoundOutcome | None:
    """Preamble: interrupt / memory checks, message building, planning.

    Returns a _RoundOutcome when the round ends here, else None.
    """
    # ── Preamble ──────────────────────────────────────────────────

    # --- Interrupt check: per-round ---
    with _core_module.interrupt_lock:
        if _core_module.interrupt_requested:
            _core_module.interrupt_requested = False
            ctx.core._last_round_reason = "interrupted"
            _inject_stop_prompt(ctx.messages, ctx.core)
            return _round_outcome(ctx, _RS_BREAK, "")

    # Optional translation layer (off by default).
    tr_cfg = load_translate_config()
    if ctx.judgment_mode:
        tr_cfg = None  # judgment prompt is English; skip translate

    memory_snapshot = getattr(ctx.core, "memory_projection_snapshot", None)
    if not ctx.judgment_mode and not memory_projection_access_is_current(
        memory_snapshot, ctx.core
    ):
        ctx.core._last_round_reason = "memory_access_changed"
        ctx.core._memory_projection_invalidated = True
        _clear_responses_after_tool_loop(ctx.core, reason="memory_access_changed")
        return _round_outcome(ctx, _RS_BREAK, "")

    call_messages = _build_call_messages(
        provider=ctx.provider,
        messages=ctx.messages,
        core=ctx.core,
        depname=ctx.depname,
        gemini_cache_name=ctx.gemini_cache_name,
    )
    call_messages = apply_memory_projection(
        call_messages,
        (
            getattr(ctx.core, "memory_projection_snapshot", None)
            if not ctx.judgment_mode
            else None
        ),
        ctx.core,
    )
    if not ctx.judgment_mode and not memory_projection_access_is_current(
        memory_snapshot, ctx.core
    ):
        ctx.core._last_round_reason = "memory_access_changed"
        ctx.core._memory_projection_invalidated = True
        _clear_responses_after_tool_loop(ctx.core, reason="memory_access_changed")
        return _round_outcome(ctx, _RS_BREAK, "")

    def _call_maybe_thread_fn(fn: Any) -> Any:
        return _call_maybe_thread(fn, use_llm_thread=ctx.use_llm_thread)

    ctx.use_responses_api, ctx.stream_responses = _resolve_round_runtime_flags(
        tr_cfg=tr_cfg,
        core=ctx.core,
        provider=ctx.provider,
        depname=ctx.depname,
    )

    transport_selection = RoundTransportSelection.from_flags(
        use_responses_api=ctx.use_responses_api,
        stream_responses=ctx.stream_responses,
    )

    # OpenRouter's native deferred-tool state is signed against the full
    # Responses history; DeepSeek requires its tool_search_call/output loading
    # records to be replayed as well. Once such a turn exists, local context
    # projections must not remove or rewrite earlier messages.
    responses_search_history_locked = _responses_tool_search_history_locked(
        provider=ctx.provider,
        model_name=ctx.depname,
        use_responses_api=ctx.use_responses_api,
        core=ctx.core,
        messages=ctx.messages,
    )

    # Build an optional LLM-summary projection before context selection. This
    # keeps auto-shrink on the same ContextPlan -> Projection path as the
    # uncompressed request and avoids rebuilding context after planning.
    _using_prev_rid = bool(ctx.core.responses_state.get("previous_response_id"))
    if ctx.use_responses_api:
        from .providers.responses_manager import get_responses_capabilities

        if not get_responses_capabilities(ctx.provider).previous_response_id:
            state = getattr(ctx.core, "responses_state", None)
            if isinstance(state, dict):
                had_previous_id = state.pop("previous_response_id", None) is not None
                state.pop("_stale_rid_occurred", None)
                if had_previous_id:
                    try:
                        from .core import _save_responses_state

                        _save_responses_state()
                    except Exception:
                        pass
            runtime = getattr(ctx.core, "responses_runtime", None)
            ctx.clear_continuation = getattr(runtime, "clear_continuation", None)
            if callable(ctx.clear_continuation):
                ctx.clear_continuation("unsupported_continuation")
            _using_prev_rid = False
    projection_changed = False
    structured_projection = None
    # A new user turn is the safe boundary for a durable checkpoint. Tool
    # continuation rounds must preserve their pending call_id/response_id chain.
    if (
        not ctx.judgment_mode
        and not responses_search_history_locked
        and ctx.messages
        and ctx.messages[-1].get("role") in {"user", "tool"}
    ):
        structured_projection = build_structured_auto_shrink_projection(
            provider=ctx.provider,
            client=ctx.client,
            depname=ctx.depname,
            messages=ctx.messages,
            core=ctx.core,
            cache_mgr=ctx.cache_mgr,
            gemini_cache_name=ctx.gemini_cache_name,
            call_maybe_thread_fn=_call_maybe_thread_fn,
            use_responses_api=ctx.use_responses_api,
            previous_response_id=_using_prev_rid,
            allow_checkpoint_creation=ctx.messages[-1].get("role") == "user",
        )
    if structured_projection is not None:
        # A locally shortened request cannot continue a server-held response
        # that still contains the uncompressed history.
        if _using_prev_rid:
            _clear_responses_after_tool_loop(ctx.core, reason="structured_compaction")
            _using_prev_rid = False
        projection_changed = True
        ctx.gemini_cache_name = structured_projection.cache_name
        call_messages = _build_call_messages(
            provider=ctx.provider,
            messages=list(structured_projection.messages),
            core=ctx.core,
            depname=ctx.depname,
            gemini_cache_name=ctx.gemini_cache_name,
        )
        call_messages = apply_memory_projection(
            call_messages,
            getattr(ctx.core, "memory_projection_snapshot", None),
            ctx.core,
        )
    elif (
        not ctx.judgment_mode
        and not _using_prev_rid
        and not responses_search_history_locked
    ):
        auto_shrink_projection = build_auto_shrink_projection(
            provider=ctx.provider,
            client=ctx.client,
            depname=ctx.depname,
            messages=ctx.messages,
            core=ctx.core,
            cache_mgr=ctx.cache_mgr,
            gemini_cache_name=ctx.gemini_cache_name,
            call_maybe_thread_fn=_call_maybe_thread_fn,
            use_responses_api=ctx.use_responses_api,
        )
        if auto_shrink_projection.changed:
            projection_changed = True
            ctx.gemini_cache_name = auto_shrink_projection.cache_name
            call_messages = _build_call_messages(
                provider=ctx.provider,
                messages=list(auto_shrink_projection.messages),
                core=ctx.core,
                depname=ctx.depname,
                gemini_cache_name=ctx.gemini_cache_name,
            )
            call_messages = apply_memory_projection(
                call_messages,
                getattr(ctx.core, "memory_projection_snapshot", None),
                ctx.core,
            )

    if not ctx.judgment_mode and not responses_search_history_locked:
        context_manager = getattr(ctx.core, "context_manager", None)
        build_message_context = getattr(context_manager, "build_message_context", None)
        if callable(build_message_context):
            session_store = getattr(ctx.core, "session_store", None)
            session_id = getattr(ctx.core, "_session_store_active_id", None) or getattr(
                ctx.core, "session_id", None
            )
            if session_store is not None and session_id:
                active_context = build_message_context(
                    call_messages,
                    session_store=session_store,
                    session_id=str(session_id),
                )
            else:
                active_context = build_message_context(call_messages)
            ctx.core.active_context = active_context
            _persist_context_decision_log(active_context, ctx.core)
            call_messages = active_context.messages
    if not ctx.judgment_mode and not responses_search_history_locked:
        round_plan = _record_round_context_plan(
            provider=ctx.provider,
            depname=ctx.depname,
            call_messages=call_messages,
            core=ctx.core,
        )
        if round_plan is not None:
            call_messages = [dict(message) for message in round_plan.messages]
    # Realign the prompt with this round's route before any transform
    # rewrites the system text: with translation on, the semantic
    # transform translates the system entry, so a reconcile after it
    # would no longer recognize the entry and would miss the outgoing
    # copy while still swapping the stored one.
    _reconcile_system_prompt_for_route(
        call_messages,
        ctx.messages,
        ctx.core,
        provider=ctx.provider,
        depname=ctx.depname,
        use_responses_api=ctx.use_responses_api,
    )
    call_messages = _apply_semantic_message_transforms(call_messages, tr_cfg)
    call_messages = project_messages_for_provider(
        call_messages,
        provider=ctx.provider,
        model=ctx.depname,
        preserve_responses_output_items=(
            ctx.use_responses_api and ctx.provider in {"openrouter", "deepseek"}
        ),
    )

    _begin_responses_runtime(
        core=ctx.core,
        provider=ctx.provider,
        model=ctx.depname,
        enabled=(transport_selection.use_responses_api and not ctx.judgment_mode),
        transport_selection=transport_selection,
    )

    cache_plan = plan_provider_cache(
        provider=ctx.provider,
        model=ctx.depname,
        projection_changed=projection_changed,
        previous_response_id=_using_prev_rid,
    )
    try:
        ctx.core.provider_cache_plan = cache_plan.to_dict()
    except Exception:
        pass

    if ctx.round_count > ctx.max_tool_rounds:
        # A hard tool-round stop can leave the provider cache paired with the
        # last assistant tool turn. Rebuild Gemini/Vertex cache state before a
        # later user continuation rather than reusing that stale turn.
        if ctx.provider in ("gemini", "vertexai"):
            try:
                ctx.core._gemini_cache_needs_refresh = True
            except Exception:
                pass
        ctx.core._last_round_reason = "max_tool_rounds"
        _clear_responses_after_tool_loop(ctx.core, reason="tool_round_limit")
        _spinner_stop_quietly()
        print(
            _("[WARN] Tool rounds exceeded %(max)d; aborting.")
            % {"max": ctx.max_tool_rounds}
        )
        return _round_outcome(ctx, _RS_BREAK, "")

    send_tools_this_round = getattr(_core_module, "tools_enabled", True)
    from .runtime.execution_broker import (
        SecurityProfile,
        current_profile,
        current_sandbox_enabled,
    )

    if current_profile() is SecurityProfile.REMOTE and not current_sandbox_enabled():
        # Remote tools are sent only when the ingress is bound to an enabled
        # sandbox. The common dispatcher still rejects any unsolicited calls.
        send_tools_this_round = False
    # The isolated LM Studio SDK adapter can reuse the normal uagent tool
    # executor without importing this module at provider-import time.
    try:
        ctx.core._lmstudio_sdk_messages = ctx.messages
        ctx.core._lmstudio_sdk_cache_mgr = ctx.cache_mgr
    except Exception:
        pass
    if ctx.judgment_mode:
        send_tools_this_round = False
    max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
    retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
    retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

    ctx.tool_calls_list: list[dict[str, Any]] = []
    ctx.assistant_text: str = ""

    from .runtime.provider_round_dispatcher import (
        RegistryRoundRoute,
        dispatch_provider_round,
        resolve_registry_round_route,
    )

    registry_discovery = None
    registry_route = None
    if not ctx.judgment_mode:
        try:
            registry_discovery = resolve_tool_discovery(
                provider=ctx.provider,
                depname=ctx.depname,
                use_responses_api=True,
            )
            registry_route = resolve_registry_round_route(
                provider=ctx.provider,
                configured_providers=env_get("UAGENT_PROVIDER_REGISTRY", "") or "",
                use_responses_api=ctx.use_responses_api,
                responses_enabled=_env_default_on("UAGENT_PROVIDER_REGISTRY_RESPONSES"),
                send_tools=bool(send_tools_this_round),
                tools_enabled=_env_default_on("UAGENT_PROVIDER_REGISTRY_TOOLS"),
                has_context_tools=bool(getattr(ctx.core, "context_tool_specs", None)),
                uses_legacy_catalog=(
                    ctx.use_responses_api and registry_discovery.uses_legacy_catalog
                ),
                transport_selection=transport_selection,
                model_name=ctx.depname,
            )
        except Exception:
            # The registry route is advisory until all providers are migrated.
            # Let the compatibility runner retain its own safety gate.
            registry_route = None
    try:
        from .runtime.tool_discovery import provider_messages_api_enabled

        if provider_messages_api_enabled(ctx.provider):
            registry_route = RegistryRoundRoute(False, "messages_api_selected")
    except Exception:
        pass

    ctx.dispatch = dispatch_provider_round(
        registry_runner=_try_registry_simple_chat_round,
        registry_allowed=not ctx.judgment_mode,
        registry_route=registry_route,
        legacy_runner=run_legacy_provider_outcome,
        openai_runner=call_legacy_openai_compatible_outcome,
        registry_kwargs={
            "provider": ctx.provider,
            "client": ctx.client,
            "depname": ctx.depname,
            "call_messages": call_messages,
            "core": ctx.core,
            "use_responses_api": ctx.use_responses_api,
            "stream_responses": ctx.stream_responses,
            "transport_selection": transport_selection,
            "send_tools_this_round": bool(send_tools_this_round),
            "round_count": ctx.round_count,
            "registry_route": registry_route,
            "tool_discovery": registry_discovery,
        },
        legacy_kwargs={
            "provider": ctx.provider,
            "client": ctx.client,
            "depname": ctx.depname,
            "call_messages": call_messages,
            "messages": ctx.messages,
            "gemini_cache_name": ctx.gemini_cache_name,
            "cache_mgr": ctx.cache_mgr,
            "core": ctx.core,
            "make_client_fn": ctx.make_client_fn,
            "call_maybe_thread_fn": _call_maybe_thread_fn,
            "append_result_to_outfile_fn": ctx.append_result_to_outfile_fn,
            "try_open_images_from_text_fn": ctx.try_open_images_from_text_fn,
            "empty_no_tool_rounds": ctx.empty_no_tool_rounds,
            "empty_no_tool_max": ctx.empty_no_tool_max,
            "tr_cfg": tr_cfg,
            "use_responses_api": ctx.use_responses_api,
            "stream_responses": ctx.stream_responses,
            "send_tools_this_round": send_tools_this_round,
            "max_retries_429": max_retries_429,
            "retry_base": retry_base,
            "retry_cap": retry_cap,
            "judgment_mode": ctx.judgment_mode,
            "inject_stop_prompt_fn": _inject_stop_prompt,
            "translate_assistant_fn": _translate_assistant_if_needed,
            "should_keep_assistant_message_fn": _should_keep_assistant_message,
            "append_assistant_message_fn": _append_assistant_message,
            "handle_empty_no_tool_fn": _handle_openai_empty_no_tool,
            "emit_final_answer_fn": _emit_final_answer_if_any,
        },
        openai_kwargs={
            "provider": ctx.provider,
            "client": ctx.client,
            "depname": ctx.depname,
            "call_messages": call_messages,
            "core": ctx.core,
            "make_client_fn": ctx.make_client_fn,
            "call_maybe_thread_fn": _call_maybe_thread_fn,
            "use_responses_api": ctx.use_responses_api,
            "stream_responses": ctx.stream_responses,
            "send_tools_this_round": send_tools_this_round,
            "max_retries_429": max_retries_429,
            "retry_base": retry_base,
            "retry_cap": retry_cap,
            "messages": ctx.messages,
            "responses_state": ctx.core.responses_state,
            "round_count": ctx.round_count,
        },
    )
    if ctx.dispatch.source != "registry":
        _sync_responses_runtime_completed(
            core=ctx.core,
            enabled=ctx.use_responses_api and not ctx.judgment_mode,
            round_outcome=ctx.dispatch.outcome,
        )
    ctx.registry_simple_result = (
        ctx.dispatch.outcome.raw_result
        if ctx.dispatch.handles_collected_result
        else None
    )
    ctx.round_supports_tool_continuation = False
    if ctx.registry_simple_result is not None:
        ctx.ok, ctx.assistant_text, ctx.reasoning_content, ctx.tool_calls_list = (
            ctx.registry_simple_result
        )
        ctx.round_supports_tool_continuation = ctx.dispatch.supports_tool_continuation
        if not ctx.ok:
            ctx.core._last_round_reason = "error"
            return _round_outcome(ctx, _RS_RETURN, ctx.assistant_text)
        responses_output_items = getattr(ctx.core, "_last_responses_output_items", None)
        # Same boundary as the OpenAI-compatible path: an interrupt that
        # arrived during the provider call must win before any tool runs.
        if _consume_post_response_interrupt(ctx.messages, ctx.core):
            return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)
        if not ctx.round_supports_tool_continuation:
            ctx.assistant_text = _translate_assistant_if_needed(
                assistant_text=ctx.assistant_text,
                tr_cfg=tr_cfg,
                use_responses_api=ctx.use_responses_api,
                stream_responses=ctx.stream_responses,
                stream_output_rendered=False,
            )
            # Store the final answer in the conversation like the legacy path
            # does; without this the next turn never sees the reply.
            if _should_keep_assistant_message(ctx.assistant_text, ctx.tool_calls_list):
                _append_assistant_message(
                    messages=ctx.messages,
                    core=ctx.core,
                    assistant_text=ctx.assistant_text,
                    tool_calls_list=ctx.tool_calls_list,
                    responses_output_items=responses_output_items,
                )
            if not ctx.judgment_mode:
                _emit_final_answer_if_any(
                    assistant_text=ctx.assistant_text,
                    use_responses_api=ctx.use_responses_api,
                    stream_responses=ctx.stream_responses,
                    append_result_to_outfile_fn=ctx.append_result_to_outfile_fn,
                    try_open_images_from_text_fn=ctx.try_open_images_from_text_fn,
                    reasoning_content=ctx.reasoning_content,
                    # Registry text deltas have already been rendered by the
                    # event observer. Avoid printing the collected answer a
                    # second time, while still recording it and opening media.
                    skip_print=bool(
                        getattr(ctx.core, "_registry_stream_output_rendered", False)
                    ),
                    render_reasoning_when_skip_print=bool(
                        getattr(ctx.core, "_registry_stream_output_rendered", False)
                    ),
                    stream_output_rendered=False,
                    core=ctx.core,
                    provider=ctx.provider,
                )
            return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)
        if _should_keep_assistant_message(ctx.assistant_text, ctx.tool_calls_list):
            _append_assistant_message(
                messages=ctx.messages,
                core=ctx.core,
                assistant_text=ctx.assistant_text,
                tool_calls_list=ctx.tool_calls_list,
                responses_output_items=responses_output_items,
            )
        ctx.empty_no_tool_rounds = 0


def _dispatch_round(ctx: _RoundContext) -> _RoundOutcome | None:
    """Provider dispatch: registry / legacy / OpenAI-compatible paths.

    Returns a _RoundOutcome when the round ends here, else None.
    """
    # ── Provider dispatch ─────────────────────────────────────────

    if ctx.registry_simple_result is not None:
        pass
    else:
        legacy_round_result = (
            ctx.dispatch.outcome if ctx.dispatch.owns_tool_execution else None
        )
        if legacy_round_result is not None:
            return _RoundOutcome(*legacy_round_result.raw_result)
        openai_round_result = ctx.dispatch.outcome
        (
            ctx.ok,
            ctx.client,
            ctx.assistant_text,
            ctx.reasoning_content,
            ctx.tool_calls_list,
            _is_xai_grpc,
        ) = openai_round_result.raw_result
        ctx.round_supports_tool_continuation = ctx.dispatch.supports_tool_continuation
        if not ctx.ok:
            ctx.core._last_round_reason = "error"
            return _round_outcome(ctx, _RS_RETURN, ctx.assistant_text)

        # Preserve native Responses output items (including reasoning items)
        # for full-history fallback and tool-call continuation.
        responses_output_items = getattr(ctx.core, "_last_responses_output_items", None)

        if _consume_post_response_interrupt(ctx.messages, ctx.core):
            return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)

        if _should_keep_assistant_message(ctx.assistant_text, ctx.tool_calls_list):
            if ctx.reasoning_content:
                deepseek_msg = build_assistant_message_with_reasoning(
                    assistant_text=ctx.assistant_text,
                    tool_calls_list=ctx.tool_calls_list,
                    reasoning_content=ctx.reasoning_content,
                )
                if str(ctx.provider or "").strip().lower() == "sarashina":
                    # Store Sarashina's encrypted token under its native field.
                    # The web display projection intentionally does not expose
                    # this field, while provider replay preserves it verbatim.
                    deepseek_msg["reasoning"] = deepseek_msg.pop("reasoning_content")
                if isinstance(responses_output_items, list) and responses_output_items:
                    deepseek_msg["_responses_output_items"] = responses_output_items
                ctx.messages.append(deepseek_msg)
                if not ctx.judgment_mode:
                    ctx.core.log_message(deepseek_msg)
            else:
                _append_assistant_message(
                    messages=ctx.messages,
                    core=ctx.core,
                    assistant_text=ctx.assistant_text,
                    tool_calls_list=ctx.tool_calls_list,
                    responses_output_items=responses_output_items,
                )

        action, ctx.empty_no_tool_rounds = _handle_openai_empty_no_tool(
            assistant_text=ctx.assistant_text,
            tool_calls_list=ctx.tool_calls_list,
            empty_no_tool_rounds=ctx.empty_no_tool_rounds,
            empty_no_tool_max=ctx.empty_no_tool_max,
            provider=ctx.provider,
            depname=ctx.depname,
            messages=ctx.messages,
            core=ctx.core,
        )
        if not ctx.tool_calls_list:
            if ctx.tool_round_history is not None:
                ctx.tool_round_history.clear()
            clear_consecutive_tool_call_streak(ctx.consecutive_tool_streak)
        if action == "continue":
            return _round_outcome(ctx, _RS_CONTINUE, ctx.assistant_text)
        if action == "break":
            return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)

        if not ctx.round_supports_tool_continuation:
            if not ctx.judgment_mode:
                # Host-rendering capability controls duplicate final output.
                _emit_final_answer_if_any(
                    assistant_text=ctx.assistant_text,
                    reasoning_content=ctx.reasoning_content,
                    use_responses_api=ctx.use_responses_api,
                    stream_responses=ctx.stream_responses,
                    append_result_to_outfile_fn=ctx.append_result_to_outfile_fn,
                    try_open_images_from_text_fn=ctx.try_open_images_from_text_fn,
                    skip_print=ctx.dispatch.host_rendered,
                    core=ctx.core,
                    provider=ctx.provider,
                )
            return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)

        ctx.empty_no_tool_rounds = 0


def _execute_round_tools(ctx: _RoundContext) -> _RoundOutcome:
    """Postamble: append the assistant message and execute tool calls."""
    # ── Postamble: tool execution ────────────────────────────────

    if ctx.judgment_mode:
        return _round_outcome(ctx, _RS_OK, ctx.assistant_text)

    _debug_tool_loop(
        "received",
        provider=ctx.provider,
        count=len(ctx.tool_calls_list),
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
            for tc in ctx.tool_calls_list
            if isinstance(tc, dict)
        ],
    )
    response_tool_continuation = bool(
        ctx.use_responses_api and ctx.round_supports_tool_continuation
    )
    _record_responses_runtime_response(
        core=ctx.core,
        enabled=response_tool_continuation,
        tool_calls=ctx.tool_calls_list,
    )
    disallowed_tool_names: frozenset[str] = frozenset()
    if ctx.provider in {"gemini", "vertexai"}:
        try:
            from .runtime.tool_discovery import (
                MANAGEMENT_TOOL_NAMES,
                gemini_interactions_tool_retrieval_enabled,
            )

            if gemini_interactions_tool_retrieval_enabled(ctx.provider, ctx.depname):
                # These management functions are deliberately absent from the
                # Gemini Tool Retrieval request. Reject a model-emitted or
                # history-replayed call as well; never execute an unadvertised
                # catalog/load/unload function on this route.
                disallowed_tool_names = MANAGEMENT_TOOL_NAMES
        except Exception:
            pass
    executed_new_tool, fresh_tool_calls = execute_tool_continuation(
        tool_calls_list=ctx.tool_calls_list,
        messages=ctx.messages,
        core=ctx.core,
        cache_mgr=ctx.cache_mgr,
        responses_api_continuation=response_tool_continuation,
        responses_runtime=getattr(ctx.core, "responses_runtime", None),
        disallowed_tool_names=disallowed_tool_names,
    )
    if bool(getattr(ctx.core, "_session_resume_control_transfer", False)):
        try:
            ctx.core._session_resume_control_transfer = False
        except Exception:
            pass
        ctx.core._last_round_reason = "session_resume"
        return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)
    if ctx.provider in ("gemini", "vertexai") and any(
        isinstance(tc, dict)
        and (tc.get("function") or {}).get("name") == "tool_catalog"
        for tc in fresh_tool_calls
    ):
        # Only a successful catalog call completes the Gemini discovery
        # boundary. Other tool calls must not silently skip discovery later.
        ctx.core._gemini_tool_catalog_ready = True
    # Record actual execution, not only the assistant message shape. Some
    # providers normalize tool calls differently, which previously caused a
    # genuinely used tool to look idle to the auto-unloader.
    _au_state = _auto_unload_state()
    next_productive_round = _au_state.productive_rounds + 1
    for _tc in fresh_tool_calls:
        if not isinstance(_tc, dict):
            continue
        _name = str((_tc.get("function") or {}).get("name") or "").strip()
        if _name:
            _au_state.last_round[_name] = next_productive_round
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

    if not supports_generate_image_continuation(ctx.provider) and any(
        isinstance(tc, dict)
        and (tc.get("function") or {}).get("name") == "generate_image"
        for tc in ctx.tool_calls_list
    ):
        # This path intentionally terminates the Responses tool continuation:
        # the provider cannot safely continue after generate_image. Clear the
        # server-side response id here, at the orchestration boundary, so the
        # next user turn starts from the local history instead of reusing an
        # incomplete response chain.
        try:
            ctx.clear_continuation = getattr(
                ctx.core, "clear_responses_continuation", None
            )
            if callable(ctx.clear_continuation):
                ctx.clear_continuation()
        except Exception:
            pass
        return _round_outcome(ctx, _RS_BREAK, ctx.assistant_text)

    # Re-check before the next LLM call.

    ctx.core.set_status(True, "LLM")

    # Detect repeated same-target management tool calls.
    # Parallel tool_load of different tools is allowed; only the same target
    # (e.g. tool_load(file_grep) x4) across rounds is treated as a loop.
    # unload_tool(target) clears that target's load streak first.
    if ctx.tool_calls_list and not ctx.judgment_mode:
        # Re-planning via tool_catalog starts a fresh general-tool streak.
        if _tool_calls_include_name(ctx.tool_calls_list, "tool_catalog"):
            clear_general_tool_loop_streaks()

        _rs_break = (
            _RS_BREAK,
            ctx.client,
            ctx.gemini_cache_name,
            ctx.empty_no_tool_rounds,
            ctx.assistant_text,
        )
        blocked, blocked_name, blocked_count = check_mgmt_tool_loop(ctx.tool_calls_list)
        if blocked:
            _block_tool_loop(
                core=ctx.core,
                tool_name=blocked_name,
                count=blocked_count,
                reason="management_tool_repeat",
                round_count=ctx.round_count,
                tool_calls_list=ctx.tool_calls_list,
                warning=_(
                    "[WARN] Management tool call '%(name)s' repeated %(n)d times; "
                    "aborting to prevent loop."
                )
                % {"name": blocked_name, "n": blocked_count},
            )
            return _rs_break

        # Exact tool+argument repeats are the narrowest loop signal.
        blocked, blocked_name, blocked_count = check_general_tool_loop(fresh_tool_calls)
        if blocked:
            _block_tool_loop(
                core=ctx.core,
                tool_name=blocked_name,
                count=blocked_count,
                reason="same_arguments",
                round_count=ctx.round_count,
                tool_calls_list=fresh_tool_calls,
                warning=_(
                    "[WARN] Tool call '%(name)s' repeated %(n)d times with the same "
                    "arguments; aborting to prevent loop."
                )
                % {"name": blocked_name, "n": blocked_count},
            )
            return _rs_break

        # Match short, exact cycles such as search_web -> read_file repeated
        # three times. Only digests are retained; argument values are not logged.
        cycle_blocked, cycle_names, cycle_length = check_repeating_tool_round_cycle(
            fresh_tool_calls,
            history=ctx.tool_round_history,
        )
        if cycle_blocked:
            cycle_label = " -> ".join("+".join(names) for names in cycle_names)
            cycle_rounds = cycle_length * 3
            _block_tool_loop(
                core=ctx.core,
                tool_name=f"cycle:{cycle_label}",
                count=cycle_rounds,
                reason="repeating_tool_cycle",
                round_count=ctx.round_count,
                tool_calls_list=fresh_tool_calls,
                clear_reason="repeating_tool_cycle",
                warning=_(
                    "[WARN] Tool-call cycle %(cycle)s repeated 3 times across %(n)d rounds; aborting."
                )
                % {
                    "cycle": json.dumps(cycle_label, ensure_ascii=False),
                    "n": cycle_rounds,
                },
            )
            return _rs_break

        # A per-tool-name streak is a secondary guard for varying arguments.
        # Mixed-tool rounds reset it; UAGENT_MAX_TOOL_ROUNDS remains the final
        # limit.
        blocked, blocked_name, blocked_count = check_consecutive_tool_calls(
            fresh_tool_calls, streak=ctx.consecutive_tool_streak
        )
        if blocked:
            _block_tool_loop(
                core=ctx.core,
                tool_name=blocked_name,
                count=blocked_count,
                reason="consecutive_tool_calls",
                round_count=ctx.round_count,
                tool_calls_list=fresh_tool_calls,
                warning=_(
                    "[WARN] Tool '%(name)s' appeared in %(n)d consecutive rounds; aborting."
                )
                % {"name": blocked_name, "n": blocked_count},
            )
            return _rs_break

    elif not ctx.judgment_mode:
        # A no-tool response breaks every consecutive-tool loop signal.
        ctx.tool_round_history.clear()
        clear_consecutive_tool_call_streak(ctx.consecutive_tool_streak)

    return _round_outcome(ctx, _RS_OK, ctx.assistant_text)


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
    tool_round_history: deque[tuple[tuple[str, str], ...]] | None = None,
    consecutive_tool_streak: dict[str, Any] | None = None,
) -> _RoundOutcome:
    """Run a single LLM round.

    Returns a _RoundOutcome. Caller dispatches on status:
      RS_RETURN   → return from run_llm_rounds
      RS_BREAK    → break while loop
      RS_CONTINUE → continue while loop (skip postamble)
      RS_OK       → execute postamble, then continue loop
    When judgment_mode=True, tool execution is suppressed and side effects
    (log, outfile, image open) are skipped. Only the assistant text is returned.
    """
    if tool_round_history is None:
        tool_round_history = deque(maxlen=_TOOL_ROUND_HISTORY_SIZE)
    if consecutive_tool_streak is None:
        consecutive_tool_streak = _loop_guard_state().consecutive

    ctx = _RoundContext(
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
        tool_round_history=tool_round_history,
        consecutive_tool_streak=consecutive_tool_streak,
    )
    outcome = _prepare_round(ctx)
    if outcome is not None:
        return outcome
    outcome = _dispatch_round(ctx)
    if outcome is not None:
        return outcome
    return _execute_round_tools(ctx)


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


@ephemeral_receipt_context_round
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
    global _TOOL_AUTO_UNLOAD_ROUNDS, _TOOL_SPECS
    # Judgment mode: swap messages so all side effects go to judgment_messages
    if judgment_mode:
        if not judgment_messages:
            return ""
        messages = judgment_messages

    # Drop a stale interrupt left over from before this turn. Do it before the
    # turn preparation below: a Stop pressed while the turn is being prepared
    # must survive until the first round checks it, instead of being cleared
    # and letting the LLM call run to completion.
    with _core_module.interrupt_lock:
        _core_module.interrupt_requested = False

    if not judgment_mode:
        core.context_policy = ContextPolicy.from_environment(
            provider=provider, model=depname
        )
        core.context_manager = ContextManager(policy=core.context_policy)
        _prepare_turn_context(messages, core)

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
            _computer_use_enabled = _computer_use_enabled_for_current_execution(
                core, policy
            )
            if _computer_use_enabled:
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
                    # Stop pressed during preparation: do not open the browser;
                    # the first round's interrupt check ends the turn.
                    direct_navigation_done = (
                        not _interrupt_pending()
                    ) and _maybe_navigate_computer_runtime(messages, core, policy)
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
            return _("Could not open the browser: %(diagnostic)s") % {
                "diagnostic": diagnostic
            }
        return _("Opened the browser.")

    # A runaway model can otherwise spend a very long time issuing tool calls.
    # Keep a high but finite final backstop so long tool-heavy workflows can
    # complete without leaving runaway loops unbounded.
    max_tool_rounds = _resolve_max_tool_rounds()
    round_count = 0
    tool_round_history: deque[tuple[tuple[str, str], ...]] = deque(
        maxlen=_TOOL_ROUND_HISTORY_SIZE
    )
    # Reset loop detection for a new user operation. Auto-Pilot invokes this
    # function once for each follow-up round from the same context, so those
    # calls must preserve the counters or a repeated tool_load can evade the
    # runaway guard forever. The state is context-local (see _LoopGuardState)
    # so concurrent A2A Tasks never share or reset each other's counters.
    loop_guard_state = (
        _loop_guard_state() if preserve_tool_loop_state else begin_loop_guard_turn()
    )
    consecutive_tool_streak = loop_guard_state.consecutive

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

    if not preserve_tool_loop_state:
        try:
            core._file_grep_turn_count = 0
        except Exception:
            pass
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

    final_text: str | None = None

    try:
        while True:
            if not judgment_mode and not memory_projection_access_is_current(
                getattr(core, "memory_projection_snapshot", None), core
            ):
                core._last_round_reason = "memory_access_changed"
                core._memory_projection_invalidated = True
                _clear_responses_after_tool_loop(core, reason="memory_access_changed")
                break
            round_count += 1
            core._last_round_reason = ""
            round_started = time.perf_counter()
            message_count_before_round = len(messages)
            usage_before_round = getattr(core, "_last_responses_usage", {})
            if not isinstance(usage_before_round, dict):
                usage_before_round = {}
            _auto_unload_state().total_rounds += 1
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

            _outcome = _run_one_round(
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
                tool_round_history=tool_round_history,
                consecutive_tool_streak=consecutive_tool_streak,
            )
            round_status = _outcome.status
            client = _outcome.client
            gemini_cache_name = _outcome.gemini_cache_name
            empty_no_tool_rounds = _outcome.empty_no_tool_rounds
            _round_text = _outcome.assistant_text

            completion_regex = getattr(core, "auto_pilot_complete_regex", None)
            if completion_regex and _completion_regex_matches(
                _round_text, completion_regex
            ):
                round_status = _RS_RETURN
                core._last_completion_reason = "regex"
                print(
                    "[COMPLETE] "
                    + json.dumps(
                        {"reason": "regex", "round": round_count},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    flush=True,
                )

            try:
                from .runtime.logging_setup import log_event

                round_tool_calls = 0
                for _message in messages[message_count_before_round:]:
                    if not isinstance(_message, dict):
                        continue
                    _calls = _message.get("tool_calls")
                    if isinstance(_calls, list):
                        round_tool_calls += len(_calls)
                usage_after_round = getattr(core, "_last_responses_usage", {})
                usage_delta = (
                    reconcile_usage(None, usage_after_round)
                    if isinstance(usage_after_round, dict)
                    and usage_after_round is not usage_before_round
                    else {}
                )
                round_reason = str(getattr(core, "_last_round_reason", "") or "")
                public_status = _public_round_status(
                    str(round_status),
                    reason=round_reason,
                    assistant_text=str(_round_text or ""),
                )
                round_duration_ms = round(
                    (time.perf_counter() - round_started) * 1000, 3
                )
                round_summary = RoundSummary(
                    status=(
                        public_status
                        if public_status
                        in {
                            "completed",
                            "continue",
                            "failed",
                            "cancelled",
                            "interrupted",
                        }
                        else "completed"
                    ),
                    duration_ms=round_duration_ms,
                    event_count=max(0, len(messages) - message_count_before_round),
                    tool_call_count=round_tool_calls,
                    assistant_chars=len(str(_round_text or "")),
                    reasoning_chars=0,
                    usage_delta=usage_delta,
                )
                core._last_round_outcome = {
                    "round": round_count,
                    "status": public_status,
                    "reason": round_reason,
                    "tool_calls": round_tool_calls,
                    "assistant_chars": len(str(_round_text or "")),
                    "summary": round_summary.to_dict(),
                }
                usage_setting = (
                    str(env_get("UAGENT_SHOW_USAGE", "") or "").strip().lower()
                )
                usage_enabled = usage_setting not in {"0", "false", "no", "off"}
                try:
                    from .core_impl.display import set_usage_status

                    shown_in_status = set_usage_status(usage_delta or None)
                except Exception:
                    shown_in_status = False
                # Keep a visible fallback when the full-screen status line is
                # unavailable; usage reporting is enabled unless explicitly
                # disabled with UAGENT_SHOW_USAGE=0.
                if usage_delta and not shown_in_status and usage_enabled:
                    print(
                        "[USAGE] "
                        + json.dumps(
                            {
                                "round": round_count,
                                "prompt": usage_delta.get("input_tokens_delta"),
                                "completion": usage_delta.get("output_tokens_delta"),
                                "total": usage_delta.get("total_tokens_delta"),
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        file=sys.stderr,
                        flush=True,
                    )
                log_event(
                    "llm.round.completed",
                    provider=provider,
                    model=depname,
                    round=round_count,
                    internal_status=str(round_status),
                    reason=round_reason,
                    **round_summary.to_dict(),
                    messages_added=max(0, len(messages) - message_count_before_round),
                    usage_available=bool(usage_delta),
                )
                if (env_get("UAGENT_SHOW_ROUND_STATUS", "") or "").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }:
                    round_label = public_status
                    print(
                        "[ROUND] "
                        + json.dumps(
                            {
                                "round": round_count,
                                "status": round_label,
                                "tool_calls": round_tool_calls,
                                "duration_ms": round(
                                    (time.perf_counter() - round_started) * 1000, 3
                                ),
                                "usage_available": bool(usage_delta),
                                "reason": round_reason,
                                "final": public_status != "continue",
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        file=sys.stderr,
                        flush=True,
                    )
            except Exception:
                pass

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
                _au_state = _auto_unload_state()
                _au_state.productive_rounds += 1
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
                    _au_state.last_round[_tname] = _au_state.productive_rounds
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
                                        _au_state.last_round[_target] = (
                                            _au_state.productive_rounds
                                        )
                                break
                        except Exception:
                            pass
                    # tool_catalog may auto-load a tool; stamp single-loaded
                    # tools that still have no last-used marker.
                    if _tname == "tool_catalog":
                        try:
                            for _loaded_name in list(_LOADED_SINGLE_TOOLS):
                                if _loaded_name not in _au_state.last_round:
                                    _au_state.last_round[_loaded_name] = (
                                        _au_state.productive_rounds
                                    )
                        except Exception:
                            pass

                # Keep the complete searchable inventory available while a
                # provider-native search route is active.
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
                        last = _au_state.last_round.get(tname)
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
                            _au_state.last_round.pop(tname, None)
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
