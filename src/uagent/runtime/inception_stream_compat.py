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


__all__ = ["collect_inception_stream_events"]
