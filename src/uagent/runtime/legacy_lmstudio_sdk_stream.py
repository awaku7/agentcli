"""Host-owned consumption of LM Studio native SDK Chat stream chunks.

Native SDK streams emit OpenAI-shaped deltas and a final usage-only chunk.
Keep this legacy adapter separate from Inception's diffusion stream renderer.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable

from ..llm_helpers import LLMWaitInterrupted, llm_call_abandoned
from ..providers.openai_compatible_runtime import _reported_usage
from .stream_host import build_stream_callbacks


def _stream_interrupted(core: Any) -> bool:
    """Check host Stop and the durable signal of an abandoned call thread."""
    if llm_call_abandoned():
        return True
    from .. import core as core_module

    with core_module.interrupt_lock:
        if core_module.interrupt_requested:
            return True
    if bool(getattr(core, "interrupt_requested", False)):
        return True
    cancellation = getattr(core, "cancellation_token", None)
    return cancellation is not None and cancellation.is_cancelled()


def collect_lmstudio_sdk_stream(stream: Iterable[Any], *, core: Any) -> Any:
    """Return a complete Chat response after rendering native SDK deltas.

    Do not expose usage until the stream is fully consumed. An exception or
    cancellation prevents partial usage from reaching the shared OTel span.
    """
    web = bool(getattr(core, "_is_web", False))
    callbacks = build_stream_callbacks(
        print_delta_fn=None if web else getattr(core, "print_stream_delta", None),
        core=core,
    )
    parts: list[str] = []
    last_usage: Any = None
    try:
        for chunk in stream:
            if _stream_interrupted(core):
                raise LLMWaitInterrupted("LM Studio SDK stream interrupted")
            raw_usage = getattr(chunk, "usage", None)
            if _reported_usage(raw_usage, responses=False):
                last_usage = raw_usage
            for choice in getattr(chunk, "choices", None) or ():
                delta = getattr(choice, "delta", None)
                content = getattr(delta, "content", None)
                if isinstance(content, str) and content:
                    if _stream_interrupted(core):
                        raise LLMWaitInterrupted("LM Studio SDK stream interrupted")
                    parts.append(content)
                    if callable(callbacks.on_delta):
                        callbacks.on_delta(content)
        if _stream_interrupted(core):
            raise LLMWaitInterrupted("LM Studio SDK stream interrupted")
    finally:
        # A completed older worker must never terminate a newer Web stream.
        if not _stream_interrupted(core):
            if web:
                log_message = getattr(core, "log_message", None)
                if callable(log_message):
                    log_message({"type": "assistant_stream_end"})
            elif parts and callable(callbacks.on_delta):
                callbacks.on_delta(chr(10))

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="".join(parts), tool_calls=[]),
                finish_reason="stop",
            )
        ],
        usage=last_usage,
    )


__all__ = ["collect_lmstudio_sdk_stream"]
