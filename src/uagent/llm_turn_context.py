"""Per-turn context preparation for the round loop: context budget,
telemetry, agent state, retrieved tool context, tool selection and the
round context plan (split out of uagent_llm).
"""

from __future__ import annotations

from typing import Any
import hashlib
import json

from .env_utils import env_get
from .runtime.context_budget import ContextBudget
from .runtime.context_plan_builder import build_context_plan
from .runtime.context_policy import ContextPolicy
from .runtime.memory_projection import prepare_memory_projection


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
    if telemetry is None:
        telemetry = {}
    else:
        telemetry = dict(telemetry)
    memory_snapshot = getattr(core, "memory_projection_snapshot", None)
    if memory_snapshot is not None:
        try:
            telemetry["memory_projection"] = memory_snapshot.to_diagnostics()
        except Exception:
            pass
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
    failed = state.get("failed_steps") or []
    if not isinstance(failed, list):
        failed = list(failed) if isinstance(failed, tuple) else []
    lines = [
        "[agent state]",
        f"goal: {str(state.get('goal') or '')[-1000:]}",
        f"current_step: {str(state.get('current_step') or '')[-500:]}",
        f"failed_steps: {', '.join(str(item) for item in failed[-20:])}",
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


_DEFAULT_MAX_TOOL_ROUNDS = 512


def _resolve_max_tool_rounds() -> int:
    try:
        return max(
            1,
            int(env_get("UAGENT_MAX_TOOL_ROUNDS", str(_DEFAULT_MAX_TOOL_ROUNDS))),
        )
    except (TypeError, ValueError):
        return _DEFAULT_MAX_TOOL_ROUNDS


def _message_content_chars(messages: list[dict[str, Any]]) -> int:
    return sum(
        len(str(message.get("content") or ""))
        for message in messages
        if isinstance(message, dict)
    )


def _run_turn_prep_step(step: str, fn: Any, *args: Any) -> bool:
    """Run one per-turn preparation step without aborting the others.

    Each step is best-effort, but a failure must stay diagnosable and must not
    skip later steps: the context budget and tool narrowing still have to run
    so the provider never receives an unbudgeted request or a stale tool
    surface from a previous turn.
    """
    try:
        fn(*args)
        return True
    except Exception as exc:
        try:
            from .runtime.logging_setup import log_event

            log_event(
                "llm.turn_prep.failed",
                step=step,
                error_type=type(exc).__name__,
                status="error",
            )
        except Exception:
            pass
        return False


def _observe_shadow_retrieval(messages: list[dict[str, Any]], core: Any) -> None:
    from .runtime.memory_retrieval import observe_memory_shadow_retrieval

    observe_memory_shadow_retrieval(messages, core)


def _prepare_turn_memory_projection(messages: list[dict[str, Any]], core: Any) -> None:
    # Cleared first so a failure never reuses the previous turn's snapshot.
    core.memory_projection_snapshot = None
    core.memory_projection_snapshot = prepare_memory_projection(messages, core)


def _inject_turn_receipt_context(messages: list[dict[str, Any]], core: Any) -> None:
    from .runtime.sub_agent_receipt_context import inject_sub_agent_receipt_context

    inject_sub_agent_receipt_context(messages, core)


def _build_turn_active_context(messages: list[dict[str, Any]], core: Any) -> None:
    core.active_context = None
    core.active_context = core.context_manager.build_message_context(
        messages,
        budget=ContextBudget(total_chars=max(1, _message_content_chars(messages))),
    )


def _select_turn_tool_specs(messages: list[dict[str, Any]], core: Any) -> None:
    # Cleared first: on failure the provider falls back to the full registry
    # instead of the previous turn's narrowed selection.
    core.context_tool_specs = None
    from . import tools as _tools

    task_text = next(
        (
            str(message.get("content") or "")
            for message in reversed(messages)
            if isinstance(message, dict) and message.get("role") == "user"
        ),
        "",
    )
    tool_selection = core.context_manager.optimize_tool_definitions(
        _tools.get_tool_specs(),
        task=task_text,
    )
    core.context_tool_specs = tool_selection.specs
    core.context_tool_decisions = tool_selection.decisions
    core.context_tool_report = {
        "raw_chars": tool_selection.raw_chars,
        "active_chars": tool_selection.active_chars,
    }


def _prepare_turn_context(messages: list[dict[str, Any]], core: Any) -> None:
    """Prepare per-user-turn context. Order matters; each step is isolated."""
    raw_context_chars = _message_content_chars(messages)
    # Shadow retrieval is observational and opt-in. Run it before
    # state/tool-result injection so its query is the user's original turn and
    # never changes the provider input.
    _run_turn_prep_step("shadow_retrieval", _observe_shadow_retrieval, messages, core)
    # Prepare once per user turn; _run_one_round reuses this snapshot for
    # retries and the entire tool loop.
    _run_turn_prep_step(
        "memory_projection", _prepare_turn_memory_projection, messages, core
    )
    _run_turn_prep_step(
        "agent_state_context", _inject_agent_state_context, messages, core
    )
    _run_turn_prep_step(
        "retrieved_tool_context", _inject_retrieved_tool_context, messages, core
    )
    _run_turn_prep_step(
        "agent_state_update", _update_agent_state_for_turn, messages, core
    )
    # Add lower-trust receipt evidence only AFTER state updates: the generated
    # receipt prose must never become a persisted Goal.
    _run_turn_prep_step(
        "sub_agent_receipt_context", _inject_turn_receipt_context, messages, core
    )
    # Apply the budget after state/retrieval injection so recovered context is
    # governed by the same policy as the conversation.
    _run_turn_prep_step("context_budget", _apply_context_budget, messages, core)
    # Keep a provider-neutral snapshot as the single context hand-off, without
    # compacting a second time or changing tool metadata/call pairing.
    _run_turn_prep_step("active_context", _build_turn_active_context, messages, core)
    _run_turn_prep_step(
        "context_telemetry",
        _record_context_telemetry,
        messages,
        core,
        raw_context_chars,
    )
    _run_turn_prep_step("tool_selection", _select_turn_tool_specs, messages, core)
