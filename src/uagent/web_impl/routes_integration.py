"""Versioned, read-only integration API for external UAG management services."""

from __future__ import annotations

import asyncio
import base64
from contextlib import closing
from datetime import datetime, timezone
import hmac
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from importlib.metadata import PackageNotFoundError, version
import json
from typing import Any

from fastapi import Request

from fastapi.responses import JSONResponse

from ..env_utils import env_get
from ..runtime.project_access import ProjectAccessPolicy
from ..tools import long_memory as _long_memory_mod
from ..utils.paths import get_state_dir

from ..runtime.instance_identity import get_instance_id, get_instance_name
from .app import app

INTEGRATION_API_VERSION = "1"
SUPPORTED_ENTRYPOINTS = ("cli", "web", "gui", "a2a")


def _uag_version() -> str:
    try:
        return version("uag")
    except PackageNotFoundError:
        return "unknown"


@app.get("/api/admin/integration/v1/manifest", include_in_schema=False)
async def get_integration_manifest():
    """Describe this UAG installation to an authorized management client.

    The application middleware protects this path with the configured global
    administrator policy. The instance ID is an identifier, not a credential.
    """
    try:
        instance_id = get_instance_id()
        instance_name = get_instance_name(instance_id)
    except (OSError, RuntimeError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"error": "UAG integration identity is unavailable"},
        )

    capabilities = ["instance.identity.read"]
    try:
        configured = _read_config()
    except ValueError:
        configured = None
    if configured is not None and str(
        env_get("UAGENT_SESSION_STORE", "1")
    ).lower() not in {
        "0",
        "false",
        "no",
        "off",
    }:
        capabilities.append("session.metadata.read")

    if configured is not None:
        capabilities.append("project.membership.read")

    return {
        "api_version": INTEGRATION_API_VERSION,
        "instance": {
            "id": instance_id,
            "name": instance_name,
        },
        "software": {
            "name": "uag",
            "version": _uag_version(),
        },
        "supported_entrypoints": list(SUPPORTED_ENTRYPOINTS),
        "capabilities": capabilities,
    }


def _read_config() -> tuple[str, str, str] | None:
    """Separate read-only service secret, identity and exact project grant."""
    values = tuple(
        str(env_get(name, "") or "").strip()
        for name in (
            "UAGENT_MANAGEMENT_READ_TOKEN",
            "UAGENT_MANAGEMENT_READ_PRINCIPAL",
            "UAGENT_MANAGEMENT_READ_PROJECT_ID",
        )
    )
    if not any(values):
        return None
    token, principal, project_id = values
    if (
        len(token.encode("utf-8")) < 32
        or not principal
        or len(principal) > 256
        or not project_id
        or len(project_id) > 128
    ):
        raise ValueError("incomplete read-only management configuration")
    return token, principal, project_id


def _authorized_project(principal: str, project_id: str) -> bool:
    """Use existing, explicitly granted membership without database writes.

    Directory-derived memberships depend on a separate identity-sync request.
    Since this service credential has no directory identity, deny those grants
    instead of trusting potentially stale cached group membership.
    """
    if not _long_memory_mod.is_sqlite_backend():
        return False
    path = Path(_long_memory_mod._sqlite_path())
    if not path.is_file():
        return False
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    ) as connection:
        connection.row_factory = sqlite3.Row
        grant = connection.execute(
            "SELECT pm.granted_by FROM project_memberships pm "
            "JOIN projects p ON p.project_id = pm.project_id "
            "WHERE pm.project_id = ? AND pm.principal_id = ? "
            "AND pm.status = 'active' AND p.status = 'active'",
            (project_id, principal),
        ).fetchone()
        if grant is None or grant["granted_by"] == "directory-policy":
            return False
        return ProjectAccessPolicy(SimpleNamespace(db=connection)).can_access(
            principal, project_id, "viewer"
        )


def _read_members_page(
    principal: str, project_id: str, cursor: str, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    """Read one project's membership snapshot with a fixed manual admin grant."""
    if not _long_memory_mod.is_sqlite_backend():
        raise FileNotFoundError("membership store unavailable")
    path = Path(_long_memory_mod._sqlite_path())
    if not path.is_file():
        raise FileNotFoundError("membership store unavailable")
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        grant = connection.execute(
            "SELECT pm.role, pm.granted_by FROM project_memberships pm "
            "JOIN projects p ON p.project_id = pm.project_id "
            "WHERE pm.project_id = ? AND pm.principal_id = ? "
            "AND pm.status = 'active' AND p.status = 'active'",
            (project_id, principal),
        ).fetchone()
        if (
            grant is None
            or grant["role"] != "admin"
            or grant["granted_by"] == "directory-policy"
            or not ProjectAccessPolicy(SimpleNamespace(db=connection)).can_access(
                principal, project_id, "admin"
            )
        ):
            raise PermissionError("explicit project admin required")
        rows = connection.execute(
            "SELECT principal_id, role, revision FROM project_memberships "
            "WHERE project_id = ? AND status = 'active' AND principal_id > ? "
            "ORDER BY principal_id LIMIT ?",
            (project_id, cursor, limit + 1),
        ).fetchall()
        members = [
            {
                "principal_id": str(row["principal_id"]),
                "role": str(row["role"]),
                "revision": int(row["revision"]),
            }
            for row in rows[:limit]
        ]
        next_cursor = members[-1]["principal_id"] if len(rows) > limit else None
        return members, next_cursor


def _open_session_store() -> sqlite3.Connection | None:
    """Open existing SQLite history without migrations or any write permission."""
    if os.environ.get("UAGENT_SESSION_STORE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return None
    configured = os.environ.get("UAGENT_SESSION_STORE_PATH", "").strip()
    legacy = Path(".uagent/sessions.sqlite3")
    path = (
        Path(configured)
        if configured
        else (
            Path(".uag/sessions.sqlite3")
            if legacy.exists()
            else get_state_dir() / "sessions" / "sessions.sqlite3"
        )
    )
    if not path.is_file():
        return None
    connection = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0
    )
    connection.row_factory = sqlite3.Row
    return connection


def _read_page(
    project_id: str,
    principal: str,
    cursor: tuple[str, str] | None,
    limit: int,
) -> tuple[list[dict[str, str]], str | None]:
    store = _open_session_store()
    if store is None:
        raise FileNotFoundError("session history unavailable")
    try:
        return _metadata_page(
            store,
            project_id=project_id,
            principal=principal,
            cursor=cursor,
            limit=limit,
        )
    finally:
        store.close()


def _as_rfc3339(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("invalid stored timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _decode_cursor(value: str) -> tuple[str, str] | None:
    if not value:
        return None
    if len(value) > 2048 or not value.isascii():
        raise ValueError("invalid cursor")
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        obj = json.loads(raw)
        if not isinstance(obj, dict) or set(obj) != {"t", "id"}:
            raise ValueError("invalid cursor")
        timestamp = obj["t"]
        session_id = obj["id"]
        if (
            not isinstance(timestamp, str)
            or not isinstance(session_id, str)
            or not 1 <= len(session_id) <= 128
        ):
            raise ValueError("invalid cursor")
        _as_rfc3339(timestamp)
        return timestamp, session_id
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise ValueError("invalid cursor") from exc


def _encode_cursor(timestamp: str, session_id: str) -> str:
    raw = json.dumps({"t": timestamp, "id": session_id}, separators=(",", ":")).encode(
        "utf-8"
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _metadata_page(
    store: sqlite3.Connection,
    *,
    project_id: str,
    principal: str,
    cursor: tuple[str, str] | None,
    limit: int,
) -> tuple[list[dict[str, str]], str | None]:
    """Query only safe columns; never SELECT message text or summaries."""
    condition = ""
    parameters: list[Any] = [project_id, principal]
    if cursor is not None:
        condition = (
            " AND (last_used_at < ? OR " "(last_used_at = ? AND session_id < ?))"
        )
        parameters.extend([cursor[0], cursor[0], cursor[1]])
    parameters.append(limit + 1)
    rows = store.execute(
        "SELECT session_id, created_at, last_used_at FROM sessions "
        "WHERE project = ? AND principal_id = ?"
        + condition
        + " ORDER BY last_used_at DESC, session_id DESC LIMIT ?",
        tuple(parameters),
    ).fetchall()
    items = [
        {
            "id": str(row["session_id"]),
            "project_id": project_id,
            "state": "recorded",
            "created_at": _as_rfc3339(row["created_at"]),
            "updated_at": _as_rfc3339(row["last_used_at"]),
        }
        for row in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last["last_used_at"], last["session_id"])
    return items, next_cursor


@app.get("/api/admin/integration/v1/sessions", include_in_schema=False)
async def get_integration_sessions(
    request: Request, project_id: str = "", cursor: str = "", limit: int = 50
):
    """Exact-project, exact-owner metadata with a separate service credential."""
    try:
        config = _read_config()
    except ValueError:
        return JSONResponse(
            status_code=503, content={"error": "read API misconfigured"}
        )
    if config is None:
        return JSONResponse(status_code=404, content={"error": "not supported"})
    token, principal, allowed_project = config
    scheme, separator, provided = (
        str(request.headers.get("authorization", "") or "").strip().partition(" ")
    )
    if (
        scheme.lower() != "bearer"
        or not separator
        or not hmac.compare_digest(
            token.encode("utf-8"), provided.strip().encode("utf-8")
        )
    ):
        return JSONResponse(status_code=401, content={"error": "invalid credential"})
    if project_id != allowed_project or not 1 <= len(project_id) <= 128:
        return JSONResponse(status_code=403, content={"error": "project not permitted"})
    try:
        decoded = _decode_cursor(cursor)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid cursor"})
    try:
        if not await asyncio.to_thread(_authorized_project, principal, project_id):
            return JSONResponse(
                status_code=403, content={"error": "project not permitted"}
            )
    except Exception:
        return JSONResponse(
            status_code=503, content={"error": "project policy unavailable"}
        )
    try:
        items, next_cursor = await asyncio.to_thread(
            _read_page, project_id, principal, decoded, min(max(limit, 1), 100)
        )
        instance_id = get_instance_id()
    except (OSError, RuntimeError, ValueError, sqlite3.DatabaseError):
        return JSONResponse(status_code=503, content={"error": "history unavailable"})
    return {
        "api_version": INTEGRATION_API_VERSION,
        "instance_id": instance_id,
        "items": items,
        "next_cursor": next_cursor,
    }


@app.get(
    "/api/admin/integration/v1/projects/{project_id}/members",
    include_in_schema=False,
)
async def get_integration_project_members(
    request: Request, project_id: str, cursor: str = "", limit: int = 50
):
    """Read only the preconfigured project's members; never modify policy."""
    try:
        config = _read_config()
    except ValueError:
        return JSONResponse(
            status_code=503, content={"error": "read API misconfigured"}
        )
    if config is None:
        return JSONResponse(status_code=404, content={"error": "not supported"})
    token, principal, allowed_project = config
    scheme, separator, provided = (
        str(request.headers.get("authorization", "") or "").strip().partition(" ")
    )
    if (
        scheme.lower() != "bearer"
        or not separator
        or not hmac.compare_digest(
            token.encode("utf-8"), provided.strip().encode("utf-8")
        )
    ):
        return JSONResponse(status_code=401, content={"error": "invalid credential"})
    if project_id != allowed_project or not 1 <= len(project_id) <= 128:
        return JSONResponse(status_code=403, content={"error": "project not permitted"})
    if not 1 <= limit <= 100:
        return JSONResponse(status_code=400, content={"error": "invalid pagination"})
    try:
        members, next_cursor = await asyncio.to_thread(
            _read_members_page, principal, project_id, cursor, limit
        )
        instance_id = get_instance_id()
    except PermissionError:
        return JSONResponse(status_code=403, content={"error": "project not permitted"})
    except (OSError, RuntimeError, ValueError, sqlite3.DatabaseError):
        return JSONResponse(
            status_code=503, content={"error": "project policy unavailable"}
        )
    return {
        "api_version": INTEGRATION_API_VERSION,
        "instance_id": instance_id,
        "project_id": project_id,
        "members": members,
        "next_cursor": next_cursor,
    }
