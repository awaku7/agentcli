"""Fast wc-style counters for files."""

from __future__ import annotations

import codecs
import json
import os
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:wc"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "file",
    "x_parallel_safe": True,
    "function": {
        "name": "wc",
        "description": _(
            "tool.description",
            default="Fast read-only count of lines, words, bytes, and characters in files.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["wc", "word count", "line count", "byte count", "file statistics"],
        ),
        "x_search_terms_en": [
            "wc",
            "word count",
            "line count",
            "byte count",
            "file statistics",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.paths.description", default="Files to count."
                    ),
                },
                "chunk_size": {
                    "type": "integer",
                    "default": 1048576,
                    "description": _(
                        "param.chunk_size.description",
                        default="Read buffer size in bytes; larger values are faster for large files.",
                    ),
                },
                "return": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.return.description", default="Output format."
                    ),
                },
            },
            "required": ["paths"],
            "additionalProperties": False,
        },
    },
}


def _count_file(path: str, chunk_size: int) -> dict[str, int]:
    lines = words = byte_count = chars = 0
    pending = b""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            byte_count += len(chunk)
            chars += len(decoder.decode(chunk, final=False))
            lines += chunk.count(b"\n")
            data = pending + chunk
            parts = data.split()
            if chunk[-1:].isspace():
                words += len(parts)
                pending = b""
            elif parts:
                words += max(len(parts) - 1, 0)
                pending = parts[-1]
            else:
                pending = data
    if pending:
        words += 1
    chars += len(decoder.decode(b"", final=True))
    return {
        "lines": lines,
        "words": words,
        "bytes": byte_count,
        "chars": chars,
    }


def run_tool(args: dict[str, Any]) -> str:
    paths = args.get("paths", [])
    try:
        chunk_size = int(args.get("chunk_size") or 1048576)
    except (TypeError, ValueError):
        return json.dumps({"ok": False, "error": "chunk_size must be an integer"})
    fmt = str(args.get("return") or "json")
    if not isinstance(paths, list) or not paths:
        return json.dumps({"ok": False, "error": "paths must be a non-empty array"})
    if chunk_size < 4096:
        return json.dumps({"ok": False, "error": "chunk_size must be >= 4096"})
    if fmt not in {"json", "text"}:
        return json.dumps({"ok": False, "error": "return must be json or text"})

    results: list[dict[str, Any]] = []
    for raw_path in paths:
        display_path = str(raw_path)
        if is_path_dangerous(display_path):
            results.append(
                {"path": display_path, "ok": False, "error": "dangerous path rejected"}
            )
            continue
        try:
            path = ensure_within_workdir(display_path)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            counts = _count_file(path, chunk_size)
            results.append({"path": path, "ok": True, **counts})
        except Exception as exc:
            results.append(
                {
                    "path": display_path,
                    "ok": False,
                    "error": f"count failed: {type(exc).__name__}: {exc}",
                }
            )

    if fmt == "text":
        return "\n".join(
            (
                f"{item['lines']} {item['words']} {item['bytes']} {item['chars']} {item['path']}"
                if item.get("ok")
                else f"ERROR {item['path']}: {item['error']}"
            )
            for item in results
        )
    return json.dumps(
        {"ok": all(item.get("ok") for item in results), "files": results},
        ensure_ascii=False,
    )
