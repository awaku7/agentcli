"""Hooks execution engine for uagent plugin hooks.

Supports loading hooks from registry, event matching, and executing
command-type hooks. Designed to integrate with runtime lifecycle.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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


def _resolve_plugin_root(plugin_name: str, explicit: str | None = None) -> str:
    """Resolve a plugin install directory for Claude-compatible vars."""
    if explicit:
        p = Path(str(explicit)).expanduser()
        if p.is_dir():
            return str(p.resolve())

    name = str(plugin_name or "").strip()
    if not name:
        return ""

    # Prefer known plugin roots (user/project, uag/claude).
    candidates: list[Path] = []
    try:
        candidates.append(get_state_dir() / "plugins" / name)
    except Exception:
        pass
    home = Path.home()
    cwd = Path.cwd()
    for base in (
        home / ".uag" / "plugins" / name,
        home / ".claude" / "plugins" / name,
        cwd / ".uag" / "plugins" / name,
        cwd / ".claude" / "plugins" / name,
    ):
        candidates.append(base)

    seen: set[str] = set()
    for c in candidates:
        try:
            key = str(c.resolve()).lower()
        except Exception:
            key = str(c).lower()
        if key in seen:
            continue
        seen.add(key)
        if c.is_dir():
            return str(c.resolve())
    return ""


def _annotate_hook_group(
    group: Any,
    *,
    plugin_name: str,
    plugin_root: str,
) -> Any:
    """Attach plugin identity/root onto hook groups and leaf hook defs."""
    if isinstance(group, dict):
        out = dict(group)
        out.setdefault("_plugin_name", plugin_name)
        if plugin_root:
            out.setdefault("_plugin_root", plugin_root)
        nested = out.get("hooks")
        if isinstance(nested, list):
            out["hooks"] = [
                _annotate_hook_group(
                    h, plugin_name=plugin_name, plugin_root=plugin_root
                )
                for h in nested
            ]
        return out
    return group


def load_hooks_registry(registry_path: str | None = None) -> dict[str, Any]:
    """Load hooks from the registry file.

    Returns hooks organized as event_name -> list of hook entries.
    Returns empty dict if registry is missing or invalid.

    Each hook group/def is annotated with:
      - ``_plugin_name``
      - ``_plugin_root`` (best-effort absolute plugin directory)
    so command expansion can resolve Claude Code's ``${CLAUDE_PLUGIN_ROOT}``.
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

    roots_map = data.get("plugin_roots", {})
    if not isinstance(roots_map, dict):
        roots_map = {}

    # Merge all hooks from all plugins, organized by event
    merged: dict[str, list[dict[str, Any]]] = {}
    for plugin_name, plugin_hooks in plugins.items():
        if not isinstance(plugin_hooks, dict):
            continue
        # Skip metadata-only keys if present under plugins
        if str(plugin_name).startswith("_"):
            continue
        explicit_root = None
        if isinstance(roots_map.get(plugin_name), str):
            explicit_root = roots_map.get(plugin_name)
        # Also allow per-plugin metadata block: plugins[name]._plugin_root
        meta_root = plugin_hooks.get("_plugin_root")
        if isinstance(meta_root, str) and meta_root.strip():
            explicit_root = meta_root
        plugin_root = _resolve_plugin_root(str(plugin_name), explicit_root)

        for event_name, hook_groups in plugin_hooks.items():
            if str(event_name).startswith("_"):
                continue
            if not isinstance(hook_groups, list):
                continue
            if event_name not in merged:
                merged[event_name] = []
            for group in hook_groups:
                merged[event_name].append(
                    _annotate_hook_group(
                        group,
                        plugin_name=str(plugin_name),
                        plugin_root=plugin_root,
                    )
                )

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
    stdin_data: str | None = None,
) -> dict[str, Any]:
    """Execute a single hook.

    Args:
        hook: Hook definition dict with type, command, etc.
        timeout_ms: Timeout in milliseconds.
        tool_name: Context: name of the tool being used (for PreToolUse etc.)
        event_name: Context: name of the event firing.
        stdin_data: Optional text fed to command hooks on stdin (Claude Code
            feeds JSON for UserPromptSubmit / tool events).

    Returns:
        Dict with ok, stdout, stderr, etc. May include decision/reason when
        stdout is Claude-compatible JSON.
    """
    hook_type = hook.get("type", "")

    if hook_type not in SUPPORTED_TYPES:
        return {
            "ok": False,
            "error": f"Unsupported hook type: {hook_type}. Supported: {SUPPORTED_TYPES}",
        }

    if hook_type == COMMAND_TYPE:
        result = _execute_command_hook(
            hook, timeout_ms=timeout_ms, stdin_data=stdin_data
        )
    elif hook_type == HTTP_TYPE:
        result = _execute_http_hook(hook, timeout_ms=timeout_ms, stdin_data=stdin_data)
    elif hook_type == PROMPT_TYPE:
        result = _execute_prompt_hook(hook, timeout_ms=timeout_ms)
    elif hook_type == MCP_TOOL_TYPE:
        result = _execute_mcp_tool_hook(hook, timeout_ms=timeout_ms)
    elif hook_type == AGENT_TYPE:
        result = _execute_agent_hook(hook, timeout_ms=timeout_ms)
    else:
        return {"ok": False, "error": f"Unknown hook type: {hook_type}"}

    return _annotate_hook_result(result)


def _annotate_hook_result(result: dict[str, Any]) -> dict[str, Any]:
    """Attach decision/reason parsed from stdout/body when present."""
    if not isinstance(result, dict):
        return result
    raw = result.get("stdout")
    if not (isinstance(raw, str) and raw.strip()):
        raw = result.get("body")
    decision = parse_hook_decision(raw if isinstance(raw, str) else None)
    if decision:
        result.setdefault("decision", decision.get("decision"))
        if decision.get("reason") is not None:
            result.setdefault("reason", decision.get("reason"))
    return result


def _execute_command_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
    stdin_data: str | None = None,
) -> dict[str, Any]:
    """Execute a command-type hook via subprocess."""
    command = hook.get("command", "")
    if not command:
        return {"ok": False, "error": "Command hook has no command."}

    plugin_root = ""
    raw_root = hook.get("_plugin_root")
    if isinstance(raw_root, str) and raw_root.strip():
        plugin_root = raw_root.strip()
    else:
        plugin_name = str(hook.get("_plugin_name") or "").strip()
        if plugin_name:
            plugin_root = _resolve_plugin_root(plugin_name)

    # Substitute environment variables like ${UAGENT_PLUGIN_ROOT}
    # and Claude Code compatible ${CLAUDE_PLUGIN_ROOT}.
    expanded = _expand_vars(command, plugin_root=plugin_root)

    env = os.environ.copy()
    if plugin_root:
        # Claude Code compatibility + uagent alias.
        env.setdefault("CLAUDE_PLUGIN_ROOT", plugin_root)
        env.setdefault("UAGENT_PLUGIN_ROOT", plugin_root)
        # Some scripts also read process.env without ${} expansion.
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root

    try:
        run_kwargs: dict[str, Any] = {
            "shell": True,
            "capture_output": True,
            "text": True,
            "timeout": timeout_ms / 1000.0,
            "env": env,
            "cwd": plugin_root or None,
        }
        # Feed stdin when provided (UserPromptSubmit JSON, etc.).
        if stdin_data is not None:
            run_kwargs["input"] = stdin_data
        result = subprocess.run(expanded, **run_kwargs)
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

        # Add all hooks in this group (inherit plugin root/name from group)
        if isinstance(group_hooks, list):
            for h in group_hooks:
                if isinstance(h, dict):
                    leaf = dict(h)
                    if group.get("_plugin_name") and not leaf.get("_plugin_name"):
                        leaf["_plugin_name"] = group.get("_plugin_name")
                    if group.get("_plugin_root") and not leaf.get("_plugin_root"):
                        leaf["_plugin_root"] = group.get("_plugin_root")
                    matched.append(leaf)

    return matched


def fire_event(
    event_name: str,
    hooks: dict[str, Any],
    *,
    tool_name: str | None = None,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
    stdin_data: str | None = None,
) -> list[dict[str, Any]]:
    """Fire an event, executing all matching hooks.

    Args:
        stdin_data: Optional stdin text for command hooks (JSON string).

    Returns list of execution results.
    """
    matching = find_matching_hooks(event_name, hooks, tool_name=tool_name)
    if not matching:
        return []

    results: list[dict[str, Any]] = []
    for hook_def in matching:
        result = execute_hook(
            hook_def,
            timeout_ms=timeout_ms,
            tool_name=tool_name,
            event_name=event_name,
            stdin_data=stdin_data,
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Variable expansion
# ---------------------------------------------------------------------------

# Compiled patterns for variable expansion
_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_vars(command: str, *, plugin_root: str | None = None) -> str:
    """Expand ${VAR} style variables in a command.

    Supports:
    - ${CLAUDE_PLUGIN_ROOT} -> this plugin's directory (Claude Code compat)
    - ${UAGENT_PLUGIN_ROOT} -> same as CLAUDE_PLUGIN_ROOT when known,
      otherwise the shared plugins root (~/.uag/plugins)
    - ${UAGENT_PROJECT_DIR} / ${CLAUDE_PROJECT_DIR} -> project directory
    - Any ${ENV_VAR} -> os.environ lookup

    Unknown variables are left as-is.
    """
    root = (plugin_root or "").strip()
    shared_plugins_root = str(get_state_dir() / "plugins")
    project_dir = os.getcwd()

    def _replace(m: re.Match) -> str:
        var_name = m.group(1)

        if var_name in ("CLAUDE_PLUGIN_ROOT", "UAGENT_PLUGIN_ROOT"):
            if root:
                return root
            # Fall back to env, then shared plugins root.
            env_val = os.environ.get(var_name) or os.environ.get("CLAUDE_PLUGIN_ROOT")
            if env_val:
                return env_val
            if var_name == "UAGENT_PLUGIN_ROOT":
                return shared_plugins_root
            return m.group(0)
        if var_name in ("UAGENT_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
            return project_dir
        return os.environ.get(var_name, m.group(0))

    return _VAR_RE.sub(_replace, command)


# ---------------------------------------------------------------------------
# HTTP hook execution
# ---------------------------------------------------------------------------


def _execute_http_hook(
    hook: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
    stdin_data: str | None = None,
) -> dict[str, Any]:
    """Execute an http-type hook via urllib."""
    url = hook.get("url", "")
    if not url:
        return {"ok": False, "error": "HTTP hook has no url."}

    method = hook.get("method", "POST").upper()
    if method not in ("POST", "PUT", "PATCH"):
        return {
            "ok": False,
            "error": f"Unsupported HTTP method: {method}. Supported: POST, PUT, PATCH",
        }

    import urllib.request
    import urllib.error

    if "body" in hook:
        body_obj = hook.get("body", {})
    elif stdin_data is not None:
        # Prefer structured stdin JSON when hook body is omitted.
        try:
            body_obj = json.loads(stdin_data) if stdin_data.strip() else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            body_obj = {"raw": stdin_data}
    else:
        body_obj = {}
    body_bytes = json.dumps(body_obj).encode("utf-8")
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

        result = mcp_run(
            {
                "server_name": _expand_vars(server),
                "tool_name": tool,
                "arguments": args,
            }
        )
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
    stdin_data: str | None = None,
) -> list[dict[str, Any]]:
    """Fire a tool-related event with context.

    Supports PreToolUse, PostToolUse, PostToolUseFailure.
    When stdin_data is omitted, a Claude-compatible JSON payload is built
    from tool_name/args/result/error.
    """
    matching = find_matching_hooks(event_name, hooks, tool_name=tool_name)
    if not matching:
        return []

    payload = stdin_data
    if payload is None:
        payload = build_hook_stdin_json(
            event_name,
            tool_name=tool_name,
            tool_input=tool_args or {},
            tool_response=tool_result,
            tool_error=tool_error,
        )

    results: list[dict[str, Any]] = []
    for hook_def in matching:
        result = execute_hook(
            hook_def,
            timeout_ms=timeout_ms,
            tool_name=tool_name,
            event_name=event_name,
            stdin_data=payload,
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Hook stdout -> conversation context injection
# ---------------------------------------------------------------------------
#
# Claude Code injects SessionStart / UserPromptSubmit hook stdout into the
# model context. uagent mirrors that additively via system messages marked
# with ``[HOOK] `` so existing callers that ignore fire_* results stay safe.

HOOK_CONTEXT_MARKER = "[HOOK] "
_TRIVIAL_HOOK_STDOUT = frozenset(
    {
        "",
        "ok",
        "OK",
        "done",
        "Done",
        "success",
        "Success",
        "true",
        "1",
        "{}",
        "null",
    }
)

_pending_session_hook_texts: list[str] = []


def hook_context_marker_prefix() -> str:
    return HOOK_CONTEXT_MARKER


def build_hook_stdin_payload(
    event_name: str,
    *,
    prompt: str | None = None,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_response: str | None = None,
    tool_error: str | None = None,
    session_id: str | None = None,
    transcript_path: str | None = None,
    cwd: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Claude Code-compatible hook stdin JSON object."""
    payload: dict[str, Any] = {
        "hook_event_name": str(event_name or ""),
        "cwd": cwd if isinstance(cwd, str) and cwd else os.getcwd(),
    }
    if session_id:
        payload["session_id"] = session_id
    if transcript_path:
        payload["transcript_path"] = transcript_path
    if prompt is not None:
        payload["prompt"] = prompt
    if tool_name:
        payload["tool_name"] = tool_name
    if tool_input is not None:
        payload["tool_input"] = tool_input
    if tool_response:
        payload["tool_response"] = tool_response
    if tool_error:
        payload["tool_error"] = tool_error
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            if k not in payload:
                payload[k] = v
    return payload


def build_hook_stdin_json(
    event_name: str,
    **kwargs: Any,
) -> str:
    """Serialize :func:`build_hook_stdin_payload` as UTF-8 JSON text."""
    return json.dumps(
        build_hook_stdin_payload(event_name, **kwargs),
        ensure_ascii=False,
    )


def build_user_prompt_submit_stdin(
    prompt: str,
    *,
    session_id: str | None = None,
    transcript_path: str | None = None,
    cwd: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """JSON stdin for UserPromptSubmit (genshijin mode-tracker compatible)."""
    return build_hook_stdin_json(
        "UserPromptSubmit",
        prompt=prompt if isinstance(prompt, str) else str(prompt or ""),
        session_id=session_id,
        transcript_path=transcript_path,
        cwd=cwd,
        extra=extra,
    )


def parse_hook_decision(stdout: str | None) -> dict[str, Any] | None:
    """Parse Claude-compatible decision JSON from hook stdout.

    Recognizes:
      - ``{"decision": "block"|"approve", "reason": "..."}``
      - ``hookSpecificOutput.decision`` (less common)

    Returns dict with at least ``decision`` (lowercased), optional ``reason``.
    """
    text = (stdout or "").strip()
    if not text or text[0] not in "{[":
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    decision = data.get("decision")
    reason = data.get("reason")
    hso = data.get("hookSpecificOutput")
    if isinstance(hso, dict):
        if decision is None:
            decision = hso.get("decision")
        if reason is None:
            reason = hso.get("reason")
        # permissionDecision is used by some PreToolUse hooks
        if decision is None:
            pd = hso.get("permissionDecision")
            if isinstance(pd, str):
                decision = pd

    if not isinstance(decision, str) or not decision.strip():
        return None
    out: dict[str, Any] = {"decision": decision.strip().lower()}
    if isinstance(reason, str):
        out["reason"] = reason
    elif reason is not None:
        out["reason"] = str(reason)
    return out


def collect_hook_block_decision(
    results: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return the first block decision from hook results, if any.

    A block is honored even when the command exit code is non-zero, as long as
    stdout carries an explicit decision=block (Claude Code behavior).
    """
    for r in results or []:
        if not isinstance(r, dict):
            continue
        decision = r.get("decision")
        reason = r.get("reason")
        if not decision:
            raw = r.get("stdout")
            if not (isinstance(raw, str) and raw.strip()):
                raw = r.get("body")
            parsed = parse_hook_decision(raw if isinstance(raw, str) else None)
            if not parsed:
                continue
            decision = parsed.get("decision")
            reason = parsed.get("reason") if reason is None else reason
        if str(decision or "").strip().lower() != "block":
            continue
        out: dict[str, Any] = {"decision": "block"}
        if isinstance(reason, str):
            out["reason"] = reason
        elif reason is not None:
            out["reason"] = str(reason)
        else:
            out["reason"] = ""
        return out
    return None


def fire_user_prompt_submit(
    prompt: str,
    *,
    registry_path: str | None = None,
    hooks: dict[str, Any] | None = None,
    session_id: str | None = None,
    transcript_path: str | None = None,
    cwd: str | None = None,
    timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fire UserPromptSubmit with Claude-compatible stdin JSON.

    Callers should:
      1. ``block = collect_hook_block_decision(results)`` and abort the turn if set
      2. ``inject_hook_context(..., replace_event=True)`` for additionalContext
    """
    reg = hooks if hooks is not None else load_hooks_registry(registry_path)
    stdin_data = build_user_prompt_submit_stdin(
        prompt,
        session_id=session_id,
        transcript_path=transcript_path,
        cwd=cwd,
        extra=extra,
    )
    return fire_event(
        "UserPromptSubmit",
        reg,
        timeout_ms=timeout_ms,
        stdin_data=stdin_data,
    )


def parse_hook_stdout_context(stdout: str | None) -> str | None:
    text = (stdout or "").strip()
    if not text or text in _TRIVIAL_HOOK_STDOUT:
        return None

    if text[0] in "{[":
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            data = None
        if isinstance(data, dict):
            hso = data.get("hookSpecificOutput")
            if isinstance(hso, dict):
                ac = hso.get("additionalContext")
                if isinstance(ac, str) and ac.strip():
                    return ac.strip()
            ac = data.get("additionalContext")
            if isinstance(ac, str) and ac.strip():
                return ac.strip()
            return None
        if isinstance(data, list):
            return None

    if text.lower() in {"ok", "done", "success", "true"}:
        return None
    return text


def collect_hook_context_texts(
    results: list[dict[str, Any]] | None,
) -> list[str]:
    out: list[str] = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        if r.get("ok") is False:
            continue
        # decision=block is a control signal, not LLM context.
        dec = r.get("decision")
        if not dec:
            raw_dec = r.get("stdout")
            if not (isinstance(raw_dec, str) and raw_dec.strip()):
                raw_dec = r.get("body")
            parsed = parse_hook_decision(raw_dec if isinstance(raw_dec, str) else None)
            if parsed:
                dec = parsed.get("decision")
        if str(dec or "").strip().lower() == "block":
            continue
        raw = r.get("stdout")
        if not (isinstance(raw, str) and raw.strip()):
            raw = r.get("body")
        ctx = parse_hook_stdout_context(raw if isinstance(raw, str) else None)
        if ctx:
            out.append(ctx)
    return out


def make_hook_system_content(text: str, *, event_name: str = "") -> str:
    ev = (event_name or "").strip() or "hook"
    body = (text or "").strip()
    return f"{HOOK_CONTEXT_MARKER}event={ev}\n{body}"


def _hook_message_event(content: str) -> str | None:
    if not isinstance(content, str) or not content.startswith(HOOK_CONTEXT_MARKER):
        return None
    first = content.split("\n", 1)[0]
    rest = first[len(HOOK_CONTEXT_MARKER) :].strip()
    if rest.startswith("event="):
        return rest[len("event=") :].strip() or None
    return None


def clear_hook_messages(
    messages_ref: list[dict[str, Any]] | None,
    *,
    event_name: str | None = None,
) -> int:
    if not isinstance(messages_ref, list):
        return 0
    before = len(messages_ref)
    ev_filter = (event_name or "").strip() or None

    def _keep(m: Any) -> bool:
        if not isinstance(m, dict) or m.get("role") != "system":
            return True
        content = m.get("content")
        if not isinstance(content, str) or not content.startswith(HOOK_CONTEXT_MARKER):
            return True
        if ev_filter is None:
            return False
        return _hook_message_event(content) != ev_filter

    messages_ref[:] = [m for m in messages_ref if _keep(m)]
    return before - len(messages_ref)


def _insert_system_after_leading_block(
    messages_ref: list[dict[str, Any]],
    msg: dict[str, Any],
) -> None:
    idx = 0
    while idx < len(messages_ref) and (
        isinstance(messages_ref[idx], dict)
        and messages_ref[idx].get("role") == "system"
    ):
        idx += 1
    messages_ref.insert(idx, msg)


def inject_hook_context(
    messages: list[dict[str, Any]] | None,
    results: list[dict[str, Any]] | None,
    *,
    event_name: str = "",
    replace_event: bool = False,
) -> int:
    if not isinstance(messages, list):
        return 0
    texts = collect_hook_context_texts(results)
    if not texts:
        return 0
    ev = (event_name or "").strip()
    if replace_event and ev:
        clear_hook_messages(messages, event_name=ev)
    n = 0
    for t in texts:
        content = make_hook_system_content(t, event_name=ev)
        _insert_system_after_leading_block(
            messages, {"role": "system", "content": content}
        )
        n += 1
    return n


def note_session_start_results(results: list[dict[str, Any]] | None) -> list[str]:
    global _pending_session_hook_texts
    texts = collect_hook_context_texts(results)
    _pending_session_hook_texts = list(texts)
    return list(texts)


def take_pending_session_hook_texts() -> list[str]:
    global _pending_session_hook_texts
    out = list(_pending_session_hook_texts)
    _pending_session_hook_texts = []
    return out


def inject_pending_session_hook_context(
    messages: list[dict[str, Any]] | None,
) -> int:
    texts = take_pending_session_hook_texts()
    if not texts or not isinstance(messages, list):
        return 0
    fake = [{"ok": True, "stdout": t} for t in texts]
    return inject_hook_context(
        messages, fake, event_name="SessionStart", replace_event=True
    )


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
    results = fire_event("SessionStart", hooks)
    # Stash for Web/GUI (messages may not exist yet). CLI injects from results
    # and should call take_pending_session_hook_texts() to avoid double inject.
    note_session_start_results(results)
    return results


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
