"""Keep tools required by a scheduled run available during its execution."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator


def _normalise_tool_names(tool_names: object) -> tuple[str, ...]:
    if isinstance(tool_names, str):
        names = (tool_names,)
    elif isinstance(tool_names, (list, tuple, set, frozenset)):
        names = tuple(str(name or "") for name in tool_names)
    else:
        names = ()
    return tuple(dict.fromkeys(name.strip() for name in names if name.strip()))


@contextmanager
def required_tools_guard(
    tool_names: object,
    *,
    reason: str = "scheduled run",
) -> Iterator[tuple[str, ...]]:
    """Load and pin required tools for the lifetime of a scheduled run."""
    names = _normalise_tool_names(tool_names)
    if not names:
        yield ()
        return

    from .. import tools
    from ..tools._genre_control_util import (
        disable_single_tool,
        enable_single_tool,
        is_tool_pinned,
        list_pinned_tools,
        pin_tool,
        unpin_tool,
    )

    previous_pins = list_pinned_tools()
    loaded_here: list[str] = []
    pinned_here: list[str] = []
    try:
        visible_names = set()
        for spec in tools.get_tool_specs() or []:
            if not isinstance(spec, dict):
                continue
            fn = spec.get("function") or {}
            name = fn.get("name") if isinstance(fn, dict) else spec.get("name")
            if name:
                visible_names.add(str(name))

        for name in names:
            if name not in visible_names:
                if not enable_single_tool(name):
                    raise RuntimeError(
                        f"required scheduled tool is unavailable: {name}"
                    )
                loaded_here.append(name)
                visible_names.add(name)
            if not is_tool_pinned(name):
                pin_tool(name, reason=f"{reason}:{name}")
                pinned_here.append(name)
        yield names
    finally:
        for name in reversed(pinned_here):
            unpin_tool(name)
            if name in previous_pins:
                pin_tool(name, previous_pins[name])
        for name in reversed(loaded_here):
            try:
                disable_single_tool(name)
            except Exception:
                pass


def run_scheduled_callback_with_tools(
    callback: Callable[..., Any],
    *args: Any,
    tool_names: object,
    reason: str = "scheduled run",
    sandbox_enabled: bool = False,
    **kwargs: Any,
) -> Any:
    """Run scheduled work without loading Host tools in a Sandbox turn."""
    names = _normalise_tool_names(tool_names)
    if sandbox_enabled:
        from ..runtime.mxc_backend import sandbox_tool_specs

        allowed: set[str] = set()
        for spec in sandbox_tool_specs():
            if not isinstance(spec, dict):
                continue
            function = spec.get("function")
            name = function.get("name") if isinstance(function, dict) else None
            if isinstance(name, str) and name:
                allowed.add(name)
        unavailable = sorted(set(names) - allowed)
        if unavailable:
            raise RuntimeError(
                "Sandbox scheduled run requires unavailable Host tool(s): "
                + ", ".join(unavailable)
            )
        return callback(*args, **kwargs)

    with required_tools_guard(names, reason=reason):
        return callback(*args, **kwargs)


__all__ = ["required_tools_guard", "run_scheduled_callback_with_tools"]
