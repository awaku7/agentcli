"""Versioned, read-only integration API for external UAG management services."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hmac
from importlib.metadata import PackageNotFoundError, version
import json
from typing import Any

from fastapi import Request

from fastapi.responses import JSONResponse

from ..env_utils import env_get
from ..runtime.project_access import ProjectAccessPolicy
from ..runtime.session_store import SessionStore

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
    """UAG, not the admin web application, owns the project permissions."""
    from . import routes_api

    store = routes_api._memory_store()
    try:
        return ProjectAccessPolicy(store).can_access(principal, project_id, "viewer")
    finally:
        store.close()


def _open_session_store() -> SessionStore | None:
    return SessionStore.from_environment()


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
    store: SessionStore,
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
    rows = store._execute(
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
        if not _authorized_project(principal, project_id):
            return JSONResponse(
                status_code=403, content={"error": "project not permitted"}
            )
    except Exception:
        return JSONResponse(
            status_code=503, content={"error": "project policy unavailable"}
        )
    try:
        store = _open_session_store()
        if store is None:
            return JSONResponse(
                status_code=503, content={"error": "session history disabled"}
            )
        try:
            items, next_cursor = _metadata_page(
                store,
                project_id=project_id,
                principal=principal,
                cursor=decoded,
                limit=min(max(limit, 1), 100),
            )
        finally:
            store.close()
        instance_id = get_instance_id()
    except (OSError, RuntimeError, ValueError):
        return JSONResponse(status_code=503, content={"error": "history unavailable"})
    return {
        "api_version": INTEGRATION_API_VERSION,
        "instance_id": instance_id,
        "items": items,
        "next_cursor": next_cursor,
    }
