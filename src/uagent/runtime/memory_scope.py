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

    ``UAGENT_MEMORY_PROJECT`` is the explicit override. Authenticated
    non-local Web turns use their server-validated project; other entry points
    retain the existing ``UAGENT_WORKDIR`` / CWD fallback.
    """
    configured = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
    if configured:
        return configured
    from .identity_context import get_current_turn_context

    turn = get_current_turn_context()
    if (
        turn is not None
        and turn.entry_point == "web"
        and turn.authenticated
        and turn.authn_kind != "local"
        and turn.server_bound_project
        and turn.project_id
    ):
        return turn.project_id
    workdir = str(env_get("UAGENT_WORKDIR", "") or "").strip() or os.getcwd()
    return project_id_from_path(workdir)


def resolve_server_workspace_project() -> str:
    """Resolve a Web default from configured or captured startup workdir.

    Do not use request-time ``os.getcwd()`` here: Web room workers can change
    the process-global CWD while another request is resolving its default.
    """
    from .runtime_workdir import get_captured_startup_workdir

    workdir = get_captured_startup_workdir()
    return project_id_from_path(workdir) if workdir else ""


__all__ = [
    "resolve_memory_owner",
    "resolve_memory_project",
    "resolve_server_workspace_project",
]
