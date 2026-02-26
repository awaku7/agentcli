# tools/get_long_memory_tool.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict

from . import long_memory

BUSY_LABEL = False

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_long_memory",
        "description": _(
            "tool.description", default="Get all saved long-term memory notes (JSONL)."
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool is used for the following purpose: retrieve all saved long-term memory notes (in JSONL format).",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """Retrieve the entire long-term memory as JSONL text."""
    return long_memory.load_long_memory_raw()
