"""Helpers for attaching Computer Use execution to the existing tool loop."""

from __future__ import annotations

import json
from typing import Any

from .actions import normalize_action
from .audit import InMemoryAuditSink
from .policy import ComputerUsePolicy
from .runtime import ComputerRuntime, execute_action


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
