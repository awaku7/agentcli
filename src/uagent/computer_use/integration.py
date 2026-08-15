"""Helpers for attaching Computer Use execution to the existing tool loop."""

from __future__ import annotations

import base64
import json
import time
from threading import Lock
from typing import Any

from .actions import normalize_action
from .audit import InMemoryAuditSink
from .policy import ComputerUsePolicy
from .runtime import ComputerRuntime, execute_action


def _host_confirmation_callback():
    try:
        from .. import tools

        getter = getattr(tools, "get_confirmation_callback", None)
        callback = getter() if callable(getter) else None
        if not callable(callback):
            return None

        # The host tool-policy callback uses (name, args, policy), while the
        # Computer Runtime boundary uses (ComputerAction). Adapt explicitly.
        from ..tools.tool_policy import policy_for

        def confirm(action: Any) -> bool:
            args = {
                "action": action.action,
                "coordinate": action.coordinate,
                "text_length": len(action.text or ""),
                "key": action.key,
            }
            return bool(callback("computer", args, policy_for("computer", args)))

        return confirm
    except Exception:
        return None


def make_unavailable_computer_use_handler(*, reason: str):
    """Return a safe handler that reports an unavailable Runtime."""

    def handle(*, tool_call: dict[str, Any], action, messages, core):
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
    """Install the guarded Computer Use callback on a live round-loop core."""
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
        items = action.get("actions") if isinstance(action, dict) else None
        if not isinstance(items, list):
            items = [action]
        turn_id = str(getattr(core, "computer_use_turn_id", "") or "")
        outputs = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            item_id = f"{action_id}:{index}" if len(items) > 1 else action_id
            normalized = normalize_action(
                action_id=item_id, payload=item, provider=provider
            )
            with lock:
                if state["actions"] >= policy.max_actions:
                    outputs.append(
                        {
                            "success": False,
                            "action_id": item_id,
                            "error": "Computer Use max_actions limit reached",
                        }
                    )
                    break
                if turn_id:
                    state["turns"].add(turn_id)
                if len(state["turns"]) > policy.max_turns:
                    outputs.append(
                        {
                            "success": False,
                            "action_id": item_id,
                            "error": "Computer Use max_turns limit reached",
                        }
                    )
                    break
                if time.monotonic() - state["started"] > policy.timeout:
                    outputs.append(
                        {
                            "success": False,
                            "action_id": item_id,
                            "error": "Computer Use timeout reached",
                        }
                    )
                    break
                state["actions"] += 1
            domain = None
            current_domain = getattr(selected_runtime, "current_domain", None)
            if callable(current_domain):
                domain = current_domain()
            result = execute_action(
                normalized,
                policy=policy,
                runtime=selected_runtime,
                domain=domain,
                confirm=confirmation,
                audit=sink,
                session_id=session_id,
                turn_id=turn_id or None,
            )
            # Responses computer calls require a screenshot output after each
            # action, not only after an explicit screenshot action.
            if result.success and result.screenshot is None:
                try:
                    result = type(result)(
                        action_id=result.action_id,
                        success=result.success,
                        error=result.error,
                        screenshot=selected_runtime.screenshot(),
                    )
                except Exception:
                    pass
            outputs.append(
                {
                    "success": result.success,
                    "action_id": result.action_id,
                    "error": result.error,
                    "provider": provider,
                    "model": model,
                    "screenshot": bool(result.screenshot),
                    "screenshot_data": (
                        base64.b64encode(result.screenshot.data).decode("ascii")
                        if result.screenshot is not None
                        else None
                    ),
                    "screenshot_media_type": (
                        result.screenshot.media_type
                        if result.screenshot is not None
                        else None
                    ),
                }
            )
        if len(outputs) == 1:
            return json.dumps(outputs[0], ensure_ascii=False)
        return json.dumps(
            {
                "success": bool(outputs)
                and all(x.get("success", False) for x in outputs),
                "action_id": action_id,
                "results": outputs,
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
    """Backward-compatible handler factory."""

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
