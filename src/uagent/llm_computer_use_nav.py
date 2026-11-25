"""Computer Use direct navigation before the LLM call (split out of
uagent_llm).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
import re

from .env_utils import env_get


def _computer_use_enabled_for_current_execution(core: Any, policy: Any) -> bool:
    """Fail closed and tear down host Computer Use outside local Sandbox-off turns."""
    from .runtime.execution_broker import computer_use_allowed

    enabled = bool(getattr(policy, "enabled", False)) and computer_use_allowed()
    if enabled:
        return True

    manager = getattr(core, "computer_use_runtime_manager", None)
    manager_closed = False
    if manager is not None and callable(getattr(manager, "close", None)):
        try:
            manager.close()
            manager_closed = True
        except Exception:
            pass
    runtime = getattr(core, "computer_use_runtime", None)
    if not manager_closed and callable(getattr(runtime, "close", None)):
        try:
            runtime.close()
        except Exception:
            pass
    if getattr(policy, "enabled", False):
        try:
            core.computer_use_diagnostic = (
                "Computer Use is disabled for Remote or Sandbox-enabled execution"
            )
        except Exception:
            pass
    for name in (
        "computer_use_runtime",
        "computer_use_runtime_manager",
        "computer_use_browser_runtime",
        "computer_use_desktop_runtime",
        "computer_use_handler",
        "computer_use_native_tool",
        "computer_use_native_headers",
        "computer_use_native_provider",
        "computer_use_native_active",
    ):
        try:
            setattr(core, name, None)
        except Exception:
            pass
    return False


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
    from .runtime.execution_broker import computer_use_allowed

    if not computer_use_allowed():
        log_event("computer.explicit_navigation.denied_by_execution_profile")
        return False
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
