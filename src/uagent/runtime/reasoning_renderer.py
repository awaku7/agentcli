"""Host-facing reasoning rendering callbacks for legacy round parsers."""

from __future__ import annotations

from typing import Any


def render_tool_call_reasoning(
    reasoning_content: str, *, provider: str, core: Any
) -> None:
    """Render reasoning attached to a tool-call turn through the host UI."""
    from ..reasoning_display import show_reasoning

    show_reasoning(
        reasoning_content,
        provider=provider,
        is_first=True,
        print_fn=getattr(core, "print_stream_delta", None)
        or (lambda text: print(text, end="", flush=True)),
        core=core,
    )


__all__ = ["render_tool_call_reasoning"]
