"""Trusted runtime helpers shared by integrated Sub-Agent Job tools."""

from __future__ import annotations

import json
from typing import Any

from ..runtime.sub_agent_job_access import get_job_runtime_context


def get_job_runtime() -> tuple[Any, Any] | None:
    return get_job_runtime_context()


def blocked(reason: str, message: str = "") -> str:
    return json.dumps(
        {
            "status": "blocked",
            "reason": str(reason),
            "message": str(message or reason),
        },
        ensure_ascii=False,
    )


def json_result(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def namespace_shared_context(values: dict[str, str]) -> dict[str, str]:
    """Bound the initial shared-context snapshot before sending it to a worker."""
    total = 0
    bounded: dict[str, str] = {}
    for key, value in values.items():
        content = str(value)
        total += len(key.encode("utf-8", errors="replace"))
        total += len(content.encode("utf-8", errors="replace"))
        if total > 64 * 1024:
            raise ValueError
        bounded[str(key)] = content
    return bounded


__all__ = ["blocked", "get_job_runtime", "json_result", "namespace_shared_context"]
