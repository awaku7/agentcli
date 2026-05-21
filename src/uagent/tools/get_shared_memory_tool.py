# tools/get_shared_memory.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict

from . import shared_memory

TOOL_SPEC: Dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "get_shared_memory",
        "description": _(
            "tool.description",
            default=(
                "Retrieves raw long-term memory (shared memory) data shared across users.\n"
                "- Usually returns text in JSONL format (one record per line).\n"
                "- If shared memory is disabled or the file is missing, returns a descriptive message.\n"
                "- Output size is automatically trimmed to the internal maximum byte limit."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool executes the functionality described in TOOL_SPEC.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "get_shared_memory",
                "get shared memory",
                "shared memory",
                "shared notes",
                "multi user memory",
                "memory store",
            ],
        ),
        "x_search_terms_en": [
            "get_shared_memory",
            "get shared memory",
            "shared memory",
            "shared notes",
            "multi user memory",
            "memory store",
        ],
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


# BUSY_LABEL = True
# STATUS_LABEL = "tool:get_shared_memory"


def run_tool(args: Dict[str, Any]) -> str:
    """Entry point called from tools/__init__.py. Implementation for get_shared_memory."""
    # shared_memory.py handles messages for disabled/missing states
    return shared_memory.load_shared_memory_raw()
