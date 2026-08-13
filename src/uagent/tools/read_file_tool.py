from __future__ import annotations

# /src/uagent/tools/read_file_tool.py
import json
import os
import threading
from typing import Any, Callable, Optional, cast

from .arg_util import get_int, get_path
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _json_err(message: str, **extra: Any) -> str:
    obj: dict[str, Any] = {"ok": False, "error": message}
    obj.update(extra)
    return json.dumps(obj, ensure_ascii=False)


def _is_probably_utf8_head(head: bytes) -> bool:
    """Heuristically detect whether bytes are UTF-8 text."""
    b = head or b""
    for cut in range(0, 4):
        try:
            (b if cut == 0 else b[:-cut]).decode("utf-8")
            return True
        except UnicodeDecodeError as e:
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


TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "x_parallel_safe": True,
    "function": {
        "name": "read_file",
        "description": _(
            "tool.description",
            default="Read file contents (max 1MB). Supports partial reading via start_line/max_lines.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read_file",
                "read file",
                "file read",
                "file contents",
                "read contents",
                "open file",
                "load file",
                "file reader",
                "text reader",
                "read text",
                "partial read",
                "max lines",
            ],
        ),
        "x_search_terms_en": [
            "read_file",
            "read file",
            "file read",
            "file contents",
            "read contents",
            "open file",
            "load file",
            "file reader",
            "text reader",
            "read text",
            "partial read",
            "max lines",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="Path of the file to read. Short path aliases @A{0} through @A{9} are supported.",
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
                "maxl": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.maxl.description",
                        default="Maximum number of lines to read. If omitted (null), read to EOF.",
                    ),
                    "default": None,
                },
                "page": {
                    "type": "integer",
                    "description": _(
                        "param.page.description",
                        default="Page number to read (1-based). Used in conjunction with max_lines.",
                    ),
                    "default": 1,
                },
                "head": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.head.description",
                        default="Number of lines to read from the beginning. Cannot be used with tail.",
                    ),
                    "default": None,
                },
                "tail": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.tail.description",
                        default="Number of lines to read from the end. Cannot be used with head.",
                    ),
                    "default": None,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()

    filename = get_path(args, "filename", get_path(args, "path", ""))
    if not filename:
        msg = _(
            "err.filename_missing",
            default="[read_file error] filename/path is not specified",
        )
        return _json_err(msg)

    # ``head``/``tail`` are the public tool arguments.  Keep the legacy
    # ``head_lines``/``tail_lines`` aliases for internal callers such as
    # :head and :tail commands.
    head_lines = args.get("head")
    if head_lines is None:
        head_lines = args.get("head_lines")
    tail_lines = args.get("tail")
    if tail_lines is None:
        tail_lines = args.get("tail_lines")

    max_lines: int | None

    if head_lines is not None and tail_lines is not None:
        msg = _(
            "err.dual_lines",
            default="[read_file error] head_lines and tail_lines cannot be specified together",
        )
        return _json_err(msg)

    # Reject negative line counts instead of allowing them to trigger
    # accidental one-line reads or other surprising behavior.
    for option_name, option_value in (
        ("head", head_lines),
        ("tail", tail_lines),
        ("maxl", args.get("maxl")),
    ):
        if option_value is not None:
            try:
                if int(option_value) < 0:
                    msg = _(
                        "err.negative_lines",
                        default="[read_file error] {option} cannot be negative",
                    ).format(option=option_name)
                    return _json_err(msg, option=option_name)
            except (TypeError, ValueError):
                msg = _(
                    "err.invalid_lines",
                    default="[read_file error] {option} must be an integer",
                ).format(option=option_name)
                return _json_err(msg, option=option_name)

    # A zero line count is a valid empty result, not a request for one line.
    if any(
        option_value is not None and int(option_value) == 0
        for option_value in (head_lines, tail_lines, args.get("maxl"))
    ):
        return ""

    try:
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

            with open(
                filename, "r", encoding=encoding, errors="replace", newline=None
            ) as f:
                total_lines = sum(1 for _ in f)

            if total_lines < tail_lines:
                start_line = 1
                max_lines = total_lines
            else:
                start_line = total_lines - tail_lines + 1
                max_lines = tail_lines
        else:
            raw_max_lines = args.get("maxl")
            if raw_max_lines is None:
                max_lines = None
            else:
                max_lines = int(raw_max_lines)

            raw_page = args.get("page", 1)
            try:
                page = int(raw_page)
            except (TypeError, ValueError):
                msg = _(
                    "err.invalid_page",
                    default="[read_file error] page must be an integer",
                )
                return _json_err(msg, option="page")
            if page < 1:
                msg = _(
                    "err.invalid_page",
                    default="[read_file error] page must be at least 1",
                )
                return _json_err(msg, option="page")
            if page > 1 and max_lines is None:
                msg = _(
                    "err.page_requires_maxl",
                    default="[read_file error] page requires maxl",
                )
                return _json_err(msg, option="page")
            if page > 1:
                start_line = (page - 1) * max_lines + 1
            else:
                start_line = max(1, get_int(args, "start_line", 1))

        max_bytes = cb.read_file_max_bytes

        with open(filename, "rb") as f:
            head = f.read(8192)
            if _is_probably_utf8_head(head):
                encoding = "utf-8"
            else:
                encoding = cb.cmd_encoding
                if encoding.lower() == "utf-8":
                    encoding = "cp932"

        lines: list[str] = []
        total_bytes = 0
        # Process physical lines in bounded binary chunks.  Long lines are
        # consumed without being accumulated and count as one physical line.
        chunk_size = max(1, min(max_bytes + 1, 65536))
        with open(filename, "rb") as f:
            i = 0
            while True:
                raw_line = f.readline(chunk_size)
                if not raw_line:
                    break

                i += 1
                has_newline = raw_line.endswith(b"\n")

                if i < start_line:
                    if not has_newline:
                        # Consume the rest of a skipped physical line without
                        # retaining it, so line numbering remains correct.
                        while True:
                            discarded = f.readline(chunk_size)
                            if not discarded or discarded.endswith(b"\n"):
                                break
                    continue

                # Preserve a selected long physical line only up to the
                # remaining byte budget, while consuming its remainder so it
                # is still counted as one physical line.
                if not has_newline:
                    reached_eof = False
                    while True:
                        discarded = f.readline(chunk_size)
                        if not discarded:
                            reached_eof = True
                            break
                        raw_line += discarded[: max(0, max_bytes - len(raw_line))]
                        if discarded.endswith(b"\n"):
                            has_newline = True
                            break
                    if reached_eof:
                        has_newline = True

                remaining_bytes = max_bytes - total_bytes
                if remaining_bytes <= 0:
                    lines.append(
                        _(
                            "msg.truncated",
                            default="\n[read_file truncated: byte limit {max_bytes} reached]",
                        ).format(max_bytes=max_bytes)
                    )
                    break

                if len(raw_line) > remaining_bytes or not has_newline:
                    prefix = raw_line[:remaining_bytes]
                    if prefix:
                        lines.append(prefix.decode(encoding, errors="replace"))
                    lines.append(
                        _(
                            "msg.truncated",
                            default="\n[read_file truncated: byte limit {max_bytes} reached]",
                        ).format(max_bytes=max_bytes)
                    )
                    break

                text_line = raw_line.decode(encoding, errors="replace")
                lines.append(text_line.replace("\r\n", "\n").replace("\r", "\n"))
                total_bytes += len(raw_line)
                if max_lines is not None and len(lines) >= max_lines:
                    break

        if not lines and start_line > 1:
            msg = _(
                "err.out_of_range",
                default="(file has only {count} lines, start_line {start_line} is out of range)",
            ).format(count=i, start_line=start_line)
            return _json_err(msg, count=i, start_line=start_line)

        if sync_file is not None and os.path.isfile(filename):
            try:
                threading.Thread(
                    target=sync_file, args=(filename, os.getcwd()), daemon=True
                ).start()
            except Exception:
                pass

        return "".join(lines)

    except Exception as e:
        msg = f"[read_file error] {type(e).__name__}: {e}"
        return _json_err(msg, exception=type(e).__name__)
