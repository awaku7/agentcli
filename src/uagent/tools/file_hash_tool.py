# tools/file_hash_tool.py
"""file_hash_tool

ファイルのハッシュ（sha256等）を計算するツール。

安全:
- 読み取りのみ。
- workdir 外のパスや危険なパスは拒否する（safe_file_ops_extras に準拠）。

出力:
- JSON（paths -> hash）
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List

from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:file_hash"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "file_hash",
        "description": "ファイルのハッシュ（sha256/sha1/md5）を計算します。",
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "対象ファイルパス配列",
                },
                "algo": {
                    "type": "string",
                    "enum": ["sha256", "sha1", "md5"],
                    "default": "sha256",
                    "description": "ハッシュアルゴリズム",
                },
                "chunk_size": {
                    "type": "integer",
                    "default": 1048576,
                    "description": "読み取りチャンクサイズ(bytes)",
                },
                "return": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": "出力形式",
                },
            },
            "required": ["paths"],
        },
    },
}


def _hash_file(path: str, algo: str, chunk_size: int) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run_tool(args: Dict[str, Any]) -> str:
    paths = args.get("paths", []) or []
    algo = str(args.get("algo") or "sha256")
    chunk_size = int(args.get("chunk_size") or 1048576)
    fmt = str(args.get("return") or "json")

    if algo not in ("sha256", "sha1", "md5"):
        return json.dumps(
            {"ok": False, "error": f"invalid algo: {algo}"}, ensure_ascii=False
        )

    if fmt not in ("json", "text"):
        return json.dumps(
            {"ok": False, "error": f"invalid return: {fmt}"}, ensure_ascii=False
        )

    if not isinstance(paths, list) or not paths:
        return json.dumps(
            {"ok": False, "error": "paths must be a non-empty array"},
            ensure_ascii=False,
        )

    results: List[Dict[str, Any]] = []
    overall_ok = True

    for p in paths:
        p = str(p)
        if is_path_dangerous(p):
            results.append({"path": p, "ok": False, "error": "dangerous path rejected"})
            overall_ok = False
            continue

        try:
            sp = ensure_within_workdir(p)
        except Exception as e:
            results.append({"path": p, "ok": False, "error": f"path not allowed: {e}"})
            overall_ok = False
            continue

        if not os.path.exists(sp) or not os.path.isfile(sp):
            results.append({"path": sp, "ok": False, "error": "file not found"})
            overall_ok = False
            continue

        try:
            digest = _hash_file(sp, algo=algo, chunk_size=chunk_size)
            results.append(
                {
                    "path": sp,
                    "ok": True,
                    "algo": algo,
                    "hash": digest,
                    "size": os.path.getsize(sp),
                }
            )
        except Exception as e:
            results.append(
                {
                    "path": sp,
                    "ok": False,
                    "error": f"hash failed: {type(e).__name__}: {e}",
                }
            )
            overall_ok = False

    if fmt == "text":
        lines: List[str] = []
        for r in results:
            if r.get("ok"):
                lines.append(f"{r.get('hash')}  {r.get('path')}")
            else:
                lines.append(f"(error) {r.get('path')}: {r.get('error')}")
        return "\n".join(lines)

    return json.dumps({"ok": overall_ok, "results": results}, ensure_ascii=False)
