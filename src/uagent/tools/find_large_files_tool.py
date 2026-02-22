# tools/find_large_files_tool.py
"""find_large_files_tool

ディレクトリ配下の大きいファイルを探すツール。

目的:
- workdir の肥大化原因の特定
- 生成物やログの整理

安全:
- 読み取り（stat）のみ。
- workdir 外の root や危険パスは拒否（safe_file_ops_extras に準拠）。

注意:
- 走査は重くなる可能性があるので、top_n / min_bytes / exclude_dirs で制御する。
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
        "description": "指定ディレクトリ配下の大きいファイルを検索し、上位N件や拡張子別集計を返します。",
        "parameters": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "default": ".",
                    "description": "探索ルート（workdir配下のみ許可）",
                },
                "top_n": {
                    "type": "integer",
                    "default": 30,
                    "description": "上位N件",
                },
                "min_bytes": {
                    "type": "integer",
                    "default": 10_000_000,
                    "description": "このサイズ以上のみ対象（既定: 10MB）",
                },
                "group_by_ext": {
                    "type": "boolean",
                    "default": True,
                    "description": "拡張子別集計も返す",
                },
                "exclude_dirs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [".git", "node_modules", "__pycache__", ".venv", "venv"],
                    "description": "除外ディレクトリ名（ディレクトリ名一致）",
                },
                "max_files": {
                    "type": "integer",
                    "default": 200000,
                    "description": "走査する最大ファイル数（暴走防止）",
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
