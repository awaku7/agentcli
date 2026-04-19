# tools/finish_skill_tool.py
"""finish_skill_tool implementation to explicitly end a skill session."""

from __future__ import annotations

import json
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:finish_skill"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "finish_skill",
        "description": _(
            "tool.description",
            default="Signal that the current skill's tasks are complete. (Use ONLY during skill execution based on SKILL.md). This removes skill instructions and prevents infinite loops.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Optional final message to the user.",
                    ),
                }
            },
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    message = (args or {}).get("message") or "Skill execution finished."

    # 履歴への参照がある場合（uagent 実行環境）、直接解除を試みる
    import sys
    # 呼び出し元のフレームから messages または messages_ref を探す
    f = sys._getframe()
    while f:
        m = f.f_locals.get("messages") or f.f_locals.get("messages_ref")
        if isinstance(m, list):
            try:
                from ..util_tools import _clear_skill_messages
                removed = _clear_skill_messages(m)
                if removed > 0:
                    # 可能であれば core 経由で永続化
                    core = f.f_locals.get("core")
                    if core:
                        from ..util_tools import _persist_messages_with_warn
                        _persist_messages_with_warn(m, core=core, label="finish_skill")
                    return json.dumps({
                        "status": "ok", 
                        "message": f"{message} (Cleared {removed} skill messages)"
                    }, ensure_ascii=False)
            except Exception:
                pass
        f = f.f_back

    return json.dumps({"status": "ok", "message": message}, ensure_ascii=False)
