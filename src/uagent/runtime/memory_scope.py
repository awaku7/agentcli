"""Shared resolution of memory ownership and project boundaries."""

from __future__ import annotations

import os
from typing import Any

from ..env_utils import env_get
from .session_store import project_id_from_path


def resolve_memory_owner(owner: Any = "") -> str:
    """Return an explicit owner, falling back to the configured environment."""
    return str(owner or env_get("UAGENT_MEMORY_OWNER", "") or "").strip()


def resolve_memory_project() -> str:
    """Resolve the project using the same basis for save and projection paths.

    ``UAGENT_MEMORY_PROJECT`` is the canonical explicit override. Otherwise both
    persistence and projection use ``UAGENT_WORKDIR`` when configured, then the
    process current directory. They deliberately do not use separate core-only
    or tool-only path sources.
    """
    configured = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
    if configured:
        return configured
    workdir = str(env_get("UAGENT_WORKDIR", "") or "").strip() or os.getcwd()
    return project_id_from_path(workdir)


__all__ = ["resolve_memory_owner", "resolve_memory_project"]
