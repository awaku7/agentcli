"""FastAPI application object and static/template paths (split from web.py)."""

from __future__ import annotations

from contextvars import ContextVar
import os
import threading
from typing import Any

try:
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ImportError:
    from .._pip_auto import install_with_status as _install

    _install("uvicorn")
    _install("fastapi")
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates


app = FastAPI(title="uag Web")

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

        tracked_open_memory_store._uag_web_request_store_tracking = True  # type: ignore[attr-defined]
        routes_api.open_memory_store = tracked_open_memory_store


@app.middleware("http")
async def _close_request_memory_stores(request: Request, call_next):
    """Always close MemoryStore handles created while serving one HTTP request."""
    _ensure_memory_store_tracking()
    opened: list[Any] = []
    token = _request_memory_stores.set(opened)
    try:
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
