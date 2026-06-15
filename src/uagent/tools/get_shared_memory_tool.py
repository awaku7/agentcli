from __future__ import annotations

# tools/get_shared_memory.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any

from . import shared_memory

TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "get_shared_memory",
        "description": _(
            "tool.description",
            default="Retrieves raw long-term memory (shared memory) data shared across users. - Usually returns text in JSONL format (one record per line).",
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


def run_tool(args: dict[str, Any]) -> str:
    """Entry point called from tools/__init__.py. Implementation for get_shared_memory."""
    # shared_memory.py handles messages for disabled/missing states
    return shared_memory.load_shared_memory_raw()
