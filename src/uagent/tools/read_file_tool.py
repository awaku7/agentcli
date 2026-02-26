from __future__ import annotations

# /src/uagent/tools/read_file_tool.py
import os
import threading
from typing import Any, Callable, Dict, Optional, cast

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _is_probably_utf8_head(head: bytes) -> bool:
    """Heuristically detect whether bytes are UTF-8 text."""
    b = head or b""
    for cut in range(0, 4):
        try:
            (b if cut == 0 else b[:-cut]).decode("utf-8")
            return True
        except UnicodeDecodeError as e:
            # If the decode fails only because the chunk ended mid-character,
            # trimming will likely fix it in the next iteration.
            last = str(e).lower()
            if "unexpected end of data" in last:
                continue
            return False
    return False


try:
    from .semantic_search_files_tool import sync_file as _sync_file
except ImportError:
    _sync_file = None  # type: ignore[assignment]

sync_file: Optional[Callable[[str, str], Any]] = cast(
    Optional[Callable[[str, str], Any]], _sync_file
)
BUSY_LABEL = True
STATUS_LABEL = "tool:read_file"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": _(
            "tool.description",
            default="Read file contents (up to 1,000,000 bytes). Partial reading is possible by specifying start_line and max_lines.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="Read file contents.\n- For large files, partial reading using start_line/max_lines is recommended.\n- Newlines are normalized automatically.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="Path of the file to read.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="(Compatibility) Alias of filename.",
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "description": _(
                        "param.start_line.description",
                        default="Line number to start reading from (1-based). Default is 1.",
                    ),
                    "default": 1,
                },
                "max_lines": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.max_lines.description",
                        default="Maximum number of lines to read. If null, read to EOF.",
                    ),
                    "default": None,
                },
                "head_lines": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.head_lines.description",
                        default="Number of lines to read from the beginning. Cannot be used with tail_lines.",
                    ),
                    "default": None,
                },
                "tail_lines": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.tail_lines.description",
                        default="Number of lines to read from the end. Cannot be used with head_lines.",
                    ),
                    "default": None,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    filename = args.get("filename") or args.get("path") or ""
    if not filename:
        return _("err.filename_missing", default="[read_file error] filename/path is not specified")
    filename = os.path.expanduser(str(filename))

    head_lines = args.get("head_lines")
    tail_lines = args.get("tail_lines")

    max_lines: int | None

    if head_lines is not None and tail_lines is not None:
        return _(
            "err.dual_lines",
            default="[read_file error] head_lines and tail_lines cannot be specified together",
        )

    if head_lines is not None:
        head_lines = int(head_lines)
        start_line = 1
        max_lines = head_lines
    elif tail_lines is not None:
        tail_lines = int(tail_lines)
        try:
            with open(filename, "rb") as f:
                head = f.read(8192)
                if _is_probably_utf8_head(head):
                    encoding = "utf-8"
                else:
                    encoding = cb.cmd_encoding
                    if encoding.lower() == "utf-8":
                        encoding = "cp932"
        except Exception:
            encoding = "utf-8"

        with open(filename, "r", encoding=encoding, errors="replace", newline=None) as f:
            total_lines = sum(1 for _ in f)

        if total_lines < tail_lines:
            start_line = 1
            max_lines = total_lines
        else:
            start_line = total_lines - tail_lines + 1
            max_lines = tail_lines
    else:
        start_line = max(1, int(args.get("start_line", 1)))
        raw_max_lines = args.get("max_lines")
        if raw_max_lines is None:
            max_lines = None
        else:
            max_lines = int(raw_max_lines)

    max_bytes = cb.read_file_max_bytes

    try:
        with open(filename, "rb") as f:
            head = f.read(8192)
            if _is_probably_utf8_head(head):
                encoding = "utf-8"
            else:
                encoding = cb.cmd_encoding
                if encoding.lower() == "utf-8":
                    encoding = "cp932"

        lines = []
        total_bytes = 0
        with open(filename, "r", encoding=encoding, errors="replace", newline=None) as f:
            i = 0
            for i, line in enumerate(f, 1):
                if i < start_line:
                    continue
                lines.append(line)
                total_bytes += len(line.encode(encoding, errors="replace"))
                if max_lines is not None and len(lines) >= max_lines:
                    break
                if total_bytes > max_bytes:
                    lines.append(
                        _("msg.truncated", default="\n[read_file truncated: byte limit {max_bytes} reached]").format(
                            max_bytes=max_bytes
                        )
                    )
                    break

        if not lines and start_line > 1:
            return _(
                "err.out_of_range",
                default="(file has only {count} lines, start_line {start_line} is out of range)",
            ).format(count=i, start_line=start_line)

        if sync_file is not None and os.path.isfile(filename):
            try:
                threading.Thread(
                    target=sync_file, args=(filename, os.getcwd()), daemon=True
                ).start()
            except Exception:
                pass

        return "".join(lines)
    except Exception as e:
        return f"[read_file error] {type(e).__name__}: {e}"
