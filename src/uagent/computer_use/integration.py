"""Helpers for attaching Computer Use execution to the existing tool loop."""

from __future__ import annotations

import json
from typing import Any

from .actions import normalize_action
from .audit import InMemoryAuditSink
from .policy import ComputerUsePolicy
from .runtime import ComputerRuntime, execute_action


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

    Entrypoints provide a runtime by assigning ``core.computer_use_runtime``;
    this function deliberately does not create a browser or desktop session.
    """
    if not policy.enabled:
        return None
    selected_runtime = runtime or getattr(core, "computer_use_runtime", None)
    if selected_runtime is None:
        raise RuntimeError(
            "Computer Use is enabled but no computer_use_runtime is configured"
        )
    handler = make_computer_use_handler(
        provider=provider,
        model=model,
        policy=policy,
        runtime=selected_runtime,
        audit=audit,
        session_id=session_id,
    )
    core.computer_use_handler = handler
    return handler


def make_computer_use_handler(
    *,
    provider: str,
    model: str,
    policy: ComputerUsePolicy,
    runtime: ComputerRuntime,
    audit: Any | None = None,
    session_id: str | None = None,
):
    """Create a callback accepted by ``llm_flow_helpers._execute_tool_calls``.

    This is intentionally an integration boundary: the existing round loop
    dispatches a ``computer`` call here, while Provider-specific native request
    construction remains in its adapter.
    """
    sink = audit or InMemoryAuditSink()

    def handle(*, tool_call: dict[str, Any], action: dict[str, Any], messages, core):
        del messages, core
        action_id = str(tool_call.get("id") or "computer")
        normalized = normalize_action(
            action_id=action_id,
            payload=action,
            provider=provider,
        )
        result = execute_action(
            normalized,
            policy=policy,
            runtime=runtime,
            audit=sink,
            session_id=session_id,
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

    return handle
