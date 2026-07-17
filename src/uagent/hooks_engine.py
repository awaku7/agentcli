"""Hooks execution engine for uagent plugin hooks.

Supports loading hooks from registry, event matching, and executing
command-type hooks. Designed to integrate with runtime lifecycle.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from .utils.paths import get_state_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_REGISTRY_FILENAME = "plugin_hooks.json"
DEFAULT_REGISTRY_DIR = "hooks"
DEFAULT_HOOK_TIMEOUT_MS = 30_000  # 30 seconds

# Supported hook types
COMMAND_TYPE = "command"
HTTP_TYPE = "http"
MCP_TOOL_TYPE = "mcp_tool"
PROMPT_TYPE = "prompt"
AGENT_TYPE = "agent"
SUPPORTED_TYPES = {COMMAND_TYPE, HTTP_TYPE, MCP_TOOL_TYPE, PROMPT_TYPE, AGENT_TYPE}


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def get_default_registry_path() -> str:
    """Return the default hooks registry path."""
    return str(get_state_dir() / DEFAULT_REGISTRY_DIR / DEFAULT_REGISTRY_FILENAME)


def load_hooks_registry(registry_path: str | None = None) -> dict[str, Any]:
    """Load hooks from the registry file.

    Returns hooks organized as event_name -> list of hook entries.
    Returns empty dict if registry is missing or invalid.
    """
    path = registry_path or get_default_registry_path()
    rp = Path(path)
    if not rp.is_file():
        return {}

    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    plugins = data.get("plugins", {})
    if not isinstance(plugins, dict):
        return {}

    # Merge all hooks from all plugins, organized by event
    merged: dict[str, list[dict[str, Any]]] = {}
    for plugin_name, plugin_hooks in plugins.items():
        if not isinstance(plugin_hooks, dict):
            continue
        for event_name, hook_groups in plugin_hooks.items():
            if not isinstance(hook_groups, list):
                continue
            if event_name not in merged:
                merged[event_name] = []
            merged[event_name].extend(hook_groups)

    return merged


# ---------------------------------------------------------------------------
# Hook execution
# ---------------------------------------------------------------------------


def execute_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
    tool_name: str | None = None,
    event_name: str | None = None,
) -> dict[str, Any]:
    """Execute a single hook.

    Args:
        hook: Hook definition dict with type, command, etc.
        timeout_ms: Timeout in milliseconds.
        tool_name: Context: name of the tool being used (for PreToolUse etc.)
        event_name: Context: name of the event firing.

    Returns:
        Dict with ok, stdout, stderr, etc.
    """
    hook_type = hook.get("type", "")

    if hook_type not in SUPPORTED_TYPES:
        return {
            "ok": False,
            "error": f"Unsupported hook type: {hook_type}. Supported: {SUPPORTED_TYPES}",
        }

    if hook_type == COMMAND_TYPE:
        return _execute_command_hook(hook, timeout_ms=timeout_ms)
    elif hook_type == HTTP_TYPE:
        return _execute_http_hook(hook, timeout_ms=timeout_ms)
    elif hook_type == PROMPT_TYPE:
        return _execute_prompt_hook(hook, timeout_ms=timeout_ms)
    elif hook_type == MCP_TOOL_TYPE:
        return _execute_mcp_tool_hook(hook, timeout_ms=timeout_ms)
    elif hook_type == AGENT_TYPE:
        return _execute_agent_hook(hook, timeout_ms=timeout_ms)

    return {"ok": False, "error": f"Unknown hook type: {hook_type}"}


def _execute_command_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> dict[str, Any]:
    """Execute a command-type hook via subprocess."""
    command = hook.get("command", "")
    if not command:
        return {"ok": False, "error": "Command hook has no command."}

    # Substitute environment variables like ${UAGENT_PLUGIN_ROOT}
    expanded = _expand_vars(command)

    try:
        result = subprocess.run(
            expanded,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000.0,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"Command timed out after {timeout_ms}ms",
            "command": command,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "command": command,
        }


# ---------------------------------------------------------------------------
# Event firing
# ---------------------------------------------------------------------------


def find_matching_hooks(
    event_name: str,
    hooks: dict[str, Any],
    *,
    tool_name: str | None = None,
) -> list[dict[str, Any]]:
    """Find hook definitions that match the given event and context.

    For events with matchers (like PreToolUse), only hooks whose matcher
    matches the tool name are returned. Hook groups without a matcher
    are always returned (default/fallback).

    Returns a flat list of individual hook definitions.
    """
    hook_groups = hooks.get(event_name, [])
    if not isinstance(hook_groups, list):
        return []

    matched: list[dict[str, Any]] = []

    for group in hook_groups:
        if not isinstance(group, dict):
            continue
        matcher = group.get("matcher")
        group_hooks = group.get("hooks", [])

        # If there's a matcher, check if it matches
        if matcher and tool_name:
            if not re.search(matcher, tool_name):
                continue  # matcher didn't match, skip this group
        elif matcher and not tool_name:
            # Matcher exists but no tool_name context - skip
            continue

        # Add all hooks in this group
        if isinstance(group_hooks, list):
            for h in group_hooks:
                if isinstance(h, dict):
                    matched.append(h)

    return matched


def fire_event(
    event_name: str,
    hooks: dict[str, Any],
    *,
    tool_name: str | None = None,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """Fire an event, executing all matching hooks.

    Returns list of execution results.
    """
    matching = find_matching_hooks(
        event_name, hooks, tool_name=tool_name
    )
    if not matching:
        return []

    results: list[dict[str, Any]] = []
    for hook_def in matching:
        result = execute_hook(
            hook_def,
            timeout_ms=timeout_ms,
            tool_name=tool_name,
            event_name=event_name,
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Variable expansion
# ---------------------------------------------------------------------------

# Compiled patterns for variable expansion
_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_vars(command: str) -> str:
    """Expand ${VAR} and ${UAGENT_PLUGIN_ROOT} style variables in a command.

    Supports:
    - ${UAGENT_PLUGIN_ROOT} -> plugin install root
    - ${UAGENT_PROJECT_DIR} -> project directory
    - Any ${ENV_VAR} -> os.environ lookup

    Unknown variables are left as-is.
    """
    def _replace(m: re.Match) -> str:
        var_name = m.group(1)

        if var_name == "UAGENT_PLUGIN_ROOT":
            return str(get_state_dir() / "plugins")
        elif var_name == "UAGENT_PROJECT_DIR":
            return os.getcwd()
        else:
            return os.environ.get(var_name, m.group(0))

    return _VAR_RE.sub(_replace, command)


# ---------------------------------------------------------------------------
# HTTP hook execution
# ---------------------------------------------------------------------------


def _execute_http_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> dict[str, Any]:
    """Execute an http-type hook via urllib."""
    url = hook.get("url", "")
    if not url:
        return {"ok": False, "error": "HTTP hook has no url."}

    method = hook.get("method", "POST").upper()
    if method not in ("POST", "PUT", "PATCH"):
        return {"ok": False, "error": f"Unsupported HTTP method: {method}. Supported: POST, PUT, PATCH"}

    import urllib.request
    import urllib.error

    body_bytes = json.dumps(hook.get("body", {})).encode("utf-8")
    req = urllib.request.Request(
        _expand_vars(url),
        data=body_bytes,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout_ms / 1000.0)
        return {
            "ok": resp.status < 400,
            "status": resp.status,
            "body": resp.read().decode("utf-8", errors="replace")[:10000],
            "url": url,
        }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "status": e.code,
            "body": e.read().decode("utf-8", errors="replace")[:10000],
            "error": str(e),
            "url": url,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "url": url,
        }


# ---------------------------------------------------------------------------
# MCP tool hook
# ---------------------------------------------------------------------------


def _execute_mcp_tool_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> dict[str, Any]:
    """Execute an mcp_tool-type hook.

    Calls a tool on a configured MCP server.
    Hook requires 'server' (MCP server name) and 'tool' (tool name).
    """
    server = hook.get("server", "")
    tool = hook.get("tool", "")
    args = hook.get("args", {})

    if not server:
        return {"ok": False, "error": "MCP tool hook has no 'server'."}
    if not tool:
        return {"ok": False, "error": "MCP tool hook has no 'tool'."}

    # Try to call via handle_mcp_v2 tool
    try:
        from .tools.handle_mcp_v2_tool import run_tool as mcp_run

        result = mcp_run({
            "server_name": _expand_vars(server),
            "tool_name": tool,
            "arguments": args,
        })
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": f"MCP tool call failed: {e}"}


# ---------------------------------------------------------------------------
# Prompt hook (LLM evaluation) - placeholder
# ---------------------------------------------------------------------------


def _execute_prompt_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> dict[str, Any]:
    """Execute a prompt-type hook.

    Note: Full LLM evaluation requires provider client setup.
    This implementation returns a descriptive message indicating
    the prompt hook was triggered but LLM execution is not yet supported.
    """
    prompt = hook.get("prompt", "")
    if not prompt:
        return {"ok": False, "error": "Prompt hook has no prompt."}

    return {
        "ok": False,
        "error": "prompt hook type not supported in this version (LLM evaluation not yet implemented)",
        "prompt": prompt[:200],
    }


# ---------------------------------------------------------------------------
# Agent hook - placeholder
# ---------------------------------------------------------------------------


def _execute_agent_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> dict[str, Any]:
    """Execute an agent-type hook.

    Note: Full agent execution requires sub-agent setup.
    This implementation returns a descriptive message.
    """
    agent_prompt = hook.get("prompt", "")
    return {
        "ok": False,
        "error": "agent hook type not supported in this version (sub-agent execution not yet implemented)",
        "prompt": agent_prompt[:200] if agent_prompt else "",
    }


# ---------------------------------------------------------------------------
# Tool event helpers (PreToolUse / PostToolUse / PostToolUseFailure)
# ---------------------------------------------------------------------------


def fire_tool_event(
    event_name: str,
    hooks: dict[str, Any],
    *,
    tool_name: str = "",
    tool_args: dict[str, Any] | None = None,
    tool_result: str = "",
    tool_error: str = "",
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """Fire a tool-related event with context.

    Supports PreToolUse, PostToolUse, PostToolUseFailure.
    """
    matching = find_matching_hooks(
        event_name, hooks, tool_name=tool_name
    )
    if not matching:
        return []

    results: list[dict[str, Any]] = []
    for hook_def in matching:
        result = execute_hook(
            hook_def,
            timeout_ms=timeout_ms,
            tool_name=tool_name,
            event_name=event_name,
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Hook counting
# ---------------------------------------------------------------------------


def get_active_hook_count(
    hooks: dict[str, Any],
) -> dict[str, int]:
    """Return the count of hook groups per event type."""
    counts: dict[str, int] = {}
    for event_name, groups in hooks.items():
        if isinstance(groups, list):
            counts[event_name] = len(groups)
    return counts


# ---------------------------------------------------------------------------
# Convenience: fire hooks at lifecycle points
# ---------------------------------------------------------------------------


def fire_session_start(
    registry_path: str | None = None,
) -> list[dict[str, Any]]:
    """Fire SessionStart event. Call at startup."""
    hooks = load_hooks_registry(registry_path)
    return fire_event("SessionStart", hooks)


def fire_stop(
    registry_path: str | None = None,
) -> list[dict[str, Any]]:
    """Fire Stop event. Call at shutdown."""
    hooks = load_hooks_registry(registry_path)
    return fire_event("Stop", hooks)


def fire_stop_failure(
    registry_path: str | None = None,
) -> list[dict[str, Any]]:
    """Fire StopFailure event. Call on API/execution errors."""
    hooks = load_hooks_registry(registry_path)
    return fire_event("StopFailure", hooks)
