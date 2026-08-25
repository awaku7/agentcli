"""FastAPI application object and static/template paths (split from web.py)."""

from __future__ import annotations

import os

try:
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ImportError:
    from .._pip_auto import install_with_status as _install

    _install("uvicorn")
    _install("fastapi")
    from fastapi import FastAPI
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
