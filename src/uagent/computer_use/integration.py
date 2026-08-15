"""Helpers for attaching Computer Use execution to the existing tool loop."""

from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any

from .actions import normalize_action
from .audit import InMemoryAuditSink
from .policy import ComputerUsePolicy
from .runtime import ComputerRuntime, execute_action


def _host_confirmation_callback():
    """Resolve the shared CLI/GUI/Web/A2A confirmation callback."""
    try:
        from .. import tools

        getter = getattr(tools, "get_confirmation_callback", None)
        if callable(getter):
            return getter()
    except Exception:
        pass
    return None


def make_unavailable_computer_use_handler(*, reason: str):
    """Return a safe handler that reports an unavailable Runtime to the LLM."""

    def handle(*, tool_call: dict[str, Any], action: dict[str, Any], messages, core):
        del action, messages, core
        return json.dumps(
            {
                "success": False,
                "action_id": str(tool_call.get("id") or "computer"),
                "error": reason,
            },
            ensure_ascii=False,
        )

    return handle


def install_computer_use_handler(
    *,
    core: Any,
    provider: str,
    model: str,
    policy: ComputerUsePolicy,
    runtime: ComputerRuntime | None = None,
    audit: Any | None = None,
    session_id: str | None = None,
) -> Any | None:
    """Install the Computer Use callback on a live round-loop ``core``.

    Entrypoints provide a Runtime by assigning ``core.computer_use_runtime``;
    this function deliberately does not create a browser or desktop session.
    Missing Runtime configuration is reported by the round loop and never
    causes an enabled CLI/GUI/Web/A2A process to crash at startup.
    """
    if not policy.enabled:
        return None
    selected_runtime = runtime or getattr(core, "computer_use_runtime", None)
    if selected_runtime is None:
        raise RuntimeError(
            "Computer Use is enabled but no computer_use_runtime is configured"
        )
    sink = audit or InMemoryAuditSink()
    confirmation = getattr(core, "computer_use_confirmation", None)
    if confirmation is None:
        confirmation = _host_confirmation_callback()
    state = {"actions": 0, "turns": set(), "started": time.monotonic()}
    lock = Lock()

    def handle(*, tool_call: dict[str, Any], action: dict[str, Any], messages, core):
        del messages
        action_id = str(tool_call.get("id") or "computer")
        normalized = normalize_action(
            action_id=action_id, payload=action, provider=provider
        )
        turn_id = str(getattr(core, "computer_use_turn_id", "") or "")
        with lock:
            if state["actions"] >= policy.max_actions:
                error = "Computer Use max_actions limit reached"
                return json.dumps(
                    {"success": False, "action_id": action_id, "error": error}
                )
            if turn_id:
                state["turns"].add(turn_id)
            if len(state["turns"]) > policy.max_turns:
                error = "Computer Use max_turns limit reached"
                return json.dumps(
                    {"success": False, "action_id": action_id, "error": error}
                )
            if time.monotonic() - state["started"] > policy.timeout:
                error = "Computer Use timeout reached"
                return json.dumps(
                    {"success": False, "action_id": action_id, "error": error}
                )
            state["actions"] += 1
        result = execute_action(
            normalized,
            policy=policy,
            runtime=selected_runtime,
            confirm=confirmation,
            audit=sink,
            session_id=session_id,
            turn_id=turn_id or None,
        )
        return json.dumps(
            {
                "success": result.success,
                "action_id": result.action_id,
                "error": result.error,
                "provider": provider,
                "model": model,
                "screenshot": bool(result.screenshot),
            },
            ensure_ascii=False,
        )

    core.computer_use_handler = handle
    return handle


def make_computer_use_handler(
    *,
    provider: str,
    model: str,
    policy: ComputerUsePolicy,
    runtime: ComputerRuntime,
    audit: Any | None = None,
    session_id: str | None = None,
):
    """Backward-compatible alias for the guarded handler factory."""

    class _Core:
        computer_use_runtime = runtime

    return install_computer_use_handler(
        core=_Core(),
        provider=provider,
        model=model,
        policy=policy,
        runtime=runtime,
        audit=audit,
        session_id=session_id,
    )
