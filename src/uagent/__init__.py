"""scheck package.

Version is resolved from installed distribution metadata (pyproject.toml) when available.

This avoids keeping version in multiple places.
"""

from __future__ import annotations


def __getattr__(name: str):
    # PEP 562: module attribute access hook
    if name != "__version__":
        raise AttributeError(name)

    try:
        # Prefer installed distribution metadata
        from importlib.metadata import PackageNotFoundError, version

        return version("uag")
    except Exception:
        # Fallback for source-tree execution without installation
        return "unknown"


__all__ = ["__version__"]

