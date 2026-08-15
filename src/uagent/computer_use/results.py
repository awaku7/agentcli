"""Computer Runtime result and screenshot models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Screenshot:
    """A screenshot returned by a Computer Runtime."""

    data: bytes
    media_type: str = "image/png"
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class ComputerActionResult:
    """Result returned after a ComputerAction is evaluated."""

    action_id: str
    success: bool
    error: str | None = None
    screenshot: Screenshot | None = None
