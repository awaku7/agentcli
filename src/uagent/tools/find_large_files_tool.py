# tools/find_large_files_tool.py
"""find_large_files_tool

A tool for finding large files in a directory.

Purpose:
- Identify the causes of workdir bloat
- Organize products and logs

Safety:
- Read-only (stat only).
- Rejects roots or dangerous paths outside of workdir (compliant with safe_file_ops_extras).

Note:
- Scanning can be heavy, so control it with top_n / min_bytes / exclude_dirs.
"""

from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple, TypedDict

from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:find_large_files"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "find_large_files",
        "description": _(
            "tool.description",
            default="Searches for large files under the specified directory and returns the top N results along with statistics by extension.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "default": ".",
                    "description": _(
                        "param.root.description",
                        default="Root directory for search (only paths under workdir are allowed).",
                    ),
                },
                "top_n": {
                    "type": "integer",
                    "default": 30,
                    "description": _(
                        "param.top_n.description", default="Top N results."
                    ),
                },
                "min_bytes": {
                    "type": "integer",
                    "default": 10_000_000,
                    "description": _(
                        "param.min_bytes.description",
                        default="Only target files larger than this size (default: 10MB).",
                    ),
                },
                "group_by_ext": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.group_by_ext.description",
                        default="Whether to return statistics grouped by extension.",
                    ),
                },
                "exclude_dirs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [".git", "node_modules", "__pycache__", ".venv", "venv"],
                    "description": _(
                        "param.exclude_dirs.description",
                        default="Directory names to exclude (matching base name).",
                    ),
                },
                "max_files": {
                    "type": "integer",
                    "default": 200000,
                    "description": _(
                        "param.max_files.description",
                        default="Maximum number of files to scan (runaway protection).",
                    ),
                },
            },
        },
    },
}


class _ExtStat(TypedDict):
    count: int
    bytes: int


class _ExtOut(TypedDict):
    ext: str
    count: int
    bytes: int


def run_tool(args: Dict[str, Any]) -> str:
    root = str(args.get("root") or ".")
    top_n = int(args.get("top_n") or 30)
    min_bytes = int(args.get("min_bytes") or 10_000_000)
    group_by_ext = bool(args.get("group_by_ext", True))
    exclude_dirs = args.get("exclude_dirs", []) or []
    max_files = int(args.get("max_files") or 200000)

    if is_path_dangerous(root):
        return json.dumps(
            {"ok": False, "error": f"dangerous root rejected: {root}"},
            ensure_ascii=False,
        )

    try:
        safe_root = ensure_within_workdir(root)
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"root not allowed: {e}"}, ensure_ascii=False
        )

    if not os.path.isdir(safe_root):
        return json.dumps(
            {"ok": False, "error": f"root is not a directory: {safe_root}"},
            ensure_ascii=False,
        )

    exclude_set = set(str(x) for x in exclude_dirs)

    big_files: List[Tuple[int, str]] = []
    ext_stats: dict[str, _ExtStat] = defaultdict(lambda: {"count": 0, "bytes": 0})

    scanned_files = 0
    skipped_dirs = 0

    for dirpath, dirnames, filenames in os.walk(safe_root):
        pruned = [d for d in dirnames if d in exclude_set]
        if pruned:
            skipped_dirs += len(pruned)
        dirnames[:] = [d for d in dirnames if d not in exclude_set]

        for fn in filenames:
            scanned_files += 1
            if scanned_files > max_files:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"max_files exceeded: {max_files}",
                        "safe_root": safe_root,
                        "scanned_files": scanned_files,
                        "skipped_dirs": skipped_dirs,
                    },
                    ensure_ascii=False,
                )

            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
            except Exception:
                continue

            size = int(st.st_size)
            if size < min_bytes:
                continue

            big_files.append((size, p))

            if group_by_ext:
                ext = os.path.splitext(fn)[1].lower() or "(noext)"
                ext_stats[ext]["count"] += 1
                ext_stats[ext]["bytes"] += size

    big_files.sort(key=lambda x: x[0], reverse=True)
    top = big_files[: max(0, top_n)]

    out: Dict[str, Any] = {
        "ok": True,
        "safe_root": safe_root,
        "min_bytes": min_bytes,
        "top_n": top_n,
        "scanned_files": scanned_files,
        "skipped_dirs": skipped_dirs,
        "files": [{"path": p, "bytes": s} for s, p in top],
    }

    if group_by_ext:
        exts: list[_ExtOut] = [
            {"ext": k, "count": v["count"], "bytes": v["bytes"]}
            for k, v in ext_stats.items()
        ]
        exts.sort(key=lambda x: x["bytes"], reverse=True)
        out["ext_stats"] = exts

    return json.dumps(out, ensure_ascii=False)
