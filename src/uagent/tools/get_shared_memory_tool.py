# tools/get_shared_memory.py
from typing import Any, Dict

from . import shared_memory

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_shared_memory",
        "description": (
            "複数ユーザーで共有する長期記憶（共有メモリ）の生データを取得します。\n"
            "- 通常は JSONL 形式（1行1レコード）のテキストを返します。\n"
            "- 共有メモリが無効な場合やファイルが存在しない場合は、その旨を示す文字列を返します。\n"
            "- 出力サイズは内部で上限バイト数までに自動トリミングされます。"
        ),
        "system_prompt": """このツールは TOOL_SPEC に記載された機能を実行します。""",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


# こちらも IO は軽いので Busy ラベルは付与しない
# BUSY_LABEL = True
# STATUS_LABEL = "tool:get_shared_memory"


def run_tool(args: Dict[str, Any]) -> str:
    """tools/__init__.py から呼ばれるエントリポイント。get_shared_memory 用の実装。"""
    # shared_memory 側で無効/未作成などのメッセージも含めて返す
    return shared_memory.load_shared_memory_raw()
