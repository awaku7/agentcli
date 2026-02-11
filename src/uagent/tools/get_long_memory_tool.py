# tools/get_long_memory_tool.py
from typing import Any, Dict

from . import long_memory

BUSY_LABEL = False

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_long_memory",
        "description": "保存されている長期記憶メモ（JSONL形式）をまとめて取得します。",
        "system_prompt": """このツールは次の目的で使われます: 保存されている長期記憶メモ（JSONL形式）をまとめて取得します。""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """長期記憶の全体（JSONLテキスト）を取得するツール。"""
    return long_memory.load_long_memory_raw()
