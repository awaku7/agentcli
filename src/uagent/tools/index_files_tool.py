from __future__ import annotations

import os
import glob
from typing import Any, Dict

# セマンティック検索DB更新用のインポート
# NOTE:
# - semantic_search_files_tool は Embedding API 疎通失敗時に TOOL_SPEC=None になり、
#   toolsローダから登録されない。
# - その場合、この index_files もロードしない（ユーザー要件: embed不可ならツールを出さない）。
try:
    from . import semantic_search_files_tool as vec_tool

    sync_file = getattr(vec_tool, "sync_file", None)
    _VEC_TOOL_ENABLED = isinstance(getattr(vec_tool, "TOOL_SPEC", None), dict)
except Exception:
    sync_file = None
    _VEC_TOOL_ENABLED = False

BUSY_LABEL = True
STATUS_LABEL = "tool:index_files"


# If vector/embedding tool is disabled, do not expose this tool either.
# tools/__init__.py registers a tool only when TOOL_SPEC is a dict.
if not _VEC_TOOL_ENABLED:
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC: Dict[str, Any] = {
        "type": "function",
        "function": {
            "name": "index_files",
            "description": "指定されたファイルやディレクトリ（globパターン）をベクトルDBにインデックスし、意味検索（semantic_search_files）を可能にします。ファイルの中身を読み取らずに検索準備だけを行いたい場合に便利です。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "対象とするファイル名、ディレクトリ名、またはglobパターン（例: 'src/**/*.py', '*.md'）。",
                    },
                    "root_path": {
                        "type": "string",
                        "description": "検索・インデックスの起点となるディレクトリ。デフォルトはカレントディレクトリ。",
                        "default": ".",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "パターンに '**' を含む場合に再帰的に探索するかどうか。",
                        "default": True,
                    },
                },
                "required": ["pattern"],
            },
        },
    }


def run_tool(args: Dict[str, Any]) -> str:
    if sync_file is None:
        return "エラー: セマンティック検索モジュール (semantic_search_files_tool) が利用できないため、インデックスを作成できません。"

    pattern = str(args.get("pattern", ""))
    root_path = str(args.get("root_path", "."))
    recursive = bool(args.get("recursive", True))

    if not pattern:
        return "エラー: pattern が指定されていません。"

    root_abs = os.path.abspath(root_path)
    if not os.path.isdir(root_abs):
        return f"エラー: root_path がディレクトリではありません: {root_path}"

    search_pattern = os.path.join(root_abs, pattern)

    try:
        files = glob.glob(search_pattern, recursive=recursive)
    except Exception as e:
        return f"エラー: パターンの解析に失敗しました: {e}"

    from uagent.utils.scan_filters import is_ignored_path

    target_files = [f for f in files if os.path.isfile(f) and (not is_ignored_path(f))]

    if not target_files:
        return f"パターン '{pattern}' に一致するファイルが見つかりませんでした。"

    # インデックス処理を開始
    # 大量のファイルがある可能性があるため、一つずつ sync_file を呼ぶ
    # 本来は semantic_search_files 内部のように一括処理したほうが早いが、
    # 既存の sync_file を再利用して確実に動作させる。

    success_count = 0
    error_count = 0

    # ユーザーへのレスポンスが遅くなりすぎないよう、このツールは「開始したこと」を返すが、
    # sync_file 自体はフォアグラウンドで回す（LLMに完了を伝えるため）
    for fpath in target_files:
        try:
            sync_file(fpath, root_abs)
            success_count += 1
        except Exception:
            error_count += 1

    result = [
        "インデックス処理が完了しました。",
        f"対象パターン: {pattern}",
        f"ルートディレクトリ: {root_abs}",
        f"成功: {success_count} 件",
    ]
    if error_count > 0:
        result.append(f"失敗: {error_count} 件")

    result.append(
        "\nこれで `semantic_search_files` を使用してこれらのファイルを検索できるようになりました。"
    )

    return "\n".join(result)
