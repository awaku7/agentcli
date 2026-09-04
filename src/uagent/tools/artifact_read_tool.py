"""Read a bounded portion of a session-owned tool-result artifact."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .context import get_callbacks
from .i18n_helper import make_tool_translator
from ..runtime.artifact_manager import ArtifactManager, ArtifactManagerError

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:artifact_read"
_MAX_LINES = 500
_MAX_CHARS = 50_000
_DEFAULT_MAX_CHARS = 12_000
_ARTIFACT_ID = re.compile(r"^[0-9a-f]{32}$")


def _json_result(**data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(message: str, **extra: Any) -> str:
    return _json_result(ok=False, error=message, **extra)


TOOL_SPEC: dict[str, Any] = {
    # Infrastructure tool: keep it available like tool_catalog/tool_load/
    # unload_tool, regardless of the selected tool genre.
    "tool_level": 0,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "artifact_read",
        "description": _(
            "tool.description",
            default="Read a bounded portion of a previously stored tool-result artifact.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "artifact_read",
                "artifact",
                "tool result artifact",
                "artifact reference",
                "read artifact",
            ],
        ),
        "x_search_terms_en": [
            "artifact_read",
            "artifact",
            "tool result artifact",
            "artifact reference",
            "read artifact",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": _(
                        "param.artifact_id.description",
                        default="Artifact ID or artifact:// reference from an earlier tool result.",
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": _(
                        "param.start_line.description",
                        default="1-based line number to start reading from.",
                    ),
                },
                "max_lines": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LINES,
                    "default": 100,
                    "description": _(
                        "param.max_lines.description",
                        default="Maximum number of lines to return.",
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_CHARS,
                    "default": _DEFAULT_MAX_CHARS,
                    "description": _(
                        "param.max_chars.description",
                        default="Maximum number of UTF-8 characters to return.",
                    ),
                },
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
    },
}


def _positive_int(args: dict[str, Any], name: str, default: int) -> int | None:
    value = args.get(name, default)
    if isinstance(value, bool):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


def run_tool(args: dict[str, Any]) -> str:
    reference = str(args.get("artifact_id") or args.get("reference") or "").strip()
    if reference.startswith("artifact://"):
        reference = reference[len("artifact://") :]
    if not _ARTIFACT_ID.fullmatch(reference):
        return _error(
            _(
                "error.invalid_artifact_id",
                default="artifact_id must be a valid artifact ID or artifact:// reference",
            )
        )

    start_line = _positive_int(args, "start_line", 1)
    max_lines = _positive_int(args, "max_lines", 100)
    max_chars = _positive_int(args, "max_chars", _DEFAULT_MAX_CHARS)
    if start_line is None or max_lines is None or max_chars is None:
        return _error(
            _(
                "error.positive_integers",
                default="start_line, max_lines, and max_chars must be positive integers",
            )
        )
    if max_lines > _MAX_LINES:
        return _error(
            _(
                "error.max_lines",
                default="max_lines must be at most {limit}",
                limit=_MAX_LINES,
            )
        )
    if max_chars > _MAX_CHARS:
        return _error(
            _(
                "error.max_chars",
                default="max_chars must be at most {limit}",
                limit=_MAX_CHARS,
            )
        )

    callbacks = get_callbacks()
    workdir = (
        Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd()).expanduser().resolve()
    )
    manager: ArtifactManager | None = None
    try:
        manager = ArtifactManager(
            workdir,
            store=getattr(callbacks, "session_store", None),
        )
        item = manager.get(reference)
        active_session_id = getattr(callbacks, "session_id", None)
        if item.session_id != active_session_id:
            return _error(
                _(
                    "error.not_active_session",
                    default="artifact does not belong to the active session",
                )
            )

        path = manager.open(reference)
        lines: list[str] = []
        chars = 0
        lines_read = 0
        has_more = False
        content_truncated = False
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            # Bound readline() so a malformed or generated single-line result
            # cannot allocate the whole artifact just to return a 12k preview.
            # A truncated line is only drained when it is before start_line;
            # once output begins we can stop immediately with has_more=True.
            for line_number in range(1, start_line + max_lines + 1):
                line = stream.readline(_MAX_CHARS + 1)
                if not line:
                    break
                if line_number < start_line:
                    if len(line) > _MAX_CHARS and not line.endswith("\n"):
                        while line and not line.endswith("\n"):
                            line = stream.readline(8192)
                    continue
                if lines_read >= max_lines:
                    has_more = True
                    break
                remaining = max_chars - chars
                if len(line) > remaining:
                    if remaining:
                        lines.append(line[:remaining])
                    chars += min(len(line), remaining)
                    lines_read += 1
                    has_more = True
                    content_truncated = True
                    break
                lines.append(line)
                chars += len(line)
                lines_read += 1
        return _json_result(
            ok=True,
            artifact_id=reference,
            start_line=start_line,
            lines_read=lines_read,
            has_more=has_more,
            content_truncated=content_truncated,
            content="".join(lines),
        )
    except (ArtifactManagerError, OSError) as exc:
        return _error(str(exc))
    finally:
        if manager is not None:
            manager.close()


__all__ = ["TOOL_SPEC", "run_tool"]
