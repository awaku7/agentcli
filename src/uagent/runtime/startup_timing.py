"""Lightweight CLI startup timeline; does not import provider or tool modules."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
import sys
import time

_CLOCK = time.perf_counter
_STARTED = _CLOCK()
_PREVIOUS = _STARTED


def checkpoint(name: str) -> None:
    """Report cumulative and inter-stage durations when startup timing is enabled."""
    global _PREVIOUS

    now = _CLOCK()
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
            f"[startup-timing] timeline.{name}={elapsed:.3f}s delta={delta:.3f}s",
            file=sys.stderr,
            flush=True,
        )



@contextmanager
def measure_detail(name: str) -> Iterator[None]:
    """Log one opt-in timing detail, including when the wrapped call raises."""
    if (os.environ.get("UAGENT_STARTUP_TIMING") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        yield
        return

    started = _CLOCK()
    try:
        yield
    finally:
        elapsed = _CLOCK() - started
        print(
            f"[startup-timing] detail.{name}={elapsed:.3f}s",
            file=sys.stderr,
            flush=True,
        )
