"""Versioned, read-only integration API for external UAG management services."""

from __future__ import annotations

import asyncio
import base64
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import os
from pathlib import Path
import sqlite3
import stat
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
        scopes = _read_scopes()
    except (OSError, ValueError):
        scopes = ()
    if any("session.metadata.read" in scope.capabilities for scope in scopes) and str(
        env_get("UAGENT_SESSION_STORE", "1")
    ).lower() not in {
        "0",
        "false",
        "no",
        "off",
    }:
        capabilities.append("session.metadata.read")

    if any("project.membership.read" in scope.capabilities for scope in scopes):
        capabilities.append("project.membership.read")

    # Publish the write capability only for a valid, separately protected
    # write configuration. A valid manifest alone never authorizes mutation.
    try:
        from .routes_integration_write import _write_scopes

        if await asyncio.to_thread(_write_scopes):
            capabilities.append("project.membership.write")
    except (OSError, RuntimeError, ValueError):
        pass

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


_READ_CAPABILITIES = frozenset({"session.metadata.read", "project.membership.read"})
_MAX_SCOPE_FILE_BYTES = 262144
_MAX_SCOPES = 64


@dataclass(frozen=True)
class _ReadScope:
    token: str
    principal: str
    project_id: str
    capabilities: frozenset[str]


def _validate_windows_dacl(
    acl: Any, owner: str, allowed_sids: set[str], sid_text: Any
) -> None:
    """Fail closed unless only the service principal/System/Admins can read.

    Deny ACEs cannot add access; unrecognized allow/object ACEs are rejected.
    """
    if acl is None or owner not in allowed_sids:
        raise ValueError("read scope file has an unsafe Windows owner or DACL")
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        if len(ace) != 3 or len(ace[0]) != 2:
            raise ValueError("unsupported Windows scope file ACE")
        ace_type, ace_flags = ace[0]
        if ace_flags & 0x08:  # INHERIT_ONLY_ACE does not apply to this file.
            continue
        if ace_type == 1:  # ACCESS_DENIED_ACE_TYPE
            continue
        if ace_type != 0 or sid_text(ace[2]) not in allowed_sids:
            raise ValueError("read scope file grants access outside trusted SIDs")


def _read_protected_scope_file_windows(path: Path) -> bytes:
    """Read the same Windows file handle whose DACL and attributes were checked."""
    try:
        import win32api
        import win32con
        import win32file
        import win32security

        handle = win32file.CreateFile(
            str(path),
            win32con.GENERIC_READ | win32con.READ_CONTROL,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            getattr(win32con, "FILE_FLAG_OPEN_REPARSE_POINT", 0x00200000),
            None,
        )
        try:
            attributes = win32file.GetFileInformationByHandle(handle)[0]
            if attributes & 0x410:  # DIRECTORY | REPARSE_POINT
                raise ValueError("read scope file must be a regular non-reparse file")
            if win32file.GetFileType(handle) != win32file.FILE_TYPE_DISK:
                raise ValueError("read scope file must be on a disk filesystem")
            descriptor = win32security.GetSecurityInfo(
                handle,
                win32security.SE_FILE_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION
                | win32security.DACL_SECURITY_INFORMATION,
            )
            token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
            )
            try:
                service_sid = win32security.ConvertSidToStringSid(
                    win32security.GetTokenInformation(token, win32security.TokenUser)[0]
                )
            finally:
                token.Close()
            _validate_windows_dacl(
                descriptor.GetSecurityDescriptorDacl(),
                win32security.ConvertSidToStringSid(
                    descriptor.GetSecurityDescriptorOwner()
                ),
                {service_sid, "S-1-5-18", "S-1-5-32-544"},
                win32security.ConvertSidToStringSid,
            )
            status, data = win32file.ReadFile(handle, _MAX_SCOPE_FILE_BYTES + 1)
            if status != 0:
                raise ValueError("read scope file read failed")
            return data
        finally:
            handle.Close()
    except Exception as exc:
        # Even unavailable/unsupported Windows APIs must deny, never skip ACLs.
        raise ValueError("could not securely read Windows scope file") from exc


def _read_protected_scope_file(path: Path) -> bytes:
    """Open without following the leaf symlink, then check the opened handle."""
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("read scope file must be an absolute non-symlink path")
    if os.name == "nt":
        return _read_protected_scope_file_windows(path)
    # A configured path may be a FIFO: opening without O_NONBLOCK would hang
    # the async API handler before fstat can reject non-regular files.
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | os.O_NONBLOCK
    )
    with os.fdopen(os.open(path, flags), "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("read scope file must be regular")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ValueError("read scope file is accessible by other users")
        if metadata.st_uid not in (0, os.geteuid()):
            raise ValueError("read scope file owner is not trusted")
        return source.read(_MAX_SCOPE_FILE_BYTES + 1)


def _validated_read_scopes(scopes: list[_ReadScope]) -> tuple[_ReadScope, ...]:
    tokens = [scope.token for scope in scopes]
    if len(tokens) != len(set(tokens)):
        raise ValueError("duplicate read scope credential")
    manifest_token = str(env_get("UAGENT_MANAGEMENT_API_TOKEN", "") or "").strip()
    if manifest_token and any(
        hmac.compare_digest(token.encode("utf-8"), manifest_token.encode("utf-8"))
        for token in tokens
    ):
        raise ValueError("read credential cannot reuse manifest-only credential")
    return tuple(scopes)


def _read_scopes() -> tuple[_ReadScope, ...]:
    """Load exact service-principal scopes; never derive identity from requests.

    The legacy three-variable configuration remains an independent scope.
    A separate protected file may add up to 64 per-project credentials.
    """
    scopes: list[_ReadScope] = []
    legacy = _read_config()
    if legacy is not None:
        token, principal, project_id = legacy
        scopes.append(_ReadScope(token, principal, project_id, _READ_CAPABILITIES))

    file_name = str(env_get("UAGENT_MANAGEMENT_READ_SCOPES_FILE", "") or "").strip()
    if not file_name:
        return _validated_read_scopes(scopes)
    document_bytes = _read_protected_scope_file(Path(file_name))
    if len(document_bytes) > _MAX_SCOPE_FILE_BYTES:
        raise ValueError("read scope file is too large")
    try:
        document = json.loads(document_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid read scope file") from exc
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "scopes"}
        or type(document["version"]) is not int
        or document["version"] != 1
        or not isinstance(document["scopes"], list)
        or len(document["scopes"]) > _MAX_SCOPES
    ):
        raise ValueError("invalid read scope file schema")
    instance_id = get_instance_id()
    for entry in document["scopes"]:
        if not isinstance(entry, dict) or set(entry) != {
            "instance_id",
            "token",
            "principal_id",
            "project_id",
            "capabilities",
        }:
            raise ValueError("invalid read scope record")
        token = entry["token"]
        principal = entry["principal_id"]
        project_id = entry["project_id"]
        grants = entry["capabilities"]
        if (
            not isinstance(entry["instance_id"], str)
            or entry["instance_id"] != instance_id
            or not isinstance(token, str)
            or not token.isascii()
            or not 32 <= len(token) <= 4096
            or any(ord(char) < 33 or ord(char) == 127 for char in token)
            or not isinstance(principal, str)
            or not 1 <= len(principal) <= 256
            or principal.strip() != principal
            or not isinstance(project_id, str)
            or not 1 <= len(project_id) <= 128
            or project_id.strip() != project_id
            or not isinstance(grants, list)
            or not grants
            or any(not isinstance(grant, str) for grant in grants)
            or len(grants) != len(set(grants))
            or not set(grants).issubset(_READ_CAPABILITIES)
        ):
            raise ValueError("invalid read scope values")
        scopes.append(_ReadScope(token, principal, project_id, frozenset(grants)))
    return _validated_read_scopes(scopes)


def _authenticate_read_scope(
    request: Request, scopes: tuple[_ReadScope, ...]
) -> _ReadScope | None:
    scheme, separator, provided = (
        str(request.headers.get("authorization", "") or "").strip().partition(" ")
    )
    if scheme.lower() != "bearer" or not separator:
        return None
    offered = provided.strip()
    if not offered or len(offered) > 4096:
        return None
    candidate = None
    offered_bytes = offered.encode("utf-8")
    # Compare every secret instead of exposing scope order through early return.
    for scope in scopes:
        if hmac.compare_digest(scope.token.encode("utf-8"), offered_bytes):
            candidate = scope
    return candidate


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
        scopes = _read_scopes()
    except (OSError, ValueError):
        return JSONResponse(
            status_code=503, content={"error": "read API misconfigured"}
        )
    if not scopes:
        return JSONResponse(status_code=404, content={"error": "not supported"})
    scope = _authenticate_read_scope(request, scopes)
    if scope is None:
        return JSONResponse(status_code=401, content={"error": "invalid credential"})
    if project_id != scope.project_id or not 1 <= len(project_id) <= 128:
        return JSONResponse(status_code=403, content={"error": "project not permitted"})
    principal = scope.principal
    if "session.metadata.read" not in scope.capabilities:
        return JSONResponse(
            status_code=403, content={"error": "capability not permitted"}
        )
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
        scopes = _read_scopes()
    except (OSError, ValueError):
        return JSONResponse(
            status_code=503, content={"error": "read API misconfigured"}
        )
    if not scopes:
        return JSONResponse(status_code=404, content={"error": "not supported"})
    scope = _authenticate_read_scope(request, scopes)
    if scope is None:
        return JSONResponse(status_code=401, content={"error": "invalid credential"})
    if project_id != scope.project_id or not 1 <= len(project_id) <= 128:
        return JSONResponse(status_code=403, content={"error": "project not permitted"})
    principal = scope.principal
    if "project.membership.read" not in scope.capabilities:
        return JSONResponse(
            status_code=403, content={"error": "capability not permitted"}
        )
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


# Load signed management write routes after the shared read-only helpers.
from . import routes_integration_write as _routes_integration_write  # noqa: E402,F401
