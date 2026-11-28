"""Tool trace lines and localized pre-execution action sentences.

Split out of ``tools/__init__.py`` (speed-first plan, P0-3). The package
re-exports these names; package-level state is read at call time.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from ..runtime.spinner import stop_quietly as _spinner_stop_quietly
from ..utils.secret_mask import mask_args as _mask_args
from .context import get_callbacks
from .i18n_helper import make_tool_translator

# Messages keep using the package's catalog (tools/__init__.json).
_ = make_tool_translator(Path(__file__).resolve().parent / "__init__.py")

_TRACE_LOCK = Lock()

# The most recent CLI tool trace, used to nest the result line under its
# call in the tree display. ``consumed`` flips once a result line has
# been nested under it, so a later same-name result cannot reuse it.
_LAST_TRACE: dict[str, Any] = {"name": "", "consumed": True}


def _localized_tool_action(name: str, args: dict[str, Any]) -> str:
    """Return the tool's localized pre-execution action line, or ``""``.

    Only used when ``UAGENT_SHOW_TOOL_RESULTS=2``. The text is masked and
    bounded by the display helper, so tools may describe paths and commands
    without sanitizing them here.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOL_DESCRIBERS,
    )

    describer = _TOOL_DESCRIBERS.get(name)
    if not callable(describer):
        return ""
    try:
        from ..runtime.tool_result_display import (
            bound_display_text,
            tool_result_display_mode,
        )

        if tool_result_display_mode() < 2:
            return ""
        text = describer(dict(args or {}))
    except Exception:
        return ""
    if text is None:
        return ""
    return bound_display_text(text)


_GENERIC_ACTION_ARG_KEYS = (
    "action",
    "operation",
    "mode",
    "filename",
    "path",
    "paths",
    "file_path",
    "input_path",
    "output_path",
    "source_path",
    "target_path",
    "pcap_path",
    "zip_path",
    "location",
    "url",
    "origin",
    "destination",
    "target",
    "ip",
    "host",
    "port",
    "dev",
    "devname",
    "device_id",
    "query",
    "q",
    "pattern",
    "actor",
    "uri",
    "node_id",
    "object_type",
    "object_instance",
    "eoj",
    "obj",
    "epc",
    "command",
    "sheet_name",
    "output_dir",
    "namespace",
    "bridge",
    "ctrl",
    "task_id",
    "value",
    "selector",
    "method",
    "type",
    "address",
    "recipient",
    "external_port",
    "internal_ip",
    "group",
    "city",
    "prefecture",
    "zipcode",
    "title",
    "subject",
    "model",
    "index",
    "section",
    "depth",
    "limit",
    "count",
    "actions",
    "files",
    "targets",
    "body",
    "code",
    "commands",
    "content",
    "data",
    "data_hex",
    "message",
    "messages",
    "patch_text",
    "payload",
    "prompt",
    "script",
    "text",
    "texts",
)

_GENERIC_CONTENT_ARG_KEYS = frozenset(
    {
        "body",
        "code",
        "commands",
        "content",
        "data",
        "data_hex",
        "message",
        "messages",
        "patch_text",
        "payload",
        "prompt",
        "script",
        "text",
        "texts",
    }
)


def _format_generic_action_value(
    key: str, value: Any, parameter_schema: dict[str, Any]
) -> str:
    """Format a schema-described argument without dumping free-form payloads."""

    description = parameter_schema.get("description")
    description = " ".join(description.split()) if isinstance(description, str) else ""
    content_hint = (
        key.lower() in _GENERIC_CONTENT_ARG_KEYS
        or bool(
            _GENERIC_CONTENT_DESCRIPTION_RE.search(
                f"{key.replace('_', ' ')} {description}"
            )
        )
        or (
            isinstance(value, str)
            and key.lower() not in _GENERIC_ACTION_ARG_KEYS
            and not _GENERIC_SAFE_DESCRIPTION_RE.search(description)
        )
    )

    if content_hint:
        if isinstance(value, str):
            rendered = f"<{len(value)} chars>"
        elif isinstance(value, (list, dict)):
            rendered = f"<{len(value)} items>"
        else:
            rendered = "<provided>"
    elif key.lower() == "actions" and isinstance(value, list):
        kinds = [
            str(item.get("type") or item.get("action"))
            for item in value[:4]
            if isinstance(item, dict) and (item.get("type") or item.get("action"))
        ]
        suffix = f" ({', '.join(kinds)})" if kinds else ""
        rendered = f"<{len(value)} steps>{suffix}"
    elif isinstance(value, str):
        compact = " ".join(value.split())
        if len(compact) > 80:
            compact = compact[:77] + "..."
        rendered = json.dumps(compact, ensure_ascii=False)
    elif isinstance(value, list):
        if any(isinstance(item, dict) for item in value):
            rendered = f"<{len(value)} items>"
        else:
            preview = value[:3]
            rendered = json.dumps(preview, ensure_ascii=False, separators=(",", ":"))
            if len(value) > len(preview):
                rendered += f" (+{len(value) - len(preview)} more)"
    elif isinstance(value, dict):
        rendered = f"<{len(value)} fields>"
    else:
        rendered = json.dumps(value, ensure_ascii=False)

    return f"{key}={rendered}"


_GENERIC_CONTENT_DESCRIPTION_RE = re.compile(
    r"\b(?:free[- ]form text|text content|message body|prompt|payload|body|content|"
    r"source code|script|unified diff|patch text|raw data|binary data)\b",
    re.IGNORECASE,
)
_GENERIC_SAFE_DESCRIPTION_RE = re.compile(
    r"\b(?:path|file name|filename|url|uri|host|ip address|address|identifier|"
    r"\bid\b|name|port|query|pattern|selector|command|action|operation|mode|"
    r"provider|model|status|location|destination|origin|value|number)\b",
    re.IGNORECASE,
)


def _tool_function_spec_for_action(name: str) -> dict[str, Any]:
    """Return a registered function schema for a tool action preview."""
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        TOOL_SPECS,
        _TOOLS_LOCK,
    )

    with _TOOLS_LOCK:
        for spec in TOOL_SPECS:
            function = spec.get("function")
            if isinstance(function, dict) and function.get("name") == name:
                return function
    return {}


def _generic_action_details(name: str, args: dict[str, Any]) -> list[str]:
    """Return the formatted important-argument summaries for a tool call.

    Shared by the generic action sentence and the tree display's content
    tier. Free-form payloads are represented by their size, not printed
    verbatim, and values are secret-masked before formatting.
    """

    try:
        safe_args = _mask_args(args or {})
    except Exception:
        safe_args = {}
    if not isinstance(safe_args, dict):
        safe_args = {}

    function = _tool_function_spec_for_action(name)
    parameters = function.get("parameters")
    properties = parameters.get("properties") if isinstance(parameters, dict) else None
    if not isinstance(properties, dict):
        properties = {}

    by_lower = {str(key).lower(): str(key) for key in safe_args}
    ordered_keys: list[str] = []
    for key in _GENERIC_ACTION_ARG_KEYS:
        original_key = by_lower.get(key)
        if original_key and original_key not in ordered_keys:
            ordered_keys.append(original_key)

    # Include unfamiliar plugin arguments only when their schema clearly
    # identifies them as a target (for example, a file path or URL).
    for key in safe_args:
        if str(key) in ordered_keys:
            continue
        parameter = properties.get(key)
        description = (
            parameter.get("description") if isinstance(parameter, dict) else ""
        )
        if isinstance(description, str) and _GENERIC_SAFE_DESCRIPTION_RE.search(
            description
        ):
            ordered_keys.append(str(key))

    details: list[str] = []
    for key in ordered_keys:
        value = safe_args.get(key)
        if value is None or value == "":
            continue
        parameter = properties.get(key)
        if not isinstance(parameter, dict):
            parameter = {}
        details.append(_format_generic_action_value(key, value, parameter))
        if len(details) >= 3:
            break
    return details


def _generic_tool_action(name: str, args: dict[str, Any]) -> str:
    """Build an i18n-aware action summary for tools without a describer.

    The registered tool schema supplies the localized purpose and parameter
    descriptions. Unknown/plugin tools still get a summary from their arguments.
    Free-form payloads are represented by their size, not printed verbatim.
    """

    summary = "; ".join(_generic_action_details(name, args)) or name
    return str(
        _(
            "trace.generic_action",
            default="About to use %(tool)s: %(summary)s",
            tool=name,
            summary=summary,
        )
    )


def tool_action_sentence(name: str, args: dict[str, Any]) -> str:
    """Return the localized one-line action sentence for a tool call.

    Shared with the [TOOL] trace's mode-2 rendering: the tool's own
    describer via :func:`build_tool_description` when it has one,
    otherwise the generic action sentence with a summary of the
    arguments. Computed regardless of the local display mode, for
    consumers such as the Nostr remote progress feed. Returns ``""``
    when no sentence can be produced.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        build_tool_description,
    )

    text = build_tool_description(name, args)
    if text:
        return text
    try:
        from ..runtime.tool_result_display import bound_display_text

        return bound_display_text(_generic_tool_action(name, args))
    except Exception:
        return ""


def _emit_remote_tool_progress(name: str, args: dict[str, Any]) -> None:
    """Mirror one tool start to the active remote/bitchat requester."""
    try:
        from .. import core as _core

        runtime = getattr(_core, "_nostr_remote_runtime", None)
        note_bitchat = None
        try:
            from .pybitchat_shared import (
                bitchat_turn_active,
                note_bitchat_tool_action,
            )

            if bitchat_turn_active():
                note_bitchat = note_bitchat_tool_action
        except Exception:
            pass
        if runtime is None and note_bitchat is None:
            return
        # Background sub-agent jobs share the dispatcher; their tools are
        # not part of the foreground remote turn.
        from ..runtime.sub_agent_jobs import current_sub_agent_job_mode

        if current_sub_agent_job_mode() == "background":
            return
        text = tool_action_sentence(name, args)
        if text:
            if runtime is not None:
                runtime.note_tool_action(name, text)
            if note_bitchat is not None:
                note_bitchat(name, text)
    except Exception:
        pass


def _tool_trace_body(name: str, args: dict[str, Any]) -> str:
    """Return the trace body for one pre-execution tool call.

    Mode 2 replaces the machine-readable ``name=/args=`` body with the tool's
    localized action sentence. Tools without a describer get a generic summary
    of common action/target arguments instead of a raw argument dump.
    """

    localized = _localized_tool_action(name, args)
    if localized:
        return localized
    try:
        from ..runtime.tool_result_display import tool_result_display_mode

        if tool_result_display_mode() >= 2:
            from ..runtime.tool_result_display import bound_display_text

            return bound_display_text(_generic_tool_action(name, args))
    except Exception:
        pass
    masked = _mask_args(args or {})
    try:
        arg_str = json.dumps(
            masked,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except Exception:
        arg_str = str(masked)
    return f"name={name} args={arg_str}"


def _should_emit_tool_trace(name: str) -> bool:
    """Return whether the tool's trace is enabled by its registered spec."""
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOL_TRACE_FLAGS,
    )

    return _TOOL_TRACE_FLAGS.get(name, True)


def _emit_trace_line(line: str) -> None:
    """Show one tool trace line, typed as tool output.

    The line always gathers into the shared output document under
    the "tool" kind. When the console view is active it renders the
    line from the document; otherwise the line is printed exactly
    as before.
    """
    view = None
    try:
        from ..cli_impl.console_view import active_view

        view = active_view()
    except Exception:
        view = None
    try:
        from ..runtime import display_channel

        display_channel.post_segment("tool", line + "\n")
    except Exception:
        pass
    if view is None:
        print(line, flush=True)


def emit_tool_result_tree_line(name: str, status: str, summary: str) -> None:
    """Print one tool result as the result tier of the tree display.

    When the immediately preceding tool trace belongs to the same tool,
    the line nests under that call (``  └ ...``). Otherwise — notably
    for parallel batches, whose traces are all emitted before any
    result — the line stands on its own and names the tool.
    """
    try:
        from ..runtime.tool_result_display import bound_display_text

        text = bound_display_text(f"{status}: {summary}" if summary else status)
        with _TRACE_LOCK:
            _spinner_stop_quietly()
            if _LAST_TRACE["name"] == name and not _LAST_TRACE["consumed"]:
                _LAST_TRACE["consumed"] = True
                _emit_trace_line(f"  └ {text}")
            else:
                _emit_trace_line(f"└ {name}: {text}")
    except Exception:
        return


def _emit_tool_trace(name: str, args: dict[str, Any]) -> None:
    """Print the pre-execution tool trace, localized in mode 2."""
    try:
        localized = _localized_tool_action(name, args)
        body = _tool_trace_body(name, args)

        # The timestamp is opt-in (UAGENT_TOOL_TRACE_TIMESTAMP);
        # by default the trace line is just the prefix and body.
        try:
            from ..runtime.tool_result_display import tool_trace_timestamp_enabled

            show_ts = tool_trace_timestamp_enabled()
        except Exception:
            show_ts = False
        ts_prefix = datetime.now().strftime("%Y-%m-%d %H:%M:%S ") if show_ts else ""
        try:
            from .context import get_active_sub_agent

            active_sub_agent = get_active_sub_agent()
        except Exception:
            active_sub_agent = None
        trace_prefix = (
            f"[SUB-AGENT: {active_sub_agent}] " if active_sub_agent else "[TOOL] "
        )
        with _TRACE_LOCK:
            # Clear the spinner line first (no-op when disabled).
            _spinner_stop_quietly()
            # Windows console color attributes are process-global. Serialize
            # tool traces with status output so [TOOL] cannot inherit the
            # [STATE] color.
            try:
                from .. import core as _core

                if bool(getattr(_core, "_is_web", False)):
                    # Web already has room-scoped message delivery. Reuse the
                    # same masked/localized text as CLI without exposing raw
                    # tool results or writing trace data to model history.
                    try:
                        from ..runtime.tool_result_display import bound_display_text

                        sink = getattr(get_callbacks(), "tool_trace", None)
                        if sink is not None:
                            sink(name, bound_display_text(body))
                    except Exception:
                        pass
                    return
                if bool(getattr(_core, "IS_GUI", False)):
                    return
                with _core.print_lock:
                    _emit_trace_line(f"{trace_prefix}{ts_prefix}{body}")
                    _LAST_TRACE["name"] = name
                    _LAST_TRACE["consumed"] = False
                    if localized:
                        # Content tier: the important arguments, under
                        # the describer's action sentence. Tools without
                        # a describer already carry them in the sentence.
                        details = _generic_action_details(name, args)
                        if details:
                            _emit_trace_line("└ " + "; ".join(details))
            except Exception:
                print(f"{trace_prefix}{ts_prefix}{body}", flush=True)
    except Exception:
        return
