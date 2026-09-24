"""Web API routes (split from web.py)."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from ..i18n import _
from .. import core
from ..providers import util_providers as providers
from .. import util_tools as tools_util
from ..tools import long_memory as _long_memory_mod
from .. import profile_manager as _profile_mod
from ..runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
    create_identity_resolver,
)
from ..runtime.memory_access import (
    MemoryAccessContext,
    MemoryAccessError,
    ScopedMemoryStore,
)
from ..runtime.memory_store import MemoryStoreConflictError, open_memory_store
from ..runtime.session_store import SessionStoreError, project_id_from_path
from ..runtime.project_access import ProjectAccessPolicy, ProjectMemoryService
from ..runtime.project_context import PROJECT_CONTEXT_COOKIE, ProjectContextStore
from ..runtime.room_access import RoomAccessPolicy, RoomMemoryService
from ..auth.oidc_sessions import get_oidc_session_store
from ..env_utils import env_get
from .agent_worker import run_agent_worker
from .app import app
from .rooms import _handle_mode_command, web_manager

# Tool genre state (initially all disabled; toggled via API)
_genre_enabled: dict[str, bool] = {}


def _request_identity(request: Request):
    identity = create_identity_resolver().resolve(request)
    if not identity.authenticated:
        raise IdentityResolutionError("authenticated identity is required")
    return identity


def _project_context_project(identity, request: Request, store=None) -> str:
    token = str(request.cookies.get(PROJECT_CONTEXT_COOKIE) or "").strip()
    if not token or identity.authn_kind in {"local", "oidc"}:
        return ""
    owned_store = store is None
    active_store = store or _memory_store()
    try:
        return ProjectContextStore(active_store).resolve(token, identity) or ""
    finally:
        if owned_store:
            active_store.close()


def _project_id(value: str, request: Request | None = None) -> str:
    project = str(value or "").strip()
    bound = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
    if not bound and request is not None:
        token = str(request.cookies.get("uag_oidc_session") or "").strip()
        bound = get_oidc_session_store().project_id(token) or ""
        if not bound:
            identity = _request_identity(request)
            bound = _project_context_project(identity, request)
    if not bound:
        raise MemoryAccessError("server project binding is required")
    if not project:
        project = bound
    if project != bound:
        raise MemoryAccessError("project is not bound to this server context")
    return bound


def _memory_store():
    if not _long_memory_mod.is_sqlite_backend():
        raise RuntimeError("Memory V3 Web API requires SQLite memory")
    return open_memory_store(_long_memory_mod._sqlite_path())


def _cleanup_expired_private_rooms(*, now: float | None = None) -> list[str]:
    """Expire idle private rooms without interrupting connected or running work."""
    current = time.time() if now is None else now
    ttl = web_manager.idle_ttl_seconds()
    cutoff = current - ttl
    web_manager.evict_idle_rooms(idle_ttl_seconds=ttl)
    active_room_ids = web_manager.active_room_ids()
    store = _memory_store()
    removed: list[str] = []
    try:
        policy = RoomAccessPolicy(store)
        for active_room_id in active_room_ids:
            policy.touch_private_room(active_room_id, now=current)
        expired = policy.list_expired_private_rooms(cutoff=cutoff)
        session_store = getattr(core, "session_store", None)

        def delete_session(session_id: str) -> None:
            if session_store is None:
                return
            try:
                session_store.get_session(session_id)
            except SessionStoreError as exc:
                if str(exc).startswith("unknown session:"):
                    return
                raise
            session_store.delete_session(session_id)

        for record in expired:
            room_id = record["room_id"]
            if room_id in active_room_ids:
                continue
            try:
                if policy.delete_private_room_if_expired(
                    room_id,
                    session_id=record["session_id"],
                    cutoff=cutoff,
                    before_delete=delete_session,
                ):
                    removed.append(room_id)
            except Exception:
                # A failed session deletion must leave the owner binding intact
                # so the next maintenance pass can safely retry.
                continue
        return removed
    finally:
        store.close()


async def _private_room_cleanup_loop() -> None:
    while True:
        try:
            if _long_memory_mod.is_sqlite_backend():
                await asyncio.to_thread(_cleanup_expired_private_rooms)
            else:
                web_manager.evict_idle_rooms()
        except Exception:
            print("[WARN] Private Web room cleanup failed; it will be retried.")
        ttl = web_manager.idle_ttl_seconds()
        await asyncio.sleep(min(max(ttl // 4, 30), 300))


def _memory_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, (IdentityConfigurationError, IdentityResolutionError)):
        status = 401
    elif isinstance(exc, MemoryAccessError):
        status = 403
    elif isinstance(exc, MemoryStoreConflictError):
        status = 409
    elif isinstance(exc, ValueError):
        status = 400
    else:
        status = 500
    return JSONResponse(status_code=status, content={"error": str(exc)})


def _legacy_local_only(request: Request) -> JSONResponse | None:
    try:
        identity = _request_identity(request)
    except Exception as exc:
        return _memory_error(exc)
    if identity.authn_kind != "local":
        return JSONResponse(
            status_code=403,
            content={"error": "legacy memory API is available only in local mode"},
        )
    return None


@app.get("/api/artifacts/cleanup/report")
async def artifact_cleanup_report():
    """Return a dry-run Artifact cleanup report for the active web session."""
    report_fn = getattr(core, "artifact_cleanup_report", None)
    if not callable(report_fn):
        return JSONResponse(
            status_code=409,
            content={"error": "Session store is not enabled."},
        )
    try:
        return report_fn()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/artifacts/cleanup")
async def artifact_cleanup(req: Request):
    """Return or execute guarded Artifact cleanup for the active web session."""
    body = await req.json()
    execute = bool(body.get("execute", False))
    if execute and body.get("confirm") != "DELETE":
        return JSONResponse(
            status_code=400,
            content={"error": "Set confirm to DELETE to execute cleanup."},
        )
    cleanup_fn = getattr(core, "artifact_cleanup", None)
    report_fn = getattr(core, "artifact_cleanup_report", None)
    fn = cleanup_fn if execute else report_fn
    if not callable(fn):
        return JSONResponse(
            status_code=409,
            content={"error": "Session store is not enabled."},
        )
    try:
        return fn(execute=True) if execute else fn()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


def _web_genre_labels() -> dict[str, str]:
    """Human-readable labels for every genre, kept in sync with _GENRE_BITMAP."""
    return {
        "basic": _("Basic (env, time, prompts, skills, memory, tools control)"),
        "file": _(
            "File (create, delete, read, write, search, zip, rename, hash, grep, list dir)"
        ),
        "comm": _("Communication (Teams, Discord, Bluesky)"),
        "office": _("Office (Excel, Word, PDF, PPT, document extraction)"),
        "devel": _(
            "Development (lint, test, git, DB, screenshot, browser, binary, compile)"
        ),
        "iot": _(
            "IoT (Bluetooth/BLE, ECHONET, Matter, SwitchBot, UPnP, camera, geo-IP)"
        ),
        "exec": _("Execution (cmd, python, pwsh, bash, sub-agent)"),
        "external": _("External (A2A, MCP, fetch, search web)"),
        "media": _("Media (image gen/edit/analyze, audio, QR code)"),
        "index": _(
            "Index (source/document parsers: py2idx, md2idx, excel2idx, csv2idx, ...)"
        ),
        "dev": _("Dev (lint_js_ts, mdformat_check)"),
        "web": _("Web (UCP commerce, public transit route)"),
        "utility": _("Utility (geodesic distance, pdf export, quantities)"),
    }


@app.get("/api/tool-genres")
async def get_tool_genres():
    """Return list of available genres and their current enabled state."""
    from ..tools._genre_control_util import _GENRE_BITMAP

    labels = _web_genre_labels()
    return {
        "genres": [
            {
                "key": genre,
                "label": labels.get(genre, genre),
                "enabled": _genre_enabled.get(genre, False),
            }
            for genre in _GENRE_BITMAP
        ],
        "busy": (
            web_manager.status.get("busy", False)
            if hasattr(web_manager, "status")
            else False
        ),
    }


@app.post("/api/tool-genres")
async def set_tool_genre(req: Request):
    """Toggle a tool genre on/off. Only allowed when idle."""
    from ..tools._genre_control_util import _GENRE_BITMAP
    from ..tools.genre_control_tool import _set_genre_tools_enabled

    body = await req.json()
    genre = str(body.get("genre", "")).strip().lower()
    enabled = bool(body.get("enabled", False))

    # Reject if busy
    busy = bool(getattr(core, "status_busy", False))
    if busy:
        return JSONResponse(
            status_code=409,
            content={
                "error": "Cannot change genres while busy. Wait for the current task to complete."
            },
        )

    if genre not in _GENRE_BITMAP:
        return JSONResponse(
            status_code=400, content={"error": f"Unknown genre: {genre}"}
        )

    try:
        msg = _set_genre_tools_enabled(genre, enabled)
        _genre_enabled[genre] = enabled
        return {"ok": True, "genre": genre, "enabled": enabled, "message": msg}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/tools-enabled")
async def get_tools_enabled():
    """Return whether tool sending to LLM is currently enabled."""
    return {"enabled": bool(getattr(core, "tools_enabled", True))}


@app.post("/api/tools-enabled")
async def set_tools_enabled(req: Request):
    """Toggle tool sending to LLM on/off. Only allowed when idle."""
    if bool(getattr(core, "status_busy", False)):
        return JSONResponse(
            status_code=409,
            content={
                "error": "Cannot change tools-enabled while busy. Wait for the current task to complete."
            },
        )
    body = await req.json()
    enabled = bool(body.get("enabled", True))
    core.tools_enabled = enabled
    state = "ON" if enabled else "OFF"
    return {
        "ok": True,
        "enabled": enabled,
        "message": f"Tool sending to LLM is now {state}",
    }


def _private_room_project(store, identity, room_id: str) -> str:
    room_id = str(room_id or "").strip()
    room_policy = RoomAccessPolicy(store)
    if not room_id or not room_policy.is_private_room_for(
        identity.principal_id, room_id
    ):
        raise MemoryAccessError("private room access is not permitted")
    project_policy = ProjectAccessPolicy(store)
    project_id = project_policy.room_project(room_id)
    if not project_id:
        raise MemoryAccessError("private room has no project binding")
    project_policy.require_access(identity.principal_id, project_id, "viewer")
    room_policy.touch_private_room(room_id)
    return project_id


def _private_room_session_id(room_id: str) -> str:
    store = _memory_store()
    try:
        return RoomAccessPolicy(store).private_room_session_id(room_id)
    finally:
        store.close()


def _personal_store(
    identity,
    project_id: str,
    *,
    request: Request | None = None,
    role: str = "viewer",
    room_id: str = "",
):
    store = _memory_store()
    try:
        project_policy = ProjectAccessPolicy(store)
        project_policy.sync_directory_policy(identity)
        supplied_project = str(project_id or "").strip()
        private_project = (
            _private_room_project(store, identity, room_id) if room_id else ""
        )
        if private_project and supplied_project and supplied_project != private_project:
            raise MemoryAccessError("project does not match the private room binding")

        configured_project = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
        token = (
            str(request.cookies.get("uag_oidc_session") or "").strip()
            if request
            else ""
        )
        session_project = get_oidc_session_store().project_id(token) if token else ""
        has_server_binding = bool(configured_project or session_project)
        if has_server_binding:
            bound_project = _project_id(supplied_project or private_project, request)
        elif private_project:
            bound_project = private_project
        else:
            bound_project = _project_id(supplied_project, request)
        if private_project and bound_project != private_project:
            raise MemoryAccessError("project does not match the private room binding")

        project_policy.require_access(identity.principal_id, bound_project, role)
        scoped = ScopedMemoryStore(
            store,
            MemoryAccessContext(
                principal_id=identity.principal_id,
                project_id=bound_project,
                authenticated=True,
                private_session=True,
            ),
        )
        return store, scoped
    except Exception:
        store.close()
        raise


@app.post("/api/me/private-room")
async def create_my_private_room(request: Request):
    """Issue an opaque, owner-only room for private Web Memory/Profile turns."""
    session = None
    project_context_token = ""
    project_context_max_age = 0
    session_store = getattr(core, "session_store", None)
    try:
        identity = _request_identity(request)
        raw_body = await request.body()
        body = json.loads(raw_body) if raw_body else {}
        if not isinstance(body, dict):
            raise ValueError("request body must be an object")
        requested_project = str(body.get("project_id", "") or "").strip()
        configured_project = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
        oidc_token = str(request.cookies.get("uag_oidc_session") or "").strip()
        oidc_project = (
            get_oidc_session_store().project_id(oidc_token) if oidc_token else ""
        )
        project_context = _project_context_project(identity, request)
        bound_project = configured_project or oidc_project or project_context or ""

        room_id = uuid4().hex
        from ..runtime.runtime_workdir import get_startup_workdir

        startup_workdir = str(env_get("UAGENT_WORKDIR", "") or get_startup_workdir())
        room_base_dir = os.getcwd()
        if startup_workdir and os.path.isdir(startup_workdir):
            room_base_dir = os.path.abspath(startup_workdir)
        if identity.authn_kind == "local":
            project_id = bound_project or project_id_from_path(room_base_dir)
        elif bound_project:
            if requested_project and requested_project != bound_project:
                raise MemoryAccessError("project is not bound to this server context")
            project_id = bound_project
        else:
            project_id = requested_project
            if not project_id:
                raise MemoryAccessError("server project binding is required")

        store = _memory_store()
        try:
            policy = ProjectAccessPolicy(store)
            if identity.authn_kind != "local":
                policy.sync_directory_policy(identity)
                policy.require_access(identity.principal_id, project_id, "viewer")
        finally:
            store.close()

        session_id = uuid4().hex
        if session_store is not None:
            session = session_store.create_session(
                project=project_id or room_base_dir,
                entry_point="web",
                project_path=room_base_dir,
            )
            session_id = session.session_id
            session_store.bind_identity_context(
                session_id,
                principal_id=identity.principal_id,
                room_id=room_id,
            )

        store = _memory_store()
        try:
            if identity.authn_kind != "local":
                policy = ProjectAccessPolicy(store)
                policy.sync_directory_policy(identity)
                policy.require_access(identity.principal_id, project_id, "viewer")
                if (
                    identity.authn_kind != "oidc"
                    and not configured_project
                    and not oidc_project
                ):
                    (
                        project_context_token,
                        project_context_max_age,
                    ) = ProjectContextStore(store).bind(
                        str(request.cookies.get(PROJECT_CONTEXT_COOKIE) or ""),
                        identity,
                        project_id,
                    )
            RoomAccessPolicy(store).create_private_room(
                identity.principal_id,
                room_id,
                project_id=project_id,
                session_id=session_id,
            )
        finally:
            store.close()

        room = web_manager.get_room(room_id)
        room.base_dir = room_base_dir
        room.session_id = session_id
        room.private_session = True
        room.project_id = project_id
        payload = {
            "ok": True,
            "room_id": room_id,
            "project_id": project_id,
            "private": True,
        }
        if project_context_token:
            response = JSONResponse(payload)
            secure_cookie = str(env_get("UAGENT_OIDC_COOKIE_SECURE", "1") or "")
            response.set_cookie(
                PROJECT_CONTEXT_COOKIE,
                project_context_token,
                max_age=project_context_max_age,
                httponly=True,
                secure=secure_cookie.strip().lower() not in {"0", "false", "no", "off"},
                samesite="lax",
                path="/",
            )
            return response
        return payload
    except Exception as exc:
        if session is not None and session_store is not None:
            try:
                session_store.delete_session(session.session_id)
            except Exception:
                pass
        return _memory_error(exc)


@app.get("/api/me/memories")
async def get_my_memories(request: Request, project_id: str = "", room_id: str = ""):
    try:
        store, scoped = _personal_store(
            _request_identity(request), project_id, request=request, room_id=room_id
        )
        try:
            memories = [
                record
                for record in scoped.records()
                if not record.get("shared_reference")
            ]
            return {"ok": True, "memories": memories}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.post("/api/me/memories")
async def add_my_memory(request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store, scoped = _personal_store(
            identity,
            body.get("project_id", ""),
            request=request,
            role="editor",
            room_id=str(body.get("room_id", "") or ""),
        )
        try:
            return {"ok": True, "memory": scoped.append(str(body.get("note", "")))}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/me/memories/{memory_id}")
async def update_my_memory(memory_id: str, request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store, scoped = _personal_store(
            identity,
            body.get("project_id", ""),
            request=request,
            role="editor",
            room_id=str(body.get("room_id", "") or ""),
        )
        try:
            memory = scoped.update(
                memory_id,
                str(body.get("note", "")),
                expected_revision=int(body.get("expected_revision", 0)),
            )
            return {"ok": True, "memory": memory}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.delete("/api/me/memories/{memory_id}")
async def delete_my_memory(memory_id: str, request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store, scoped = _personal_store(
            identity,
            body.get("project_id", ""),
            request=request,
            role="editor",
            room_id=str(body.get("room_id", "") or ""),
        )
        try:
            scoped.forget(
                memory_id, expected_revision=int(body.get("expected_revision", 0))
            )
            return {"ok": True}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/me/memories/{memory_id}/grants")
async def list_memory_grants(
    memory_id: str, request: Request, project_id: str = "", room_id: str = ""
):
    try:
        store, scoped = _personal_store(
            _request_identity(request), project_id, request=request, room_id=room_id
        )
        try:
            return {"ok": True, "grants": scoped.list_grants(memory_id)}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.post("/api/me/memories/{memory_id}/grants")
async def share_memory(memory_id: str, request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store, scoped = _personal_store(
            identity,
            body.get("project_id", ""),
            request=request,
            role="editor",
            room_id=str(body.get("room_id", "") or ""),
        )
        try:
            grant_id = scoped.share(
                memory_id,
                str(body.get("grantee_principal_id", "")),
                expected_revision=int(body.get("expected_revision", 0)),
            )
            return {"ok": True, "grant_id": grant_id}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.delete("/api/me/memories/{memory_id}/grants/{grant_id}")
async def revoke_memory_grant(memory_id: str, grant_id: str, request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store, scoped = _personal_store(
            identity,
            body.get("project_id", ""),
            request=request,
            role="editor",
            room_id=str(body.get("room_id", "") or ""),
        )
        try:
            scoped.revoke(memory_id, grant_id)
            return {"ok": True}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/me/shared-memories")
async def get_shared_memories(
    request: Request, project_id: str = "", room_id: str = ""
):
    try:
        store, scoped = _personal_store(
            _request_identity(request), project_id, request=request, room_id=room_id
        )
        try:
            memories = [
                record for record in scoped.records() if record.get("shared_reference")
            ]
            return {"ok": True, "memories": memories}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/me/shared-memories/{memory_id}")
async def get_shared_memory(
    memory_id: str, request: Request, project_id: str = "", room_id: str = ""
):
    try:
        store, scoped = _personal_store(
            _request_identity(request), project_id, request=request, room_id=room_id
        )
        try:
            memory = scoped.get(memory_id)
            if not memory or not memory.get("shared_reference"):
                return JSONResponse(
                    status_code=404, content={"error": "memory not found"}
                )
            return {"ok": True, "memory": memory}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/me/projects")
async def get_my_projects(request: Request):
    """List only projects available to the authenticated principal."""
    try:
        identity = _request_identity(request)
        store = _memory_store()
        try:
            policy = ProjectAccessPolicy(store)
            policy.sync_directory_policy(identity)
            configured = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
            token = str(request.cookies.get("uag_oidc_session") or "").strip()
            oidc_bound = get_oidc_session_store().project_id(token) or ""
            if configured:
                policy.require_access(identity.principal_id, configured, "viewer")
                return {
                    "ok": True,
                    "projects": [configured],
                    "bound_project": configured,
                }
            bound = oidc_bound or _project_context_project(identity, request, store)
            if bound:
                policy.require_access(identity.principal_id, bound, "viewer")
            if policy.is_global_admin(identity.principal_id):
                rows = store.db.execute(
                    "SELECT project_id FROM projects WHERE status='active' "
                    "ORDER BY project_id"
                ).fetchall()
            else:
                rows = store.db.execute(
                    "SELECT DISTINCT p.project_id FROM projects p "
                    "JOIN project_memberships m ON m.project_id=p.project_id "
                    "WHERE p.status='active' AND m.principal_id=? AND m.status='active' "
                    "ORDER BY p.project_id",
                    (identity.principal_id,),
                ).fetchall()
            return {
                "ok": True,
                "projects": [str(row["project_id"]) for row in rows],
                "bound_project": bound,
            }
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.post("/api/project-context")
async def select_project_context(request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        project_id = str(body.get("project_id", "") or "").strip()
        if not project_id:
            raise ValueError("project_id is required")
        store = _memory_store()
        try:
            project_policy = ProjectAccessPolicy(store)
            project_policy.sync_directory_policy(identity)
            project_policy.require_access(identity.principal_id, project_id, "viewer")
        finally:
            store.close()
        configured = str(env_get("UAGENT_MEMORY_PROJECT", "") or "").strip()
        if configured:
            if configured != project_id:
                raise MemoryAccessError("project is not bound to this server context")
            return {"ok": True, "project_id": project_id}
        token = str(request.cookies.get("uag_oidc_session") or "").strip()
        if token and get_oidc_session_store().bind_project(token, project_id):
            return {"ok": True, "project_id": project_id}
        if identity.authn_kind == "oidc":
            raise IdentityResolutionError(
                "authenticated project session is unavailable"
            )
        context_store = _memory_store()
        try:
            context_token, ttl = ProjectContextStore(context_store).bind(
                str(request.cookies.get(PROJECT_CONTEXT_COOKIE) or ""),
                identity,
                project_id,
            )
        finally:
            context_store.close()
        response = JSONResponse({"ok": True, "project_id": project_id})
        secure_cookie = str(env_get("UAGENT_OIDC_COOKIE_SECURE", "1") or "")
        response.set_cookie(
            PROJECT_CONTEXT_COOKIE,
            context_token,
            max_age=ttl,
            httponly=True,
            secure=secure_cookie.strip().lower() not in {"0", "false", "no", "off"},
            samesite="lax",
            path="/",
        )
        return response
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/projects/{project_id}/rooms/{room_id}")
async def bind_project_room(project_id: str, room_id: str, request: Request):
    try:
        identity = _request_identity(request)
        bound_project = _project_id(project_id, request)
        store = _memory_store()
        try:
            ProjectAccessPolicy(store).bind_room(
                identity.principal_id, bound_project, room_id
            )
            return {"ok": True, "project_id": bound_project, "room_id": room_id}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/projects/{project_id}/members")
async def get_project_members(project_id: str, request: Request):
    try:
        identity = _request_identity(request)
        bound_project = _project_id(project_id, request)
        store = _memory_store()
        try:
            members = ProjectAccessPolicy(store).list_members(
                identity.principal_id, bound_project
            )
            return {"ok": True, "members": members}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/projects/{project_id}/members/{principal_id}")
async def set_project_member(project_id: str, principal_id: str, request: Request):
    try:
        identity = _request_identity(request)
        bound_project = _project_id(project_id, request)
        body = await request.json()
        store = _memory_store()
        try:
            membership = ProjectAccessPolicy(store).set_membership(
                identity.principal_id,
                bound_project,
                principal_id,
                body.get("role", ""),
            )
            return {"ok": True, "membership": membership.__dict__}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.delete("/api/projects/{project_id}/members/{principal_id}")
async def delete_project_member(project_id: str, principal_id: str, request: Request):
    try:
        identity = _request_identity(request)
        bound_project = _project_id(project_id, request)
        store = _memory_store()
        try:
            ProjectAccessPolicy(store).revoke_membership(
                identity.principal_id, bound_project, principal_id
            )
            return {"ok": True}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


def _room_service(
    request: Request, room_id: str, project_id: str, *, role: str = "viewer"
):
    identity = _request_identity(request)
    store = _memory_store()
    bound_project = _project_id(project_id, request)
    project_policy = ProjectAccessPolicy(store)
    project_policy.sync_directory_policy(identity)
    project_policy.require_access(identity.principal_id, bound_project, role)
    project_policy.require_room_binding(bound_project, room_id)
    policy = RoomAccessPolicy(store)
    if policy.private_room_owner(room_id) is not None:
        if not policy.is_private_room_for(identity.principal_id, room_id):
            raise MemoryAccessError("private room access is not permitted")
        policy.touch_private_room(room_id)
    service = RoomMemoryService(
        store,
        policy,
        principal_id=identity.principal_id,
        project_id=bound_project,
        room_id=room_id,
    )
    return identity, store, policy, service


def _project_memory_service(request: Request, project_id: str):
    identity = _request_identity(request)
    store = _memory_store()
    try:
        bound_project = _project_id(project_id, request)
        policy = ProjectAccessPolicy(store)
        policy.sync_directory_policy(identity)
        service = ProjectMemoryService(
            store,
            policy,
            principal_id=identity.principal_id,
            project_id=bound_project,
        )
        return store, service
    except Exception:
        store.close()
        raise


@app.get("/api/projects/{project_id}/memories")
async def get_project_memories(project_id: str, request: Request):
    try:
        store, service = _project_memory_service(request, project_id)
        try:
            return {"ok": True, "memories": service.records()}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.post("/api/projects/{project_id}/memories")
async def add_project_memory(project_id: str, request: Request):
    try:
        body = await request.json()
        store, service = _project_memory_service(request, project_id)
        try:
            return {"ok": True, "memory": service.append(str(body.get("note", "")))}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/projects/{project_id}/memories/{memory_id}")
async def update_project_memory(project_id: str, memory_id: str, request: Request):
    try:
        body = await request.json()
        store, service = _project_memory_service(request, project_id)
        try:
            memory = service.update(
                memory_id,
                str(body.get("note", "")),
                expected_revision=int(body.get("expected_revision", 0)),
            )
            return {"ok": True, "memory": memory}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.delete("/api/projects/{project_id}/memories/{memory_id}")
async def delete_project_memory(project_id: str, memory_id: str, request: Request):
    try:
        body = await request.json()
        store, service = _project_memory_service(request, project_id)
        try:
            service.forget(
                memory_id, expected_revision=int(body.get("expected_revision", 0))
            )
            return {"ok": True}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/rooms/{room_id}/memories")
async def get_room_memories(room_id: str, request: Request, project_id: str = ""):
    try:
        _, store, _, service = _room_service(request, room_id, project_id)
        try:
            return {"ok": True, "memories": service.records()}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.post("/api/rooms/{room_id}/memories")
async def add_room_memory(room_id: str, request: Request):
    try:
        body = await request.json()
        _, store, _, service = _room_service(
            request, room_id, body.get("project_id", ""), role="editor"
        )
        try:
            return {"ok": True, "memory": service.append(str(body.get("note", "")))}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/rooms/{room_id}/memories/{memory_id}")
async def update_room_memory(room_id: str, memory_id: str, request: Request):
    try:
        body = await request.json()
        _, store, _, service = _room_service(
            request, room_id, body.get("project_id", ""), role="editor"
        )
        try:
            memory = service.update(
                memory_id,
                str(body.get("note", "")),
                expected_revision=int(body.get("expected_revision", 0)),
            )
            return {"ok": True, "memory": memory}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.delete("/api/rooms/{room_id}/memories/{memory_id}")
async def delete_room_memory(room_id: str, memory_id: str, request: Request):
    try:
        body = await request.json()
        _, store, _, service = _room_service(
            request, room_id, body.get("project_id", ""), role="editor"
        )
        try:
            service.forget(
                memory_id, expected_revision=int(body.get("expected_revision", 0))
            )
            return {"ok": True}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/rooms/{room_id}/members")
async def get_room_members(room_id: str, request: Request, project_id: str = ""):
    try:
        identity = _request_identity(request)
        store = _memory_store()
        try:
            bound_project = _project_id(project_id, request)
            project_policy = ProjectAccessPolicy(store)
            project_policy.require_access(identity.principal_id, bound_project, "admin")
            project_policy.require_room_binding(bound_project, room_id)
            members = RoomAccessPolicy(store).list_members(
                identity.principal_id, room_id
            )
            return {"ok": True, "members": members}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/rooms/{room_id}/members/{principal_id}")
async def set_room_member(room_id: str, principal_id: str, request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store = _memory_store()
        try:
            bound_project = _project_id(body.get("project_id", ""), request)
            project_policy = ProjectAccessPolicy(store)
            project_policy.require_access(identity.principal_id, bound_project, "admin")
            project_policy.require_room_binding(bound_project, room_id)
            membership = RoomAccessPolicy(store).set_membership(
                identity.principal_id, room_id, principal_id, body.get("role", "")
            )
            return {"ok": True, "membership": membership.__dict__}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.delete("/api/rooms/{room_id}/members/{principal_id}")
async def delete_room_member(room_id: str, principal_id: str, request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        store = _memory_store()
        try:
            bound_project = _project_id(body.get("project_id", ""), request)
            project_policy = ProjectAccessPolicy(store)
            project_policy.require_access(identity.principal_id, bound_project, "admin")
            project_policy.require_room_binding(bound_project, room_id)
            RoomAccessPolicy(store).revoke_membership(
                identity.principal_id, room_id, principal_id
            )
            return {"ok": True}
        finally:
            store.close()
    except Exception as exc:
        return _memory_error(exc)


@app.get("/api/memories")
async def get_memories(request: Request):
    """Return all long-term memory entries as structured JSON."""
    denied = _legacy_local_only(request)
    if denied is not None:
        return denied
    records = _long_memory_mod.load_long_memory_records()
    result = []
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            import time as _t

            dt = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(ts))
        else:
            dt = None
        result.append(
            {
                "idx": idx,
                "ts": ts,
                "datetime": dt,
                "note": str(rec.get("note", "")),
            }
        )
    return {"ok": True, "memories": result}


@app.post("/api/memories")
async def add_memory(req: Request):
    """Append a long-term memory entry."""
    denied = _legacy_local_only(req)
    if denied is not None:
        return denied
    body = await req.json()
    note = str(body.get("note", "")).strip()
    if not note:
        return JSONResponse(status_code=400, content={"error": "note is required"})
    _long_memory_mod.append_long_memory(note)
    return {"ok": True}


@app.put("/api/memories/{index}")
async def update_memory(index: int, req: Request):
    """Update a long-term memory entry in-place (preserves order)."""
    denied = _legacy_local_only(req)
    if denied is not None:
        return denied
    body = await req.json()
    new_note = str(body.get("note", "")).strip()
    if not new_note:
        return JSONResponse(status_code=400, content={"error": "note is required"})
    ok = _long_memory_mod.update_long_memory_entry(index, new_note)
    if not ok:
        return JSONResponse(
            status_code=404, content={"error": f"index {index} out of range"}
        )
    return {"ok": True}


@app.delete("/api/memories/{index}")
async def delete_memory(index: int, request: Request):
    """Delete a long-term memory entry."""
    denied = _legacy_local_only(request)
    if denied is not None:
        return denied
    ok = _long_memory_mod.delete_long_memory_entry(index)
    if not ok:
        return JSONResponse(
            status_code=404, content={"error": f"index {index} out of range"}
        )
    return {"ok": True}


@app.get("/api/profile")
async def get_profile(request: Request):
    """Return current profile data."""
    denied = _legacy_local_only(request)
    if denied is not None:
        return denied
    profile = _profile_mod.load_profile()
    return {"ok": True, "profile": profile}


@app.get("/api/me/profile")
async def get_my_profile(request: Request):
    try:
        identity = _request_identity(request)
        profile_key = "" if identity.authn_kind == "local" else identity.principal_id
        profile = (
            _profile_mod.load_profile(profile_key)
            if profile_key
            else _profile_mod.load_profile()
        )
        return {"ok": True, "profile": profile}
    except Exception as exc:
        return _memory_error(exc)


@app.put("/api/me/profile")
async def update_my_profile(request: Request):
    try:
        identity = _request_identity(request)
        body = await request.json()
        profile_key = "" if identity.authn_kind == "local" else identity.principal_id
        current = _profile_mod.load_profile(profile_key)
        for key in ("environment", "preferences", "constraints"):
            if key in body:
                current[key] = body[key]
        if profile_key:
            _profile_mod.save_profile(current, profile_key)
        else:
            _profile_mod.save_profile(current)
        return {"ok": True, "profile": current}
    except Exception as exc:
        return _memory_error(exc)


@app.post("/api/profile/clear")
async def clear_profile(request: Request):
    """Clear profile file."""
    denied = _legacy_local_only(request)
    if denied is not None:
        return denied
    try:
        path = _profile_mod.get_profile_file_path()
        if os.path.exists(path):
            os.remove(path)
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/profile/fromlog")
async def profile_from_logs(request: Request):
    """Rebuild profile from past logs."""
    denied = _legacy_local_only(request)
    if denied is not None:
        return denied
    from .. import core as _core_mod

    result = _profile_mod.profile_from_logs(_core_mod, max_log_files=100)
    if result:
        return {"ok": True, "profile": result}
    return {"ok": False, "error": "Failed to build profile from logs"}


@app.put("/api/profile")
async def update_profile(req: Request):
    """Update profile in-place. Body: {"environment": {...}, "preferences": [...], "constraints": [...]}"""
    denied = _legacy_local_only(req)
    if denied is not None:
        return denied
    body = await req.json()
    current = _profile_mod.load_profile()
    # Merge: only update provided keys
    for key in ("environment", "preferences", "constraints"):
        if key in body:
            current[key] = body[key]
    _profile_mod.save_profile(current)
    return {"ok": True, "profile": current}


def _log_first_user_message(path: str, limit: int = 120) -> str:
    """Return an existing log summary, falling back to the first user message."""
    first_user = ""
    existing_summary = ""
    try:
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if not isinstance(record, dict):
                    continue
                # Prefer metadata already present in the log.
                if not existing_summary:
                    for key in ("summary", "session_summary", "title"):
                        value = record.get(key)
                        if isinstance(value, str) and value.strip():
                            existing_summary = (
                                value.replace("\r", " ").replace("\n", " ").strip()
                            )
                            break
                if record.get("role") == "user" and not first_user:
                    text = (
                        str(record.get("content") or "")
                        .replace("\r", " ")
                        .replace("\n", " ")
                        .strip()
                    )
                    if text:
                        first_user = text
    except Exception:
        pass
    title = existing_summary or first_user
    return title[:limit] + ("…" if len(title) > limit else "") if title else ""


@app.get("/api/logs")
async def get_logs(request: Request, page: int = 1, per_page: int = 15):
    """Return only sessions visible to the authenticated principal."""
    try:
        identity = _request_identity(request)
    except Exception as exc:
        return _memory_error(exc)

    sqlite_sessions = (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    )
    if sqlite_sessions:
        store = core.session_store
        current_id = getattr(core, "session_id", None)
        rows = store.list_sessions(
            principal_id=(
                None if identity.authn_kind == "local" else identity.principal_id
            )
        )
        rows = [r for r in rows if r["session_id"] != current_id]
        items = []
        for row in rows:
            state = store.latest_response_state(row["session_id"])
            items.append(
                {
                    "path": row["session_id"],
                    "name": row["session_id"],
                    "project": row.get("project"),
                    "entry_point": row.get("entry_point"),
                    "summary": row.get("summary") or "",
                    "first_message": row.get("first_message") or "",
                    "last_message": row.get("last_message") or "",
                    "size": 0,
                    "mtime": row.get("created_at"),
                    "has_responses_state": state is not None,
                    "response_count": 1 if state else 0,
                    "response_status": (
                        state.get("status", "unknown") if state else "none"
                    ),
                    "latest_response_id": state.get("response_id", "") if state else "",
                    "response_provider": state.get("provider", "") if state else "",
                    "response_model": state.get("model", "") if state else "",
                }
            )
        total = len(items)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        return {
            "ok": True,
            "logs": items[start : start + per_page],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    if identity.authn_kind != "local":
        return JSONResponse(
            status_code=403,
            content={
                "error": "authenticated log access requires the SQLite session store"
            },
        )
    files = core.find_log_files(exclude_current=True)
    items = []
    for f in files:
        try:
            st = os.stat(f)
            items.append(
                {
                    "path": f,
                    "name": os.path.basename(f),
                    "summary": _log_first_user_message(f),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
            state_records = core.read_responses_state_records(f)
            latest_state = state_records[-1] if state_records else None
            items[-1].update(
                {
                    "has_responses_state": bool(state_records),
                    "response_count": len(state_records),
                    "response_status": (
                        str(latest_state.get("status") or "unknown")
                        if latest_state
                        else "none"
                    ),
                    "latest_response_id": (
                        str(latest_state.get("response_id") or "")
                        if latest_state
                        else ""
                    ),
                    "response_provider": (
                        str(latest_state.get("provider") or "") if latest_state else ""
                    ),
                    "response_model": (
                        str(latest_state.get("model") or "") if latest_state else ""
                    ),
                }
            )
        except Exception:
            pass
    # Sort by mtime descending
    items.sort(key=lambda x: x.get("mtime", 0) or 0, reverse=True)  # type: ignore[return-value]
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "ok": True,
        "logs": items[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@app.get("/api/logs/preview-by-path")
async def get_log_preview_by_path(request: Request, path: str = ""):
    """Return a preview only for a session visible to the current principal."""
    try:
        identity = _request_identity(request)
    except Exception as exc:
        return _memory_error(exc)
    if not path:
        return JSONResponse(status_code=400, content={"error": _("path is required")})
    sqlite_sessions = (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    )
    if sqlite_sessions:
        rows = core.session_store.list_sessions(
            principal_id=(
                None if identity.authn_kind == "local" else identity.principal_id
            )
        )
        rows = [r for r in rows if r["session_id"] != getattr(core, "session_id", None)]
        matches = [i for i, row in enumerate(rows) if row["session_id"] == path]
        if not matches:
            return JSONResponse(status_code=404, content={"error": _("File not found")})
        return await get_log_preview(matches[0], request)
    if identity.authn_kind != "local":
        return JSONResponse(
            status_code=403,
            content={
                "error": "authenticated log access requires the SQLite session store"
            },
        )
    files = core.find_log_files(exclude_current=True)
    norm = os.path.normpath(path)
    matches = [i for i, f in enumerate(files) if os.path.normpath(f) == norm]
    if not matches:
        return JSONResponse(status_code=404, content={"error": _("File not found")})
    idx = matches[0]
    return await get_log_preview(idx, request)


@app.get("/api/logs/{index}/preview")
async def get_log_preview(index: int, request: Request):
    """Return a preview only for a session visible to the current principal."""
    try:
        identity = _request_identity(request)
    except Exception as exc:
        return _memory_error(exc)
    sqlite_sessions = (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    )
    if sqlite_sessions:
        store = core.session_store
        rows = store.list_sessions(
            principal_id=(
                None if identity.authn_kind == "local" else identity.principal_id
            )
        )
        rows = [r for r in rows if r["session_id"] != getattr(core, "session_id", None)]
        if index < 0 or index >= len(rows):
            return JSONResponse(
                status_code=404, content={"error": _("Index out of range")}
            )
        row = rows[index]
        messages = store.list_messages(row["session_id"])
        users = [
            str(m.get("content") or "").strip()
            for m in messages
            if m.get("role") == "user"
        ]
        return {
            "ok": True,
            "index": index,
            "path": row["session_id"],
            "name": row["session_id"],
            "mtime": row.get("created_at"),
            "summary": row.get("summary") or "",
            "total_user": sum(m.get("role") == "user" for m in messages),
            "total_assistant": sum(m.get("role") == "assistant" for m in messages),
            "total_tool": sum(m.get("role") == "tool" for m in messages),
            "preserved_system": sum(m.get("role") == "system" for m in messages),
            "total_messages": len(messages),
            "first_user": users[0][:200] if users else "",
            "last_user": users[-1][:200] if users else "",
        }

    if identity.authn_kind != "local":
        return JSONResponse(
            status_code=403,
            content={
                "error": "authenticated log access requires the SQLite session store"
            },
        )
    files = core.find_log_files(exclude_current=True)
    if index < 0 or index >= len(files):
        return JSONResponse(status_code=404, content={"error": _("Index out of range")})
    path = files[index]
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None
    first_user = ""
    last_user = ""
    total_user = 0
    total_assistant = 0
    total_tool = 0
    preserved_system = 0
    last_cwd_path = None
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except Exception:
                    continue
                role = obj.get("role")
                if role == "user":
                    total_user += 1
                    content = str(obj.get("content") or "").strip()
                    if content:
                        if not first_user:
                            first_user = content[:200]
                        last_user = content[:200]
                elif role == "assistant":
                    total_assistant += 1
                elif role == "tool":
                    total_tool += 1
                elif role == "system":
                    content = obj.get("content")
                    if isinstance(content, str):
                        if content.startswith("[SKILL] ") or content.startswith(
                            "[HOOK] "
                        ):
                            preserved_system += 1
                        if content.startswith("[CWD] "):
                            try:
                                cobj = json.loads(content[len("[CWD] ") :].strip())
                            except Exception:
                                cobj = None
                            if isinstance(cobj, dict):
                                p = cobj.get("path")
                                if isinstance(p, str) and p.strip():
                                    last_cwd_path = p
    except Exception:
        pass
    # Match CLI :logs / :load "Conversation message count":
    # 1 (re-inserted SYSTEM_PROMPT) + preserved [SKILL]/[HOOK] system messages
    # + user/assistant/tool messages + [CWD] marker when auto-restored.
    cwd_bonus = 1 if (last_cwd_path and os.path.isdir(last_cwd_path)) else 0
    total_messages = (
        1 + preserved_system + total_user + total_assistant + total_tool + cwd_bonus
    )
    return {
        "ok": True,
        "index": index,
        "path": path,
        "name": os.path.basename(path),
        "mtime": mtime,
        "total_user": total_user,
        "total_assistant": total_assistant,
        "total_tool": total_tool,
        "preserved_system": preserved_system,
        "total_messages": total_messages,
        "first_user": first_user,
        "last_user": last_user,
    }


@app.post("/api/command")
async def api_command(req: Request):
    """Execute a room command for an authenticated room participant."""
    try:
        identity = _request_identity(req)
        body = await req.json()
    except Exception as exc:
        if isinstance(exc, (IdentityConfigurationError, IdentityResolutionError)):
            return _memory_error(exc)
        return JSONResponse(status_code=400, content={"error": _("Invalid JSON body")})
    room_id = str(body.get("room_id", "")).strip()
    cmd_line = str(body.get("command", "")).strip()
    if not room_id or not cmd_line:
        return JSONResponse(
            status_code=400,
            content={"error": _("room_id and command are required")},
        )
    from .connection_identity import require_room_access

    try:
        project_id, private_session = require_room_access(identity, room_id)
    except Exception as exc:
        return _memory_error(exc)
    command_name = cmd_line.lstrip(":").strip().split(maxsplit=1)[0].lower()
    if (private_session or identity.authn_kind != "local") and command_name in {
        "load",
        "cont",
        "logs",
        "sessions",
    }:
        return JSONResponse(
            status_code=403,
            content={"error": "session history commands are disabled for this room"},
        )
    room = web_manager.get_room(room_id)
    if private_session:
        room.private_session = True
        room.project_id = project_id
        room.session_id = _private_room_session_id(room_id) or room.session_id
    if not cmd_line.startswith(":"):
        cmd_line = f":{cmd_line}"
    if _handle_mode_command(cmd_line):
        return {"ok": True, "command": cmd_line, "result": "mode_changed"}
    # :cd -> room.set_base_dir() (room-scoped, no os.chdir())
    if cmd_line.lstrip(":").strip().startswith("cd"):
        _cd_arg = cmd_line.lstrip(":").strip()[3:].strip()
        try:
            room.set_base_dir(_cd_arg or ".")
            return {"ok": True, "command": "cd", "workdir": room.base_dir}
        except Exception as _cd_e:
            return JSONResponse(status_code=400, content={"error": str(_cd_e)})
    try:
        _client, _depname = None, ""
        try:
            _pname, _client, _depname = providers.make_client(core)
        except Exception:
            pass
        import io as _io
        import sys as _sys

        _capture = _io.StringIO()
        _old_stdout = _sys.stdout
        try:
            _sys.stdout = _capture
            _result = tools_util.handle_command(
                cmd_line, room.history, _client, _depname, core=core
            )
        finally:
            _sys.stdout = _old_stdout
        _output = _capture.getvalue().strip()
        if isinstance(_result, tools_util.CommandResult) and _result.run_llm:
            from ..runtime.identity_context import TurnContext

            worker_dir = room.base_dir
            turn = TurnContext.from_identity(
                identity,
                room_id=room_id,
                project_id=project_id or project_id_from_path(worker_dir),
                session_id=(
                    room.session_id or str(getattr(core, "session_id", "") or "")
                ),
                entry_point="web",
                private_session=private_session,
                server_bound_project=bool(project_id),
            )
            threading.Thread(
                target=run_agent_worker,
                args=(room, _result.prompt, None),
                kwargs={
                    "project_path": worker_dir,
                    "turn_context": turn,
                    "identity_context": identity,
                },
                daemon=True,
            ).start()
            return {
                "ok": True,
                "command": cmd_line,
                "run_llm": True,
                "prompt": _result.prompt,
            }
        if _output:
            room.add_message(
                {
                    "role": "assistant",
                    "content": _output,
                }
            )
        return {"ok": True, "command": cmd_line, "run_llm": False}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
