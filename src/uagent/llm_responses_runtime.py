"""Responses API continuation state and remote recovery for the round
loop (split out of uagent_llm).
"""

from __future__ import annotations

from typing import Any

from .runtime.round_contracts import RoundTransportSelection


def _begin_responses_runtime(
    *,
    core: Any,
    provider: str,
    model: str,
    enabled: bool | None = None,
    transport_selection: RoundTransportSelection | None = None,
) -> Any | None:
    """Synchronize the new continuation state machine with legacy state.

    This is deliberately a compatibility bridge: ``responses_state`` remains
    the persisted source until the round orchestrator owns session restore.
    A bridge failure must never change the established request path.
    """
    if transport_selection is not None:
        enabled = transport_selection.use_responses_api
    if not enabled:
        return None
    try:
        from .providers.responses_runtime import ResponsesRuntime

        runtime = getattr(core, "responses_runtime", None)
        provider_changed = False
        if not isinstance(runtime, ResponsesRuntime):
            runtime = ResponsesRuntime(provider=provider, model=model)
            setattr(core, "responses_runtime", runtime)
        else:
            provider_changed = runtime.provider != (
                provider or ""
            ).strip().lower() or runtime.model != (model or "")
            runtime.switch_provider(provider, model)

        state = getattr(core, "responses_state", {})
        if provider_changed and isinstance(state, dict):
            state.pop("previous_response_id", None)
            state.pop("active_response_id", None)
            state.pop("_stale_rid_occurred", None)
        if isinstance(state, dict) and "session_generation" in state:
            try:
                runtime.session_generation = int(
                    state.get("session_generation", 0) or 0
                )
            except (TypeError, ValueError):
                # Keep the runtime's current generation when legacy state is
                # malformed; the compatibility bridge must not abort a round.
                pass
        previous_id = (
            state.get("previous_response_id") if isinstance(state, dict) else None
        )
        if not runtime.capabilities.previous_response_id:
            previous_id = None
            if isinstance(state, dict):
                state.pop("previous_response_id", None)
            runtime.clear_continuation("unsupported_continuation")
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


def _sync_responses_runtime_completed(
    *, core: Any, enabled: bool, round_outcome: Any
) -> None:
    """Bridge a legacy Responses result into ``ResponsesRuntime``.

    Compatibility providers update ``responses_state`` themselves. That is
    sufficient for the old request path, but it leaves the new state machine
    unaware of successful responses when the registry is not selected (in
    particular, responses without a tool call never reach the postamble that
    records tool continuation). Synchronize at the dispatch boundary so both
    routes expose the same continuation state.

    The registry route already performs this synchronization in
    ``RoundOrchestrator``; callers invoke this helper only for non-registry
    outcomes. It is intentionally best-effort while legacy handlers remain
    active.
    """
    if not enabled:
        return
    outcome_status = str(getattr(round_outcome, "status", "ok") or "").lower()
    if outcome_status not in {"ok", "completed"}:
        return
    runtime = getattr(core, "responses_runtime", None)
    state = getattr(core, "responses_state", None)
    if runtime is None or not isinstance(state, dict):
        return
    response_id = state.get("previous_response_id")
    if not isinstance(response_id, str) or not response_id.startswith("resp_"):
        return

    raw_tool_calls = getattr(round_outcome, "tool_calls", ()) or ()
    tool_calls = (
        list(raw_tool_calls) if isinstance(raw_tool_calls, (list, tuple)) else []
    )
    try:
        existing_id = getattr(runtime, "active_response_id", None)
        pending = tuple(getattr(runtime, "pending_tool_calls", ()) or ())
        pending_ids = {str(getattr(item, "tool_call_id", "") or "") for item in pending}
        call_ids = {
            str(item.get("tool_call_id") or item.get("id") or "")
            for item in tool_calls
            if isinstance(item, dict)
        }
        already_synced = existing_id == response_id and (
            (not tool_calls and getattr(runtime, "state", "") == "Fresh")
            or (
                tool_calls
                and getattr(runtime, "state", "") == "AwaitingToolOutput"
                and pending_ids == call_ids
            )
        )
        if not already_synced:
            runtime.sync_completed_response(response_id, tool_calls=tool_calls)
        state["session_generation"] = int(
            getattr(runtime, "session_generation", 0) or 0
        )
    except Exception:
        # The compatibility route must retain its established result even if a
        # malformed provider response cannot be mirrored into the runtime.
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
    """Mirror a non-successful registry terminal state into runtime and state."""
    if status == "completed":
        return
    runtime = getattr(core, "responses_runtime", None)
    if runtime is not None:
        transition = {
            "cancelled": "cancel",
            "timed_out": "timeout",
            "interrupted": "interrupt",
            "failed": "fail",
        }.get(status)
        try:
            if transition is not None:
                getattr(runtime, transition)()
            else:
                runtime.fail(status or "registry_failed")
        except Exception:
            # A compatibility mirror must not hide the terminal state when an
            # already-cleared runtime rejects a repeated transition.
            try:
                runtime.clear_continuation(f"registry_{status or 'failed'}")
            except Exception:
                pass
    state = getattr(core, "responses_state", None)
    if not isinstance(state, dict):
        return
    state.pop("previous_response_id", None)
    state.pop("active_response_id", None)
    state.pop("_stale_rid_occurred", None)
    state["last_response_status"] = status
