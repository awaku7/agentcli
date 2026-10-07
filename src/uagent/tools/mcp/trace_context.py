"""Trusted MCP message-level W3C Trace Context propagation helpers."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Awaitable, Callable

_TRACE_KEYS = ("traceparent", "tracestate")
_RESERVED_TRACE_META_KEYS = frozenset({"traceparent", "tracestate", "baggage"})


def build_trusted_mcp_trace_meta(enabled: bool) -> dict[str, str]:
    """Return UAG-owned W3C Trace Context for a trusted MCP message carrier."""

    if not enabled:
        return {}
    try:
        from ...runtime.observability.bootstrap import get_observability_backend

        carrier: dict[str, str] = {}
        get_observability_backend().inject_context(carrier)
    except Exception:
        return {}

    result: dict[str, str] = {}
    for key in _TRACE_KEYS:
        value = carrier.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def inject_trusted_mcp_trace_meta(
    params: Mapping[str, Any] | None,
    *,
    enabled: bool
) -> dict[str, Any] | None:
    """Copy params and inject trusted trace context into params._meta.

    Baggage is deliberately excluded by UAG policy. Existing trace-context keys
    are removed before UAG-owned context is injected, while unrelated MCP
    metadata is preserved.
    """

    if not enabled:
        return dict(params) if params is not None else None

    copied: dict[str, Any] = dict(params or {})
    raw_meta = copied.get("_meta")
    meta = dict(raw_meta) if isinstance(raw_meta, Mapping) else {}
    for key in _RESERVED_TRACE_META_KEYS:
        meta.pop(key, None)
    meta.update(build_trusted_mcp_trace_meta(True))
    if meta:
        copied["_meta"] = meta
    else:
        copied.pop("_meta", None)
    return copied or None


def _accepts_meta_keyword(callback: Callable[..., Any]) -> bool:
    try:
        parameters = inspect.signature(callback).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "meta"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


async def call_with_trusted_mcp_trace_meta(
    callback: Callable[..., Awaitable[Any]],
    *args: Any,
    enabled: bool,
    **kwargs: Any
) -> Any:
    """Call an MCP SDK method with message-level trace metadata when supported."""

    trace_meta = build_trusted_mcp_trace_meta(enabled)
    if not trace_meta or not _accepts_meta_keyword(callback):
        return await callback(*args, **kwargs)

    raw_meta = kwargs.get("meta")
    meta = dict(raw_meta) if isinstance(raw_meta, Mapping) else {}
    for key in _RESERVED_TRACE_META_KEYS:
        meta.pop(key, None)
    meta.update(trace_meta)
    kwargs["meta"] = meta
    return await callback(*args, **kwargs)


__all__ = [
    "build_trusted_mcp_trace_meta",
    "call_with_trusted_mcp_trace_meta",
    "inject_trusted_mcp_trace_meta",
]
