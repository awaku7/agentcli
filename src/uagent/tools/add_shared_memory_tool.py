# tools/add_shared_memory_tool.py
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Any, Dict

from . import shared_memory

# このモジュールで提供するツール定義
TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_shared_memory",
        "description": (
            "複数ユーザーで共有する長期記憶（共有メモリ）に、1件のメモを追記します。\n"
            "- UAGENT_SHARED_MEMORY_FILE などで共有メモリファイルが設定されている場合、"
            "そのファイルに JSONL 形式で書き込みます。\n"
            "- 共有メモリ機能が未設定の場合は、その旨をメッセージで返します。\n"
            "- パスワード・APIキーなどの秘匿情報は絶対に保存しないでください。"
        ),
        "system_prompt": """このツールは TOOL_SPEC に記載された機能を実行します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": (
                        "共有したいメモ本文。プロジェクト共通の方針や、"
                        "複数のユーザー／セッションで再利用したい前提条件などを記述してください。"
                    ),
                }
            },
            "required": ["note"],
            "additionalProperties": False,
        },
    },
}


# このツールは IO は軽いので Busy ラベルは特につけない（デフォルト False）
# BUSY_LABEL = True
# STATUS_LABEL = "tool:add_shared_memory"


def run_tool(args: Dict[str, Any]) -> str:
    """tools/__init__.py から呼ばれるエントリポイント。add_shared_memory 用の実装。"""
    note = str(args.get("note", "")).strip()
    if not note:
        return "[add_shared_memory] note が空文字だったため、共有記憶には何も保存しませんでした。"

    if not shared_memory.is_enabled():
        return (
            "[add_shared_memory] 共有長期記憶は無効です（UAGENT_SHARED_MEMORY_FILE 未設定）。\n"
            "共有メモを使う場合は、環境変数 UAGENT_SHARED_MEMORY_FILE を設定してください。"
        )

    try:
        shared_memory.append_shared_memory(note)
    except Exception as e:
        return (
            "[add_shared_memory] 共有長期記憶への書き込みでエラーが発生しました。\n"
            f"type={type(e).__name__}, error={e}"
        )

    return f"[add_shared_memory] 共有長期記憶にメモを1件追記しました。\nnote={note}"
