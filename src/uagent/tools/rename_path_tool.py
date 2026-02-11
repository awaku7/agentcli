# -*- coding: utf-8 -*-
"""tools/rename_path_tool.py

rename_path ツール

目的:
- ファイル/ディレクトリの rename / move を行う。

安全方針:
- workdir 外・絶対パス・.. を含む等の危険パス条件に該当する場合はユーザー確認。
- overwrite=True（既存 dst を削除して置換）の場合はユーザー確認。

実装:
- 実体の操作は tools.safe_file_ops.safe_rename_path() に委譲する。
- 既存 dst を削除する場合、ファイルは os.remove、ディレクトリは shutil.rmtree。

注意:
- このツールは create_file/delete_file と同様に「実ファイル変更」を行うため、
  LLM から呼ばれる場合でも安全確認が入る設計。
"""

from __future__ import annotations

from typing import Any, Dict

from .safe_file_ops import safe_rename_path

BUSY_LABEL = True
STATUS_LABEL = "tool:rename_path"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "rename_path",
        "description": "ファイルまたはディレクトリの名前変更（移動）を行います。",
        "system_prompt": """このツールはファイル/ディレクトリの rename/move を行います。

安全注記:
- 絶対パス、.. を含むパス、workdir 外への操作等は確認が入ります。
- overwrite=true（既存 dst を削除して置換）は削除を伴うため確認が入ります。
""",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {
                    "type": "string",
                    "description": "元のパス（ファイル/ディレクトリ）。相対パス推奨。",
                },
                "dst": {
                    "type": "string",
                    "description": "移動先パス（ファイル/ディレクトリ）。相対パス推奨。",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "true の場合、dst が既に存在していれば削除して置換します（確認が入ります）。",
                    "default": False,
                },
                "mkdirs": {
                    "type": "boolean",
                    "description": "true の場合、dst の親ディレクトリを作成してから実行します。",
                    "default": False,
                },
            },
            "required": ["src", "dst"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    src = str(args.get("src") or "").strip()
    dst = str(args.get("dst") or "").strip()

    overwrite = bool(args.get("overwrite", False))
    mkdirs = bool(args.get("mkdirs", False))

    try:
        safe_rename_path(src=src, dst=dst, overwrite=overwrite, mkdirs=mkdirs)
    except Exception as e:
        return f"[rename_path error] {type(e).__name__}: {e}"

    return f"[OK] renamed: {src} -> {dst}"
