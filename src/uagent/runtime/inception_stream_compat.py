"""Legacy compatibility import for Inception stream rendering.

The renderer is host-owned in :mod:`uagent.runtime.inception_stream_host`.
This module preserves the historical collector import for callers that still
use the compatibility API.
"""

from __future__ import annotations

from .inception_stream_host import render_inception_stream_events

# Preserve the old name while keeping the implementation outside the provider
# adapter and making the host boundary explicit for new call sites.
collect_inception_stream_events = render_inception_stream_events


def render_legacy_inception_stream(
    stream: object,
    *,
    diffusing: bool,
    print_delta_fn: object,
    core: object,
) -> tuple[str, str, list[dict[str, object]]]:
    """Render the historical Inception stream through the host boundary."""
    # Imports remain lazy because the provider adapter imports this compatibility
    # module for its event collector.
    import uuid

    from ..providers.llm_inception import inception_stream_events
    from ..providers.responses_runtime import _responses_session_generation
    from .inception_stream_host import (
        build_inception_stream_callbacks,
        render_inception_stream_events,
    )
    from .round_contracts import RoundIdentifiers

    stream_id = "inception-" + uuid.uuid4().hex
    identifiers = RoundIdentifiers(
        turn_id="compat-" + stream_id,
        round_id="compat-" + stream_id,
        attempt_id="compat-" + stream_id,
        request_id="compat-" + stream_id,
        stream_id=stream_id,
        session_generation=_responses_session_generation(core),
    )
    events = inception_stream_events(
        stream,
        identifiers=identifiers,
        diffusing=diffusing,
        cancellation=getattr(core, "cancellation_token", None),
    )
    return render_inception_stream_events(
        events,
        diffusing=diffusing,
        print_delta_fn=print_delta_fn,
        core=core,
        callbacks=build_inception_stream_callbacks(
            print_delta_fn=print_delta_fn,
            core=core,
        ),
    )


__all__ = ["collect_inception_stream_events", "render_legacy_inception_stream"]
