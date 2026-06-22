from __future__ import annotations

import json
from typing import Any

from ._matter_cache import matter_cache_stats
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:matter_cache_status"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_cache_status",
        "description": _(
            "tool.description",
            default="Show Matter cache statistics: hit ratio, entry count, TTL.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


def _format_text(stats: dict[str, Any]) -> str:
    return (
        f"Matter cache statistics:\n"
        f"  Cached entries: {stats['cached_entries']}\n"
        f"  Expired entries: {stats['expired_entries']}\n"
        f"  Total slots: {stats['total_slots']}\n"
        f"  Hits: {stats['hits']}\n"
        f"  Misses: {stats['misses']}\n"
        f"  Puts: {stats['puts']}\n"
        f"  Hit ratio: {stats['hit_ratio']}\n"
        f"  TTL: {stats['ttl_seconds']}s"
    )


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    stats = matter_cache_stats()
    result = {"ok": True, **stats}
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
