"""Shared resolution of memory ownership and project boundaries."""

from __future__ import annotations

import getpass
import os
from typing import Any

from ..env_utils import env_get
from .session_store import project_id_from_path


def _os_login_owner() -> str:
    """Return a stable local owner label for the current OS login.

    V2 is primarily a single-user/local runtime. An explicit Memory owner still
    wins, but when none is configured we use the OS login instead of leaving the
    owner boundary empty. On Windows, USERDOMAIN is included when available so
    domain/local accounts with the same username remain distinguishable.
    """
    try:
        username = str(getpass.getuser() or "").strip()
    except Exception:
        username = ""
    if not username:
        username = str(
            os.environ.get("USERNAME")
            or os.environ.get("USER")
            or os.environ.get("LOGNAME")
            or ""
        ).strip()
    if not username:
        return "local-default"

    if os.name == "nt" and "\\" not in username:
        domain = str(os.environ.get("USERDOMAIN") or "").strip()
        if domain:
            return f"{domain}\\{username}"
    return username


def resolve_memory_owner(owner: Any = "") -> str:
    """Resolve owner from explicit value, configured override, then OS login."""
    explicit = str(owner or env_get("UAGENT_MEMORY_OWNER", "") or "").strip()
    return explicit or _os_login_owner()


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
