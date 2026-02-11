from typing import Any, Dict
from . import reload_plugins

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "system_reload",
        "description": "システムをリロードし、tools/ 以下のすべてのツールの最新コード（.pyファイル）をメモリ上に反映させます。コード修正後に実行してください。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    try:
        reload_plugins()
        return "System reload successful. All plugins have been reloaded with the latest code."
    except Exception as e:
        return f"Error during system reload: {str(e)}"
