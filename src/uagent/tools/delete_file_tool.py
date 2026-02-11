from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

BUSY_LABEL = True
STATUS_LABEL = "tool:delete_file"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": "指定されたパスのファイルまたはディレクトリを削除します（ディレクトリは再帰削除）。危険操作のため確認が入る場合があります。",
        "system_prompt": """このツールは次の目的で使われます: 削除するファイルのパス。""",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "削除するファイルのパス。",
                },
                "path": {
                    "type": "string",
                    "description": "(互換) 削除するファイルのパス。filename の別名として受け付けます。",
                },
                "missing_ok": {
                    "type": "boolean",
                    "description": (
                        "ファイルが存在しない場合の扱い。"
                        "省略時は false（エラーにする）。true の場合はエラーにせず成功扱いとする。"
                    ),
                },
            },
            # filename/path のどちらかは必須だが、互換のためここでは必須指定しない。
            "required": [],
        },
    },
}


SafeDeleteFile = Callable[[str, bool], None]

# 旧互換のため safe_delete_file を import しているが、
# 本ツールはファイル/ディレクトリ両対応の safe_delete_path を使用する。
try:
    from .safe_file_ops import safe_delete_path
except Exception:
    safe_delete_path = None  # type: ignore


def run_tool(args: Dict[str, Any]) -> str:
    """指定されたパスのファイル/ディレクトリを 1 つ削除する。

    - filename / path のどちらかで指定
    - missing_ok が True なら、存在しなくても成功扱い
    - ディレクトリの場合は再帰削除(shutil.rmtree)
    - ディレクトリ削除は危険操作のため、常に確認が入る（safe_delete_path 経由）
    """

    raw_filename = args.get("filename") or args.get("path") or ""
    if not raw_filename:
        return "[delete_file error] filename/path が指定されていません"

    missing_ok = bool(args.get("missing_ok", False))

    # パスを正規化
    filename = os.path.expanduser(str(raw_filename))

    # ★ デバッグ用ログ（stderr なので LLM の返答は汚れない）
    try:
        sys.stderr.write(
            f"[delete_file] filename={filename!r}, missing_ok={missing_ok}\n"
        )
        sys.stderr.flush()
    except Exception:
        pass

    try:
        # 存在チェック（missing_ok は safe_delete_path 側でも扱うが、
        # ツールのメッセージ互換のためここで分岐する）
        if not os.path.exists(filename):
            if missing_ok:
                return (
                    f"[delete_file] パス {filename} は存在しませんでしたが、"
                    "missing_ok=true のため何もせず成功とみなします。"
                )
            return f"[delete_file error] パス {filename} は存在しません。"

        # 削除前に種別判定（削除後は判定できないため）
        is_dir = os.path.isdir(filename)

        if safe_delete_path is None:
            return "[delete_file error] safe_delete_path が利用できません"

        safe_delete_path(filename, missing_ok=missing_ok)

        if is_dir:
            return f"[delete_file] ディレクトリ {filename} を削除しました。"
        return f"[delete_file] ファイル {filename} を削除しました。"

    except PermissionError as e:
        return f"[delete_file error] PermissionError: {e}"
    except Exception as e:
        return f"[delete_file error] {type(e).__name__}: {e}"
