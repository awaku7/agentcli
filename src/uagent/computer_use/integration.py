"""Helpers for attaching Computer Use execution to the existing tool loop."""

from __future__ import annotations

import base64
import json
import time
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from .actions import normalize_action
from .audit import InMemoryAuditSink
from .policy import ComputerUsePolicy
from .runtime import ComputerRuntime, execute_action


def _register_runtime_manager(core: Any, manager: Any) -> Any:
    """Expose every backend and select the native/local runtime correctly."""
    core.computer_use_runtime_manager = manager
    runtimes = getattr(manager, "runtimes", {})
    if isinstance(runtimes, dict):
        core.computer_use_browser_runtime = runtimes.get("browser")
        core.computer_use_desktop_runtime = runtimes.get("desktop")
        # Native Computer Use operates on the visible OS surface, including
        # browser chrome. BrowserRuntime screenshots only the web page and
        # cannot interpret Ctrl+L as an address-bar shortcut.
        if bool(getattr(core, "computer_use_native_active", False)):
            native_provider = str(
                getattr(core, "computer_use_native_provider", "") or ""
            ).lower()
            environment = str(
                getattr(core, "computer_use_environment", "desktop") or "desktop"
            ).lower()
            use_browser = (
                native_provider
                in {
                    "openai",
                    "azure",
                    "azure-openai",
                    "azure_foundry",
                    "azure-foundry",
                    "gemini",
                    "vertexai",
                    "meta",
                }
                and environment == "browser"
            )
            selected = runtimes.get("browser" if use_browser else "desktop")
            if selected is not None:
                core.computer_use_runtime = selected
                return selected
        selected = runtimes.get("browser") or manager.runtime
    else:
        selected = manager.runtime
    core.computer_use_runtime = selected
    return selected


def _host_confirmation_callback(core: Any | None = None):
    try:
        from .. import tools
        from ..i18n import _

        def confirm(action: Any) -> bool:
            # Use the shared human_ask route so CLI, GUI, and Web entry points
            # all display a confirmation prompt. The generic default tool
            # callback silently returns False and provides no visible prompt.
            prompt = _("Computer Use requests permission for action '%(action)s'") % {
                "action": action.action
            }
            if action.coordinate is not None:
                prompt += _(" at %(coordinate)s") % {"coordinate": action.coordinate}
            if action.key:
                prompt += _(" with key '%(key)s'") % {"key": action.key}
            if action.text:
                prompt += _(" (text length %(length)d)") % {"length": len(action.text)}
            prompt += _(".\nAllow this action? Enter y/yes to allow, or c to deny.")
            result = tools.run_tool(
                "human_ask", {"message": prompt, "is_password": False}
            )
            # A cancellation/interrupt used to answer this confirmation must
            # not leak into the outer LLM round as a global stop request.
            if core is not None:
                try:
                    with core.interrupt_lock:
                        core.interrupt_requested = False
                    core.computer_use_confirmation_just_completed = True
                except Exception:
                    pass
            if isinstance(result, dict):
                reply = result.get("user_reply", "")
            else:
                try:
                    reply = json.loads(str(result)).get("user_reply", "")
                except Exception:
                    reply = ""
            return str(reply or "").strip().lower() in {"y", "yes", "allow"}

        return confirm
    except Exception:
        return None


def _host_safety_check_confirmation(core: Any | None = None):
    """Return a fail-closed human confirmation callback for Meta checks."""
    try:
        from .. import tools
        from ..i18n import _

        def confirm(check: dict[str, Any]) -> bool:
            prompt = _(
                "Meta Computer Use requires review of safety check %(code)s: %(message)s.\n"
                "Review and approve this check? Enter y/yes to approve, or c to deny."
            ) % {
                "code": str(check.get("code") or "unknown"),
                "message": str(check.get("message") or ""),
            }
            result = tools.run_tool(
                "human_ask", {"message": prompt, "is_password": False}
            )
            if core is not None:
                try:
                    with core.interrupt_lock:
                        core.interrupt_requested = False
                    core.computer_use_confirmation_just_completed = True
                except Exception:
                    pass
            if isinstance(result, dict):
                reply = result.get("user_reply", "")
            else:
                try:
                    reply = json.loads(str(result)).get("user_reply", "")
                except Exception:
                    reply = ""
            return str(reply or "").strip().lower() in {"y", "yes", "allow"}

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
    # Runtime creation stays lazy: enabling Computer Use or registering the
    # handler must not open a browser or touch desktop input. The concrete
    # runtimes are created only when an actual Computer Use action arrives.
    sink = audit or InMemoryAuditSink()
    confirmation = getattr(core, "computer_use_confirmation", None)
    if confirmation is None:
        confirmation = _host_confirmation_callback(core)
    safety_check_confirmation = getattr(
        core, "computer_use_safety_check_confirmation", None
    )
    if provider.lower() == "meta" and safety_check_confirmation is None:
        safety_check_confirmation = _host_safety_check_confirmation(core)
    state = {
        "actions": 0,
        "turns": set(),
        "started": time.monotonic(),
        "confirmed": False,
        "failed_batches": set(),
    }
    lock = Lock()

    def handle(*, tool_call: dict[str, Any], action: dict[str, Any], messages, core):
        nonlocal selected_runtime
        del messages
        action_id = str(tool_call.get("id") or "computer")
        batch_id = str(tool_call.get("computer_batch_id") or "")
        if (
            batch_id
            and batch_id in state["failed_batches"]
            and tool_call.get("computer_toolset_name") == "computer"
        ):
            from .adapters.anthropic import ANTHROPIC_NOT_EXECUTED

            return json.dumps(
                {
                    "success": False,
                    "action_id": action_id,
                    "error": ANTHROPIC_NOT_EXECUTED,
                },
                ensure_ascii=False,
            )
        items = action.get("actions") if isinstance(action, dict) else None
        if not isinstance(items, list):
            items = [action]
        acknowledged_safety_checks: list[dict[str, Any]] = []
        replay_receipt = None
        if provider.lower() == "meta":
            replay_receipt = action.get("meta_safety_replay_receipt")
            pending_checks = action.get("pending_safety_checks", [])
            if not isinstance(pending_checks, list):
                return json.dumps(
                    {
                        "success": False,
                        "action_id": action_id,
                        "error": "Meta pending_safety_checks must be a list",
                        "acknowledged_safety_checks": [],
                        "meta_safety_replay_receipt": replay_receipt,
                    },
                    ensure_ascii=False,
                )
            checks_valid = all(
                isinstance(check, dict)
                and all(key in check for key in ("id", "code", "message"))
                for check in pending_checks
            )
            if not checks_valid:
                return json.dumps(
                    {
                        "success": False,
                        "action_id": action_id,
                        "error": "Meta safety checks must include id, code, and message",
                        "acknowledged_safety_checks": [],
                        "meta_safety_replay_receipt": replay_receipt,
                    },
                    ensure_ascii=False,
                )
            for check in pending_checks:
                try:
                    approved = (
                        callable(safety_check_confirmation)
                        and safety_check_confirmation(check) is True
                    )
                except Exception:
                    approved = False
                if not approved:
                    result: dict[str, Any] = {
                        "success": False,
                        "action_id": action_id,
                        "error": "Meta Computer Use safety check was not approved",
                        "acknowledged_safety_checks": acknowledged_safety_checks,
                    }
                    if replay_receipt is not None:
                        result["meta_safety_replay_receipt"] = replay_receipt
                    return json.dumps(result, ensure_ascii=False)
                acknowledged_safety_checks.append(dict(check))
        turn_id = str(getattr(core, "computer_use_turn_id", "") or "")
        outputs = []
        call_confirmed = False

        def confirm_once(candidate: Any) -> bool:
            nonlocal call_confirmed
            if call_confirmed or state["confirmed"]:
                return True
            if not callable(confirmation):
                return False
            allowed = bool(confirmation(candidate))
            if allowed:
                call_confirmed = True
                state["confirmed"] = True
            return allowed

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
            # Create the configured backend only when an actual action arrives.
            # Enabling the generic Computer Use capability must not open a
            # browser as a side effect.
            if selected_runtime is None:
                selected_runtime = getattr(core, "computer_use_runtime", None)
                if selected_runtime is None:
                    from .entrypoint_runtime import create_runtime_from_env

                    # The shared policy has already authorized this action.
                    # Do not apply the process-level opt-in gate a second
                    # time at the lazy action boundary.
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
                        selected_runtime = _register_runtime_manager(core, manager)
                if selected_runtime is None:
                    outputs.append(
                        {
                            "success": False,
                            "action_id": item_id,
                            "error": "Computer Use runtime is unavailable",
                        }
                    )
                    break
            domain = None
            if normalized.action == "navigate":
                # Authorize the destination before navigation, not the current
                # page (which may be about:blank or an allowed origin).
                try:
                    domain = urlparse(str(normalized.text or "")).hostname
                except Exception:
                    domain = None
            else:
                current_domain = getattr(selected_runtime, "current_domain", None)
                if callable(current_domain):
                    domain = current_domain()
            result = execute_action(
                normalized,
                policy=policy,
                runtime=selected_runtime,
                domain=domain,
                confirm=confirm_once,
                audit=sink,
                session_id=session_id,
                turn_id=turn_id or None,
            )
            # Responses computer calls require a screenshot output after each
            # action, including policy/runtime failures. The API rejects a
            # computer_call_output without an image_url.
            if result.screenshot is None:
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
            if batch_id and not result.success:
                state["failed_batches"].add(batch_id)
            if provider.lower() == "meta" and not result.success:
                # Meta batches are a single computer_call. Stop at the first
                # failed action, then return the final visible screen once.
                break
        if (
            batch_id
            and outputs
            and any(not output.get("success", False) for output in outputs)
        ):
            state["failed_batches"].add(batch_id)
        if len(outputs) == 1:
            response_payload = dict(outputs[0])
        else:
            response_payload = {
                "success": bool(outputs)
                and all(x.get("success", False) for x in outputs),
                "action_id": action_id,
                "results": outputs,
            }
        if provider.lower() == "meta":
            response_payload["acknowledged_safety_checks"] = acknowledged_safety_checks
            if replay_receipt is not None:
                response_payload["meta_safety_replay_receipt"] = replay_receipt
        return json.dumps(response_payload, ensure_ascii=False)

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
