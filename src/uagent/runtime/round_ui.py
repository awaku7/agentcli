"""Host UI side effects used by legacy round compatibility code."""

from __future__ import annotations


def stop_round_spinner() -> None:
    """Stop the active host spinner before emitting a terminal message."""
    from .spinner import stop_quietly

    stop_quietly()


__all__ = ["stop_round_spinner"]
