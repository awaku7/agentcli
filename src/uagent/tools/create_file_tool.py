from __future__ import annotations
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)


import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

BUSY_LABEL = True
STATUS_LABEL = "tool:create_file"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "create_file",
        "description": "テキストファイルを作成します（既定では既存ファイルがある場合は上書きしません）。既存ファイルを overwrite=true で上書きする場合、上書き直前に同名のバックアップ（<filename>.org / <filename>.org1 / <filename>.org2 ...）を作成します。",
        "system_prompt": """このツールは次の目的で使われます: テキストファイルを作成します（既定では既存ファイルがある場合は上書きしません）。既存ファイルを overwrite=true で上書きする場合、上書き直前に同名のバックアップ（<filename>.org / <filename>.org1 / <filename>.org2 ...）を作成します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "作成するファイルのパス。",
                },
                "path": {
                    "type": "string",
                    "description": "(互換) 作成するファイルのパス。filename の別名として受け付けます。",
                },
                "content": {
                    "type": "string",
                    "description": "ファイルに書き込むテキスト内容。",
                },
                "encoding": {
                    "type": "string",
                    "description": "テキストのエンコーディング。例: 'utf-8', 'cp932'。省略時は 'utf-8'。",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": (
                        "ファイルが既に存在する場合に上書きするかどうか。"
                        "省略時は false（上書きしない）。true の場合は既存ファイルを上書きする。"
                        "既存ファイルを上書きする場合は上書き直前にバックアップ（.org/.org1/...）を作成する。"
                    ),
                },
            },
            # content は必須。それ以外は任意。
            "required": ["content"],
        },
    },
}


SafeCreateFile = Callable[[str, str, str, bool], None]

# 安全ラッパーを利用してパスが危険な場合は確認する
safe_create_file: Optional[SafeCreateFile]
try:
    from .safe_file_ops import safe_create_file as safe_create_file
except Exception:
    safe_create_file = None  # フォールバック: import できなくても動作するようにする


def _next_backup_name(filename: str) -> str:
    """Return next available backup name.

    For '/path/to/a.txt' -> '/path/to/a.txt.org' if not exists,
    else '/path/to/a.txt.org1', '/path/to/a.txt.org2', ...
    """

    base = filename + ".org"
    if not os.path.exists(base):
        return base

    i = 1
    while True:
        cand = f"{base}{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def _make_backup_if_needed(filename: str, encoding: str, overwrite: bool) -> str | None:
    """Create a backup for an existing file when overwrite=True.

    Returns backup path if created, otherwise None.
    """

    if not overwrite:
        return None

    if not os.path.exists(filename):
        return None

    backup_path = _next_backup_name(filename)

    # Copy bytes to preserve exact content; don't re-encode.
    Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
    with open(filename, "rb") as rf, open(backup_path, "wb") as wf:
        wf.write(rf.read())

    return backup_path


def run_tool(args: Dict[str, Any]) -> str:
    """LLM からのツール呼び出しを受け、テキストファイルを作成する。

    - filename または path のどちらかでファイルパスを指定（両方あれば filename を優先）
    - encoding 省略時は 'utf-8'
    - overwrite 省略時は False（既存ファイルがあればエラー扱いで書き込まない）

    追加仕様:
    - 既存ファイルを overwrite=true で上書きする場合、上書き直前に
      バックアップ（<filename>.org / <filename>.org1 / ...）を作成する。
    """

    # 互換のため filename または path のいずれかを受け付ける
    raw_filename = args.get("filename") or args.get("path") or ""
    content = str(args.get("content", ""))

    if not raw_filename:
        return "[create_file error] filename/path が指定されていません"

    # エンコーディング（任意）
    encoding = str(args.get("encoding", "utf-8") or "utf-8")

    # 上書き可否（任意）・省略時 False（= 上書き禁止）
    overwrite_raw = args.get("overwrite", None)
    overwrite = False if overwrite_raw is None else bool(overwrite_raw)

    # Expand user and normalize
    filename = os.path.expanduser(str(raw_filename))

    # ★ デバッグ用ログ（stderr に出すので LLM の返答は汚さない）
    preview = content.replace("\n", "\\n")
    if len(preview) > 80:
        preview = preview[:80] + "..."

    try:
        sys.stderr.write(
            f"[create_file] filename={filename!r}, encoding={encoding!r}, "
            f"overwrite={overwrite}, content_len={len(content)}, preview={preview!r}\n"
        )
        sys.stderr.flush()
    except Exception:
        # ログ出力で失敗しても本処理には影響させない
        pass

    # 既存ファイルの扱い（デフォルトは上書き禁止）
    existed_before = os.path.exists(filename)
    if existed_before and not overwrite:
        return (
            f"[create_file] ファイル {filename} は既に存在するため "
            "overwrite=false（既定）では上書きしませんでした"
        )

    backup_path = None
    try:
        backup_path = _make_backup_if_needed(
            filename, encoding=encoding, overwrite=overwrite
        )
    except Exception as e:
        return f"[create_file error] バックアップ作成に失敗しました: {type(e).__name__}: {e}"

    try:
        # 可能なら safe wrapper を使う
        if safe_create_file is not None:
            safe_create_file(filename, content, encoding, overwrite)
        else:
            dirpart = os.path.dirname(filename)
            if dirpart:
                os.makedirs(dirpart, exist_ok=True)

            with open(filename, "w", encoding=encoding) as f:
                f.write(content)

        if existed_before:
            if backup_path:
                return (
                    f"[create_file] ファイル {filename} を上書きしました（{len(content)} 文字）"
                    f" / バックアップ作成: {backup_path}"
                )
            return f"[create_file] ファイル {filename} を上書きしました（{len(content)} 文字）"

        return (
            f"[create_file] ファイル {filename} を作成しました（{len(content)} 文字）"
        )

    except FileExistsError:
        # safe_create_file で既存ファイルかつ overwrite=False の場合に発生する
        return (
            f"[create_file] ファイル {filename} は既に存在するため "
            "overwrite=false（既定）では上書きしませんでした"
        )
    except PermissionError as e:
        return f"[create_file error] PermissionError: {e}"
    except Exception as e:
        return f"[create_file error] {type(e).__name__}: {e}"
