"""Host-facing reasoning rendering callbacks for legacy round parsers."""

from __future__ import annotations

from typing import Any, Callable


def render_reasoning(
    reasoning_content: str,
    *,
    provider: str,
    core: Any,
    is_first: bool = True,
    print_fn: Callable[[str], None] | None = None,
) -> None:
    """Render reasoning through the shared host display boundary."""
    from ..reasoning_display import show_reasoning

    show_reasoning(
        reasoning_content,
        provider=provider,
        is_first=is_first,
        print_fn=print_fn
        or getattr(core, "print_stream_delta", None)
        or (lambda text: print(text, end="", flush=True)),
        core=core,
    )


def render_tool_call_reasoning(
    reasoning_content: str, *, provider: str, core: Any
) -> None:
    """Render reasoning attached to a tool-call turn through the host UI."""
    render_reasoning(reasoning_content, provider=provider, core=core)


__all__ = ["render_reasoning", "render_tool_call_reasoning"]
