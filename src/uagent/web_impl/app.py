"""FastAPI application object and static/template paths (split from web.py)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import os
import threading
from typing import Any

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ImportError:
    from .._pip_auto import install_with_status as _install

    _install("uvicorn")
    _install("fastapi")
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates


@asynccontextmanager
async def _web_lifespan(_app):
    """Start and stop maintenance tasks for the Web application."""
    from .routes_api import _private_room_cleanup_loop

    cleanup_task = asyncio.create_task(_private_room_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="uag Web", lifespan=_web_lifespan)

# web.py used to live directly under src/uagent; this module is one level
# deeper (src/uagent/web_impl/), so step up one extra directory.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATE_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


_request_memory_stores: ContextVar[list[Any] | None] = ContextVar(
    "uag_web_request_memory_stores", default=None
)
_memory_store_tracking_lock = threading.Lock()

_PROCESS_AUTH_READ_PATHS = frozenset(
    {
        "/api/tool-genres",
        "/api/tools-enabled",
    }
)
_PROCESS_ADMIN_PATHS = frozenset(
    {
        "/api/artifacts/cleanup",
        "/api/artifacts/cleanup/report",
    }
)
_PROCESS_ADMIN_WRITE_PATHS = frozenset(
    {
        "/api/tool-genres",
        "/api/tools-enabled",
    }
)


def _ensure_memory_store_tracking() -> None:
    """Track MemoryStore instances opened by Web API routes for this request.

    routes_api imports ``open_memory_store`` directly, so install a lightweight
    wrapper around that module-local reference. The wrapper uses a ContextVar,
    which keeps concurrently executing requests isolated. Re-check on every
    request so tests or integrations that replace the factory are wrapped too.
    """
    from . import routes_api

    with _memory_store_tracking_lock:
        current = routes_api.open_memory_store
        if getattr(current, "_uag_web_request_store_tracking", False):
            return

        def tracked_open_memory_store(path):
            store = current(path)
            opened = _request_memory_stores.get()
            if opened is not None:
                opened.append(store)
            return store

        setattr(
            tracked_open_memory_store,
            "_uag_web_request_store_tracking",
            True,
        )
        routes_api.open_memory_store = tracked_open_memory_store


def _management_api_requires_directory_sync(path: str) -> bool:
    parts = [part for part in str(path or "").split("/") if part]
    if len(parts) < 4 or parts[0] != "api":
        return False
    if parts[1] == "projects" and parts[3] in {"members", "rooms"}:
        return True
    return parts[1] == "rooms" and parts[3] == "members"


def _request_identity(request: Request):
    """Reuse the Web API identity helper so tests/integrations share one resolver."""
    from . import routes_api

    return routes_api._request_identity(request)


def _process_api_guard(request: Request):
    """Protect process-wide controls without changing local single-user behavior."""
    path = request.url.path
    method = request.method.upper()
    requires_admin = path in _PROCESS_ADMIN_PATHS or (
        method != "GET" and path in _PROCESS_ADMIN_WRITE_PATHS
    )
    requires_auth = requires_admin or path in _PROCESS_AUTH_READ_PATHS
    if not requires_auth:
        return None, None
    try:
        identity = _request_identity(request)
    except Exception:
        return None, JSONResponse(
            status_code=401, content={"error": "authentication required"}
        )
    if requires_admin:
        from ..runtime.room_access import configured_admin_principals

        if identity.principal_id not in configured_admin_principals():
            return identity, JSONResponse(
                status_code=403, content={"error": "administrator required"}
            )
    return identity, None


def _sync_management_directory_policy(request: Request, identity: Any | None) -> Any:
    """Refresh directory-derived access before project/room administration."""
    if not _management_api_requires_directory_sync(request.url.path):
        return identity
    if identity is None:
        identity = _request_identity(request)
    from ..runtime.enterprise_identity import directory_group_policy_is_configured

    if not directory_group_policy_is_configured():
        return identity
    from . import routes_api
    from ..runtime.project_access import ProjectAccessPolicy

    store = routes_api._memory_store()
    try:
        ProjectAccessPolicy(store).sync_directory_policy(identity)
    finally:
        store.close()
    return identity


@app.middleware("http")
async def _close_request_memory_stores(request: Request, call_next):
    """Authorize guarded Web controls and close MemoryStore handles per request."""
    _ensure_memory_store_tracking()
    opened: list[Any] = []
    token = _request_memory_stores.set(opened)
    try:
        identity, denied = _process_api_guard(request)
        if denied is not None:
            return denied
        try:
            _sync_management_directory_policy(request, identity)
        except Exception:
            return JSONResponse(
                status_code=403, content={"error": "authorization policy unavailable"}
            )
        return await call_next(request)
    finally:
        try:
            for store in reversed(opened):
                try:
                    store.close()
                except Exception:
                    pass
        finally:
            _request_memory_stores.reset(token)
