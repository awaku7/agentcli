"""Lightweight CLI startup timeline; does not import provider or tool modules."""

from __future__ import annotations

import os
import sys
import time

_STARTED = time.perf_counter()
_PREVIOUS = _STARTED


def checkpoint(name: str) -> None:
    """Report cumulative and inter-stage durations when startup timing is enabled."""
    global _PREVIOUS

    now = time.perf_counter()
    elapsed = now - _STARTED
    delta = now - _PREVIOUS
    _PREVIOUS = now

    if (os.environ.get("UAGENT_STARTUP_TIMING") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        print(
            f"[startup-timing] timeline.{name}={elapsed:.3f}s "
            f"delta={delta:.3f}s",
            file=sys.stderr,
            flush=True,
        )
