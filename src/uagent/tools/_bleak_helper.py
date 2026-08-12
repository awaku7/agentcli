"""Lazy installation helper for BLE tools."""

from __future__ import annotations

from .._pip_auto import install_with_status


def ensure_bleak() -> bool:
    """Install bleak on first BLE-tool use and verify that it imports."""
    if not install_with_status("bleak", "bleak", display_name="bleak"):
        return False
    try:
        import bleak  # noqa: F401
    except ImportError:
        return False
    return True
