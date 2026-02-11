# tools/add_long_memory_tool.py
from typing import Any, Dict

from . import long_memory

BUSY_LABEL = False


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_long_memory",
        "description": "ユーザーや環境について、今後の対話でも役立ちそうな長期記憶メモを1件保存します。",
        "system_prompt": """このツールは次の目的で使われます: ユーザーや環境について、今後の対話でも役立ちそうな長期記憶メモを1件保存します。
- パスワードや API キー等の秘匿情報を長期記憶や共有メモに保存しないでください。
""",
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": (
                        "有用で、今後の会話でも再利用したい情報を "
                        "日本語で簡潔に1件だけ記述する"
                    ),
                }
            },
            "required": ["note"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """長期的に使いたい情報を1件保存するツール。"""
    note = (args.get("note") or "").strip()
    if not note:
        return "[add_long_memory error] note が空です"

    long_memory.append_long_memory(note)
    return "[add_long_memory] メモを保存しました"
