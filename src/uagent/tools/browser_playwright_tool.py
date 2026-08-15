# src/uagent/tools/browser_playwright_tool.py
from __future__ import annotations

import asyncio
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .i18n_helper import make_tool_translator
from . import _browser_session_registry as _session_reg

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:browser_playwright"

DEFAULT_SESSION_TTL_SEC = 300
DEFAULT_HARD_LIFETIME_SEC = 1800
MAX_SESSIONS = 2
MAX_PAGES = 10
DEFAULT_DOWNLOAD_DIR = "browser_downloads"

ACTION_ENUM = [
    "goto",
    "click",
    "fill",
    "wait",
    "content",
    "screenshot",
    "press",
    "scroll",
    "select",
    "hover",
    "evaluate",
    "extract_json",
    "wait_until",
    "get_attributes",
    "mouse_move",
    "mouse_click",
    "mouse_drag",
    "mouse_wheel",
    "keyboard_type",
    "save_storage",
    "intercept_network",
    "switch_page",
    "close_page",
    "list_pages",
    "wait_for_page",
    "get_accessibility_tree",
    "capture_console",
    "set_input_files",
    "element_screenshot",
    "block_resources",
    "handle_dialog",
    "check_visibility",
    "export_pdf",
    "route_mock",
    "switch_to_frame",
    "switch_to_parent_frame",
    "download",
    "trace_start",
    "trace_stop",
    "clipboard_read",
    "clipboard_write",
    "inject_script",
    "resize_viewport",
]

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "type": "function",
    "external_data": True,
    "tool_genre": "basic",
    "function": {
        "name": "browser_playwright",
        "description": _(
            "tool.description",
            default=(
                "Execute browser actions with Playwright. "
                "One-shot mode runs actions and closes. "
                "Session mode (session_action=start/act/snapshot/list/close) keeps the same browser across calls. "
                "New tabs/popups appear in pages[]/events; switch explicitly unless auto_focus_new_page=true. "
                "Always close sessions when finished."
            ),
        ),
        "x_search_terms": [
            "browser_playwright",
            "playwright",
            "browser automation",
            "screenshot",
            "scraping",
            "iframe",
            "download",
            "trace",
            "clipboard",
            "http auth",
            "inject script",
            "resize viewport",
            "session",
            "keep browser open",
            "fetch_url",
            "http get",
            "Get URL",
        ],
        "x_search_terms_en": [
            "browser",
            "playwright",
            "web",
            "automation",
            "session",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ACTION_ENUM,
                            },
                            "url": {"type": "string"},
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                            "key": {"type": "string"},
                            "timeout": {"type": "integer"},
                            "direction": {"type": "string", "enum": ["up", "down"]},
                            "expression": {"type": "string"},
                            "schema": {"type": "object"},
                            "condition": {
                                "type": "string",
                                "enum": [
                                    "load",
                                    "domcontentloaded",
                                    "networkidle",
                                    "visible",
                                    "hidden",
                                    "text",
                                ],
                            },
                            "text": {"type": "string"},
                            "attributes": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "to_x": {"type": "number"},
                            "to_y": {"type": "number"},
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "middle"],
                                "default": "left",
                            },
                            "click_count": {"type": "integer", "default": 1},
                            "delta_x": {"type": "number"},
                            "delta_y": {"type": "number"},
                            "delay": {"type": "integer", "default": 100},
                            "path": {
                                "type": "string",
                                "description": _(
                                    "param.path.description",
                                    default="File path to save output (used by content, screenshot, export_pdf, etc.).",
                                ),
                            },
                            "paths": {"type": "array", "items": {"type": "string"}},
                            "url_pattern": {"type": "string"},
                            "url_contains": {"type": "string"},
                            "index": {"type": "integer"},
                            "expect_new_page": {"type": "boolean", "default": False},
                            "resource_types": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "action": {"type": "string", "enum": ["accept", "dismiss"]},
                            "prompt_text": {"type": "string"},
                            "mock_data": {
                                "type": "object",
                                "description": "JSON data to return for route_mock.",
                            },
                            "script": {
                                "type": "string",
                                "description": "JavaScript code or URL to inject.",
                            },
                            "script_type": {
                                "type": "string",
                                "enum": ["content", "url"],
                                "default": "content",
                            },
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                        "required": ["type"],
                    },
                },
                "headless": {"type": "boolean", "default": True},
                "browser_channel": {
                    "type": "string",
                    "description": _(
                        "param.browser_channel.description",
                        default='Browser channel to use (e.g. "msedge" for Microsoft Edge, "chrome" for Google Chrome). Default: built-in Chromium.',
                    ),
                },
                "storage_state": {"type": "string"},
                "mobile_device": {"type": "string"},
                "user_agent": {"type": "string"},
                "viewport": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                },
                "locale": {"type": "string"},
                "timezone_id": {"type": "string"},
                "record_video_dir": {"type": "string"},
                "geolocation": {
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "accuracy": {"type": "number"},
                    },
                },
                "extra_http_headers": {
                    "type": "object",
                    "description": _(
                        "param.extra_http_headers.description",
                        default="Custom HTTP headers.",
                    ),
                },
                "color_scheme": {
                    "type": "string",
                    "enum": ["light", "dark", "no-preference"],
                },
                "http_credentials": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                    },
                    "description": _(
                        "param.http_credentials.description",
                        default="HTTP Basic authentication credentials.",
                    ),
                },
                "trace": {
                    "type": "object",
                    "properties": {
                        "screenshots": {"type": "boolean", "default": True},
                        "snapshots": {"type": "boolean", "default": True},
                    },
                    "description": _(
                        "param.trace.description",
                        default="Enable Playwright tracing. Trace will be saved at the end of one-shot, or when session closes if started.",
                    ),
                },
                "trace_path": {
                    "type": "string",
                    "default": "trace.zip",
                    "description": _(
                        "param.trace_path.description",
                        default="Path to save the trace zip file.",
                    ),
                },
                "session_id": {
                    "type": "string",
                    "description": _(
                        "param.session_id.description",
                        default="Existing browser session id for continued interaction.",
                    ),
                },
                "session_action": {
                    "type": "string",
                    "enum": ["start", "act", "snapshot", "list", "close"],
                    "description": _(
                        "param.session_action.description",
                        default="Session control. Omit with no session_id for one-shot mode.",
                    ),
                },
                "session_ttl_sec": {
                    "type": "integer",
                    "default": DEFAULT_SESSION_TTL_SEC,
                    "description": _(
                        "param.session_ttl_sec.description",
                        default="Idle timeout seconds for a session.",
                    ),
                },
                "keep_alive": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.keep_alive.description",
                        default="Kept for clarity; start/act keep the browser open until close/TTL.",
                    ),
                },
                "auto_focus_new_page": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.auto_focus_new_page.description",
                        default="If true, newly opened pages become active automatically.",
                    ),
                },
                "dialog_policy": {
                    "type": "string",
                    "enum": ["accept", "dismiss", "manual"],
                    "default": "manual",
                    "description": _(
                        "param.dialog_policy.description",
                        default="Default dialog handling for session pages.",
                    ),
                },
                "download_dir": {
                    "type": "string",
                    "description": _(
                        "param.download_dir.description",
                        default="Directory for downloads when action path is omitted. Default: browser_downloads/<session_id or oneshot>.",
                    ),
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Session registry
# ---------------------------------------------------------------------------


@dataclass
class BrowserSession:
    session_id: str
    created_at: float
    last_used_at: float
    ttl_sec: int
    hard_lifetime_sec: int
    headless: bool
    auto_focus_new_page: bool
    dialog_policy: str
    trace_opts: dict[str, Any] | None
    trace_path: str
    record_video_dir: str | None
    download_dir: str

    pw: Any = None
    browser: Any = None
    context: Any = None
    active_page: Any = None
    active_frame: Any = None

    console_logs: list[dict[str, Any]] = field(default_factory=list)
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    intercepted_data: list[dict[str, Any]] = field(default_factory=list)
    dialog_listeners: list[Callable] = field(default_factory=list)
    response_listeners: list[Callable] = field(default_factory=list)
    dialog_history: list[dict[str, Any]] = field(default_factory=list)

    lock: threading.RLock = field(default_factory=threading.RLock)
    loop: asyncio.AbstractEventLoop | None = None
    thread: threading.Thread | None = None
    closed: bool = False
    busy: bool = False


# Reload-safe session registry (lives outside this module)
_SESSIONS = _session_reg.get_sessions()
_SESSIONS_LOCK = _session_reg.get_lock()


def _now() -> float:
    return time.time()


def _iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _new_session_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"bp_{stamp}_{secrets.token_hex(3)}"


def _ensure_playwright_installed() -> dict[str, Any] | None:
    from .._pip_auto import install_with_status as _install_pw
    import subprocess as _sp
    import sys as _sys

    if not _install_pw("playwright", display_name="playwright"):
        return {"ok": False, "error": "playwright is not installed."}
    try:
        _sp.run(
            [_sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=_sys.stderr,
            stderr=_sys.stderr,
            timeout=300,
        )
    except Exception:
        return {"ok": False, "error": "playwright chromium browser install failed."}
    return None


def _page_info(page: Any, index: int) -> dict[str, Any]:
    url = ""
    title = ""
    opened = True
    try:
        if page.is_closed():
            opened = False
        else:
            url = page.url or ""
            try:
                title = page.title()
            except Exception:
                title = ""
    except Exception:
        opened = False
    return {"index": index, "url": url, "title": title, "open": opened}


async def _page_info_async(page: Any, index: int) -> dict[str, Any]:
    url = ""
    title = ""
    opened = True
    try:
        if page.is_closed():
            opened = False
        else:
            url = page.url or ""
            try:
                title = await page.title()
            except Exception:
                title = ""
    except Exception:
        opened = False
    return {"index": index, "url": url, "title": title, "open": opened}


async def _collect_pages(context: Any) -> list[dict[str, Any]]:
    pages = []
    for i, p in enumerate(list(context.pages)):
        pages.append(await _page_info_async(p, i))
    return pages


def _attach_page_listeners(session: BrowserSession, page: Any) -> None:
    def _on_console(msg: Any) -> None:
        try:
            session.console_logs.append({"type": msg.type, "text": msg.text})
        except Exception:
            pass

    page.on("console", _on_console)

    if session.dialog_policy in ("accept", "dismiss"):
        policy = session.dialog_policy

        def _on_dialog(dialog: Any) -> None:
            message = ""
            dtype = ""
            try:
                message = getattr(dialog, "message", "") or ""
                dtype = getattr(dialog, "type", "") or ""
            except Exception:
                pass

            async def _handle() -> None:
                try:
                    if policy == "accept":
                        await dialog.accept()
                    else:
                        await dialog.dismiss()
                except Exception:
                    pass
                event = {
                    "type": "dialog",
                    "dialog_type": dtype,
                    "action": policy,
                    "message": message,
                }
                session.pending_events.append(event)
                session.dialog_history.append(event)

            try:
                asyncio.create_task(_handle())
            except Exception:
                pass

        page.on("dialog", _on_dialog)

    def _on_close() -> None:
        session.pending_events.append({"type": "page_closed"})
        try:
            if session.active_page is page:
                remaining = [
                    p
                    for p in session.context.pages
                    if p is not page and not p.is_closed()
                ]
                if remaining:
                    session.active_page = remaining[-1]
                    session.active_frame = session.active_page.main_frame
                else:
                    session.active_page = None
                    session.active_frame = None
        except Exception:
            session.active_page = None
            session.active_frame = None

    page.on("close", lambda: _on_close())


def _attach_context_listeners(session: BrowserSession) -> None:
    async def _on_new_page(page: Any) -> None:
        try:
            # Enforce hard page limit: close extras beyond MAX_PAGES
            open_pages = [p for p in session.context.pages if not p.is_closed()]
            if len(open_pages) > MAX_PAGES:
                try:
                    await page.close()
                except Exception:
                    pass
                session.pending_events.append(
                    {
                        "type": "page_limit_exceeded",
                        "count": len(open_pages),
                        "max_pages": MAX_PAGES,
                        "action": "closed_new_page",
                    }
                )
                return

            _attach_page_listeners(session, page)
            try:
                idx = session.context.pages.index(page)
            except Exception:
                idx = len(session.context.pages) - 1
            session.pending_events.append(
                {
                    "type": "page_opened",
                    "index": idx,
                    "url": getattr(page, "url", "") or "",
                }
            )
            if session.auto_focus_new_page:
                session.active_page = page
                session.active_frame = page.main_frame
            if (
                len([p for p in session.context.pages if not p.is_closed()])
                >= MAX_PAGES
            ):
                session.pending_events.append(
                    {
                        "type": "page_limit_warning",
                        "count": len(session.context.pages),
                        "max_pages": MAX_PAGES,
                    }
                )
        except Exception:
            pass

    session.context.on("page", _on_new_page)


async def _build_context_args(
    p: Any, kwargs: dict[str, Any]
) -> dict[str, Any] | dict[str, Any]:
    context_args: dict[str, Any] = {}
    if kwargs.get("mobile_device"):
        device_config = p.devices.get(kwargs["mobile_device"])
        if device_config:
            context_args.update(device_config)

    for key in [
        "user_agent",
        "viewport",
        "locale",
        "timezone_id",
        "extra_http_headers",
        "color_scheme",
    ]:
        if kwargs.get(key):
            context_args[key] = kwargs[key]

    if kwargs.get("storage_state"):
        ss_path = kwargs["storage_state"]
        if Path(ss_path).exists():
            context_args["storage_state"] = ss_path
        else:
            return {"__error__": f"storage_state file not found: {ss_path}"}

    if kwargs.get("record_video_dir"):
        context_args["record_video_dir"] = kwargs["record_video_dir"]
    if kwargs.get("http_credentials"):
        context_args["http_credentials"] = kwargs["http_credentials"]
    if kwargs.get("geolocation"):
        context_args["geolocation"] = kwargs["geolocation"]
        existing_permissions = context_args.get("permissions", [])
        if "geolocation" not in existing_permissions:
            context_args["permissions"] = existing_permissions + ["geolocation"]
    return context_args


async def _launch_browser_bundle(
    *,
    headless: bool,
    kwargs: dict[str, Any],
) -> tuple[Any, Any, Any, Any] | dict[str, Any]:
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser_channel = kwargs.get("browser_channel")
    launch_kwargs: dict[str, Any] = {"headless": headless}
    if browser_channel:
        launch_kwargs["channel"] = browser_channel
    browser = await pw.chromium.launch(**launch_kwargs)
    context_args = await _build_context_args(pw, kwargs)
    if isinstance(context_args, dict) and context_args.get("__error__"):
        await browser.close()
        await pw.stop()
        return {"ok": False, "error": context_args["__error__"]}
    context = await browser.new_context(**context_args)
    page = await context.new_page()
    return pw, browser, context, page


# ---------------------------------------------------------------------------
# Action runner
# ---------------------------------------------------------------------------


class ActionRuntime:
    """Mutable runtime state while executing actions."""

    def __init__(
        self,
        *,
        context: Any,
        page: Any,
        frame: Any,
        console_logs: list[dict[str, Any]],
        intercepted_data: list[dict[str, Any]],
        dialog_listeners: list[Callable],
        response_listeners: list[Callable],
        pending_events: list[dict[str, Any]] | None = None,
        auto_focus_new_page: bool = False,
        download_dir: str | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.context = context
        self.page = page
        self.current_frame = frame
        self.console_logs = console_logs
        self.intercepted_data = intercepted_data
        self.dialog_listeners = dialog_listeners
        self.response_listeners = response_listeners
        self.pending_events = pending_events if pending_events is not None else []
        self.auto_focus_new_page = auto_focus_new_page
        self.download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
        self.kwargs = kwargs or {}
        self.results: list[dict[str, Any]] = []

    def require_frame(self) -> None:
        if self.page is None or (
            hasattr(self.page, "is_closed") and self.page.is_closed()
        ):
            recovered = self.recover_active_page()
            if not recovered:
                raise RuntimeError("No active page/frame. All pages have been closed.")
        if self.current_frame is None:
            if self.page is not None:
                self.current_frame = self.page.main_frame
            if self.current_frame is None:
                raise RuntimeError("No active page/frame. All pages have been closed.")

    def recover_active_page(self) -> bool:
        """Pick a live page if the current active page is gone."""
        try:
            pages = [
                p
                for p in list(self.context.pages)
                if p is not None and not p.is_closed()
            ]
        except Exception:
            pages = []
        if not pages:
            self.page = None
            self.current_frame = None
            return False
        # Prefer current if still valid
        if self.page is not None:
            try:
                if self.page in pages and not self.page.is_closed():
                    if self.current_frame is None:
                        self.current_frame = self.page.main_frame
                    return True
            except Exception:
                pass
        self.page = pages[-1]
        self.current_frame = self.page.main_frame
        return True

    def set_active_page(self, page: Any) -> None:
        self.page = page
        self.current_frame = page.main_frame if page is not None else None

    def resolve_download_path(self, action: dict[str, Any], suggested: str) -> str:
        raw = action.get("path")
        if raw:
            p = Path(str(raw))
            # Explicit path: keep relative-to-cwd semantics for compatibility
            if not p.is_absolute():
                p = Path.cwd() / p
            p.parent.mkdir(parents=True, exist_ok=True)
            return str(p)
        base = Path(self.download_dir)
        if not base.is_absolute():
            base = Path.cwd() / base
        base.mkdir(parents=True, exist_ok=True)
        name = suggested or f"download_{int(time.time())}"
        return str(base / name)

    async def active_index(self) -> int:
        try:
            return self.context.pages.index(self.page)
        except Exception:
            return -1

    async def resolve_page_index(self, action: dict[str, Any]) -> int | None:
        if "url_contains" in action and action.get("url_contains"):
            needle = str(action["url_contains"])
            for i, p in enumerate(self.context.pages):
                try:
                    if needle in (p.url or ""):
                        return i
                except Exception:
                    continue
            return None
        idx = action.get("index", 0)
        pages = self.context.pages
        if not pages:
            return None
        if idx == -1:
            return len(pages) - 1
        if idx < 0 or idx >= len(pages):
            return None
        return idx


async def run_actions(
    actions: list[dict[str, Any]],
    runtime: ActionRuntime,
    *,
    stop_trace_at_end: bool = False,
) -> dict[str, Any]:
    context = runtime.context
    kwargs = runtime.kwargs
    trace_opts = kwargs.get("trace")

    try:
        for action in actions:
            a_type = action.get("type")
            timeout = action.get("timeout", 10000)

            if a_type == "list_pages":
                # keep active page recovered
                runtime.recover_active_page()
                pages = await _collect_pages(context)
                runtime.results.append(
                    {
                        "type": "list_pages",
                        "active_page_index": await runtime.active_index(),
                        "pages": pages,
                    }
                )
                continue

            if a_type == "wait_for_page":
                before = set(id(p) for p in context.pages)
                deadline = time.time() + (timeout / 1000.0)
                needle = action.get("url_contains")
                new_page = None
                while time.time() < deadline:
                    for p in context.pages:
                        if id(p) not in before:
                            if needle:
                                try:
                                    if needle not in (p.url or ""):
                                        continue
                                except Exception:
                                    continue
                            new_page = p
                            break
                    if new_page is not None:
                        break
                    await asyncio.sleep(0.05)
                if new_page is None:
                    return {
                        "ok": False,
                        "error": "wait_for_page timed out",
                        "code": "page_not_found",
                        "results": runtime.results,
                    }
                if action.get("focus", True) or runtime.auto_focus_new_page:
                    runtime.set_active_page(new_page)
                    try:
                        await new_page.bring_to_front()
                    except Exception:
                        pass
                runtime.results.append(
                    {
                        "type": "wait_for_page",
                        "index": context.pages.index(new_page),
                        "url": new_page.url,
                    }
                )
                continue

            if a_type == "switch_to_frame":
                runtime.require_frame()
                frame_element = await runtime.current_frame.wait_for_selector(
                    action["selector"], timeout=timeout
                )
                runtime.current_frame = await frame_element.content_frame()
                if runtime.current_frame is None:
                    runtime.current_frame = runtime.page.main_frame
                    return {
                        "ok": False,
                        "error": f"Selector '{action['selector']}' did not resolve to an iframe.",
                        "results": runtime.results,
                    }
                runtime.results.append(
                    {"type": "switch_to_frame", "selector": action["selector"]}
                )

            elif a_type == "switch_to_parent_frame":
                runtime.require_frame()
                parent = runtime.current_frame.parent_frame
                runtime.current_frame = parent if parent else runtime.page.main_frame
                runtime.results.append({"type": "switch_to_parent_frame"})

            elif a_type == "download":
                runtime.require_frame()
                async with runtime.page.expect_download(
                    timeout=timeout
                ) as download_info:
                    if "selector" in action:
                        await runtime.current_frame.click(
                            action["selector"], timeout=timeout
                        )
                download = await download_info.value
                save_path = runtime.resolve_download_path(
                    action, download.suggested_filename
                )
                await download.save_as(save_path)
                runtime.results.append(
                    {
                        "type": "download",
                        "path": str(Path(save_path).absolute()),
                        "suggested_filename": download.suggested_filename,
                        "url": download.url,
                    }
                )
                runtime.pending_events.append(
                    {
                        "type": "download",
                        "path": str(Path(save_path).absolute()),
                        "url": download.url,
                    }
                )

            elif a_type == "trace_start":
                await context.tracing.start(
                    screenshots=action.get("screenshots", True),
                    snapshots=action.get("snapshots", True),
                )
                runtime.results.append({"type": "trace_start"})

            elif a_type == "trace_stop":
                t_path = action.get("path", kwargs.get("trace_path", "trace.zip"))
                await context.tracing.stop(path=t_path)
                runtime.results.append(
                    {"type": "trace_stop", "path": str(Path(t_path).absolute())}
                )

            elif a_type == "clipboard_read":
                runtime.require_frame()
                text = await runtime.current_frame.evaluate(
                    "navigator.clipboard.readText()"
                )
                runtime.results.append({"type": "clipboard_read", "text": text})

            elif a_type == "clipboard_write":
                runtime.require_frame()
                text = action.get("value", "")
                await runtime.current_frame.evaluate(
                    f"navigator.clipboard.writeText({json.dumps(text)})"
                )
                runtime.results.append({"type": "clipboard_write"})

            elif a_type == "inject_script":
                runtime.require_frame()
                if action.get("script_type", "content") == "url":
                    await runtime.current_frame.add_script_tag(url=action["script"])
                else:
                    await runtime.current_frame.add_script_tag(content=action["script"])
                runtime.results.append({"type": "inject_script"})

            elif a_type == "resize_viewport":
                w = action.get("width", 1280)
                h = action.get("height", 720)
                await runtime.page.set_viewport_size({"width": w, "height": h})
                runtime.results.append(
                    {"type": "resize_viewport", "width": w, "height": h}
                )

            elif a_type == "export_pdf":
                pdf_path = action.get(
                    "path", f"output_{int(asyncio.get_event_loop().time())}.pdf"
                )
                await runtime.page.pdf(path=pdf_path)
                runtime.results.append(
                    {"type": "export_pdf", "path": str(Path(pdf_path).absolute())}
                )

            elif a_type == "route_mock":
                pattern = action.get("url_pattern", "**/*")
                data = action.get("mock_data", {})
                await runtime.page.unroute(pattern)
                await runtime.page.route(
                    pattern, lambda route, _data=data: route.fulfill(json=_data)
                )
                runtime.results.append({"type": "route_mock", "pattern": pattern})

            elif a_type == "check_visibility":
                runtime.require_frame()
                runtime.results.append(
                    {
                        "type": "visibility_check",
                        "selector": action["selector"],
                        "is_visible": await runtime.current_frame.is_visible(
                            action["selector"], timeout=timeout
                        ),
                    }
                )

            elif a_type == "handle_dialog":
                for prev_listener in runtime.dialog_listeners:
                    try:
                        runtime.page.remove_listener("dialog", prev_listener)
                    except Exception:
                        pass
                runtime.dialog_listeners.clear()

                dialog_action = action.get("action", "accept")
                prompt_text = action.get("prompt_text")

                def _make_handler(_a: str, _t: str | None):
                    def handler(d):
                        async def _run():
                            try:
                                if _a == "accept":
                                    await d.accept(_t)
                                else:
                                    await d.dismiss()
                            except Exception:
                                pass
                            runtime.pending_events.append(
                                {
                                    "type": "dialog",
                                    "action": _a,
                                    "message": getattr(d, "message", "") or "",
                                    "dialog_type": getattr(d, "type", "") or "",
                                }
                            )

                        asyncio.create_task(_run())

                    return handler

                listener = _make_handler(dialog_action, prompt_text)
                runtime.page.on("dialog", listener)
                runtime.dialog_listeners.append(listener)
                runtime.results.append(
                    {"type": "handle_dialog", "action": dialog_action}
                )

            elif a_type == "block_resources":
                blocked = set(action.get("resource_types", ["image"]))
                await runtime.page.route(
                    "**/*",
                    lambda r, _blocked=blocked: (
                        r.abort()
                        if r.request.resource_type in _blocked
                        else r.continue_()
                    ),
                )
                runtime.results.append(
                    {"type": "block_resources", "resource_types": list(blocked)}
                )

            elif a_type == "element_screenshot":
                runtime.require_frame()
                el = await runtime.current_frame.wait_for_selector(
                    action["selector"], timeout=timeout
                )
                s_path = action.get(
                    "path", f"el_{int(asyncio.get_event_loop().time())}.png"
                )
                if el:
                    await el.screenshot(path=s_path)
                runtime.results.append(
                    {
                        "type": "element_screenshot",
                        "path": str(Path(s_path).absolute()),
                    }
                )

            elif a_type == "set_input_files":
                if "paths" in action:
                    files = action["paths"]
                elif "path" in action:
                    files = [action["path"]]
                else:
                    files = []
                await runtime.page.set_input_files(
                    action["selector"], files, timeout=timeout
                )

            elif a_type == "capture_console":
                runtime.results.append(
                    {"type": "console_logs", "data": list(runtime.console_logs)}
                )

            elif a_type == "get_accessibility_tree":
                snapshot = await runtime.page.accessibility.snapshot()
                runtime.results.append({"type": "accessibility_tree", "data": snapshot})

            elif a_type == "switch_page":
                idx = await runtime.resolve_page_index(action)
                if idx is None:
                    return {
                        "ok": False,
                        "error": "Page not found for switch_page.",
                        "code": "page_not_found",
                        "results": runtime.results,
                    }
                runtime.set_active_page(context.pages[idx])
                try:
                    await runtime.page.bring_to_front()
                except Exception:
                    pass
                runtime.results.append(
                    {
                        "type": "switch_page",
                        "index": idx,
                        "url": runtime.page.url,
                    }
                )

            elif a_type == "close_page":
                idx = None
                if "index" in action or "url_contains" in action:
                    idx = await runtime.resolve_page_index(action)
                    if idx is None:
                        return {
                            "ok": False,
                            "error": "Page not found for close_page.",
                            "code": "page_not_found",
                            "results": runtime.results,
                        }
                    target = context.pages[idx]
                else:
                    target = runtime.page
                await target.close()
                if context.pages:
                    runtime.set_active_page(context.pages[-1])
                else:
                    runtime.set_active_page(None)
                runtime.results.append({"type": "close_page", "index": idx})

            elif a_type == "intercept_network":
                for prev_listener in runtime.response_listeners:
                    try:
                        runtime.page.remove_listener("response", prev_listener)
                    except Exception:
                        pass
                runtime.response_listeners.clear()

                pattern = action.get("url_pattern", "")

                def _make_handler(_pat: str):
                    def handler(r):
                        if _pat in r.url:
                            runtime.intercepted_data.append({"url": r.url})

                    return handler

                listener = _make_handler(pattern)
                runtime.page.on("response", listener)
                runtime.response_listeners.append(listener)
                runtime.results.append(
                    {"type": "intercept_network", "url_pattern": pattern}
                )

            elif a_type == "goto":
                runtime.require_frame()
                wu = action.get("wait_until", "networkidle")
                to = action.get("timeout", 30000)
                await runtime.current_frame.goto(
                    action["url"], wait_until=wu, timeout=to
                )

            elif a_type == "click":
                runtime.require_frame()
                if action.get("expect_new_page"):
                    async with context.expect_page(timeout=timeout) as new_page_info:
                        await runtime.current_frame.click(
                            action["selector"], timeout=timeout
                        )
                    new_page = await new_page_info.value
                    runtime.pending_events.append(
                        {
                            "type": "page_opened",
                            "index": context.pages.index(new_page),
                            "url": new_page.url,
                        }
                    )
                    # expect_new_page implies focus on the new page
                    runtime.set_active_page(new_page)
                    try:
                        await new_page.bring_to_front()
                    except Exception:
                        pass
                    runtime.results.append(
                        {
                            "type": "click",
                            "expect_new_page": True,
                            "new_page_index": context.pages.index(new_page),
                            "url": new_page.url,
                        }
                    )
                else:
                    await runtime.current_frame.click(
                        action["selector"], timeout=timeout
                    )

            elif a_type == "fill":
                runtime.require_frame()
                await runtime.current_frame.fill(
                    action["selector"], action["value"], timeout=timeout
                )

            elif a_type == "press":
                runtime.require_frame()
                await runtime.current_frame.press(
                    action["selector"], action["key"], timeout=timeout
                )

            elif a_type == "keyboard_type":
                runtime.require_frame()
                if "selector" in action:
                    await runtime.current_frame.focus(action["selector"])
                await runtime.page.keyboard.type(
                    action["value"], delay=action.get("delay", 100)
                )

            elif a_type == "wait":
                runtime.require_frame()
                sel = action.get("selector")
                if sel:
                    await runtime.current_frame.wait_for_selector(sel, timeout=timeout)
                else:
                    await asyncio.sleep(timeout / 1000.0)

            elif a_type == "wait_until":
                cond = action.get("condition", "load")
                if cond in ["load", "domcontentloaded", "networkidle"]:
                    await runtime.page.wait_for_load_state(cond, timeout=timeout)
                elif cond in ["visible", "hidden"]:
                    runtime.require_frame()
                    await runtime.current_frame.wait_for_selector(
                        action["selector"], state=cond, timeout=timeout
                    )
                elif cond == "text":
                    text = action.get("text", "")
                    if not text:
                        return {
                            "ok": False,
                            "error": "text is required when condition='text'.",
                            "results": runtime.results,
                        }
                    await runtime.page.wait_for_function(
                        f"document.body.innerText.includes({json.dumps(text)})",
                        timeout=timeout,
                    )
                else:
                    return {
                        "ok": False,
                        "error": f"Unknown wait_until condition: {cond}",
                        "results": runtime.results,
                    }

            elif a_type == "hover":
                runtime.require_frame()
                await runtime.current_frame.hover(action["selector"], timeout=timeout)

            elif a_type == "scroll":
                runtime.require_frame()
                d = action.get("direction", "down")
                factor = "window.innerHeight" if d == "down" else "-window.innerHeight"
                await runtime.current_frame.evaluate(f"window.scrollBy(0, {factor})")

            elif a_type == "select":
                runtime.require_frame()
                await runtime.current_frame.select_option(
                    action["selector"], action["value"], timeout=timeout
                )

            elif a_type == "evaluate":
                runtime.require_frame()
                runtime.results.append(
                    {
                        "type": "evaluate",
                        "data": await runtime.current_frame.evaluate(
                            action["expression"]
                        ),
                    }
                )

            elif a_type == "extract_json":
                runtime.require_frame()
                schema = action.get("schema", {})
                extracted = {}
                for k, v in schema.items():
                    els = await runtime.current_frame.query_selector_all(v)
                    texts = [await el.inner_text() for el in els]
                    extracted[k] = texts
                runtime.results.append({"type": "extract_json", "data": extracted})

            elif a_type == "get_attributes":
                runtime.require_frame()
                elements = await runtime.current_frame.query_selector_all(
                    action["selector"]
                )
                attr_results = []
                for el in elements:
                    entry = {"text": await el.inner_text()}
                    for n in action.get("attributes", []):
                        entry[n] = await el.get_attribute(n)
                    attr_results.append(entry)
                runtime.results.append({"type": "get_attributes", "data": attr_results})

            elif a_type == "mouse_move":
                await runtime.page.mouse.move(action["x"], action["y"])

            elif a_type == "mouse_click":
                await runtime.page.mouse.click(
                    action.get("x", 0),
                    action.get("y", 0),
                    button=action.get("button", "left"),
                    click_count=action.get("click_count", 1),
                )

            elif a_type == "mouse_drag":
                btn = action.get("button", "left")
                await runtime.page.mouse.move(action["x"], action["y"])
                await runtime.page.mouse.down(button=btn)
                await runtime.page.mouse.move(action["to_x"], action["to_y"])
                await runtime.page.mouse.up(button=btn)

            elif a_type == "mouse_wheel":
                await runtime.page.mouse.wheel(
                    action.get("delta_x", 0), action.get("delta_y", 0)
                )

            elif a_type == "save_storage":
                p_path = action.get("path", "storage_state.json")
                await context.storage_state(path=p_path)
                runtime.results.append(
                    {"type": "save_storage", "path": str(Path(p_path).absolute())}
                )

            elif a_type == "content":
                runtime.require_frame()
                html = await runtime.current_frame.content()
                c_path = action.get("path")
                if c_path:
                    Path(c_path).write_text(html, encoding="utf-8")
                    runtime.results.append(
                        {"type": "content", "path": str(Path(c_path).absolute())}
                    )
                else:
                    runtime.results.append({"type": "content", "data": html})

            elif a_type == "screenshot":
                s_path = action.get(
                    "path", f"debug_{int(asyncio.get_event_loop().time())}.png"
                )
                await runtime.page.screenshot(path=s_path)
                runtime.results.append(
                    {"type": "screenshot", "path": str(Path(s_path).absolute())}
                )

            else:
                return {
                    "ok": False,
                    "error": f"Unknown action type: {a_type}",
                    "results": runtime.results,
                }

        if runtime.intercepted_data:
            runtime.results.append(
                {"type": "intercepted_network", "data": list(runtime.intercepted_data)}
            )

        if stop_trace_at_end and trace_opts:
            t_path = kwargs.get("trace_path", "trace.zip")
            await context.tracing.stop(path=t_path)
            runtime.results.append(
                {"type": "trace", "path": str(Path(t_path).absolute())}
            )

        v_path = None
        if kwargs.get("record_video_dir") and runtime.page is not None:
            vid = runtime.page.video
            if vid:
                p = vid.path()
                if p:
                    v_path = str(Path(p).absolute())

        final_url = None
        title = None
        if runtime.page is not None and not runtime.page.is_closed():
            final_url = runtime.page.url
            try:
                title = await runtime.page.title()
            except Exception:
                title = None

        return {
            "ok": True,
            "results": runtime.results,
            "final_url": final_url,
            "title": title,
            "video_path": v_path,
            "active_page_index": await runtime.active_index(),
            "pages": await _collect_pages(context),
            "events": list(runtime.pending_events),
        }

    except Exception as e:
        last_url = None
        try:
            if runtime.page is not None:
                last_url = runtime.page.url
        except Exception:
            pass
        return {
            "ok": False,
            "error": str(e),
            "last_url": last_url,
            "results": runtime.results,
            "events": list(runtime.pending_events),
            "pages": await _collect_pages(context) if context else [],
            "active_page_index": (
                await runtime.active_index() if runtime.page is not None else None
            ),
        }


# ---------------------------------------------------------------------------
# One-shot
# ---------------------------------------------------------------------------


async def execute_actions(
    actions: list[dict[str, Any]], headless: bool, **kwargs: Any
) -> dict[str, Any]:
    err = _ensure_playwright_installed()
    if err:
        return err

    launched = await _launch_browser_bundle(headless=headless, kwargs=kwargs)
    if isinstance(launched, dict):
        return launched
    pw, browser, context, page = launched

    console_logs: list[dict[str, Any]] = []
    page.on(
        "console",
        lambda msg: console_logs.append({"type": msg.type, "text": msg.text}),
    )

    dialog_listeners: list[Callable] = []
    response_listeners: list[Callable] = []
    pending_events: list[dict[str, Any]] = []

    def _on_new_page(p: Any) -> None:
        pending_events.append(
            {
                "type": "page_opened",
                "index": len(context.pages) - 1,
                "url": getattr(p, "url", "") or "",
            }
        )
        p.on(
            "console",
            lambda msg: console_logs.append({"type": msg.type, "text": msg.text}),
        )

    context.on("page", _on_new_page)

    trace_opts = kwargs.get("trace")
    if trace_opts:
        await context.tracing.start(
            screenshots=trace_opts.get("screenshots", True),
            snapshots=trace_opts.get("snapshots", True),
        )

    runtime = ActionRuntime(
        context=context,
        page=page,
        frame=page.main_frame,
        console_logs=console_logs,
        intercepted_data=[],
        dialog_listeners=dialog_listeners,
        response_listeners=response_listeners,
        pending_events=pending_events,
        auto_focus_new_page=bool(kwargs.get("auto_focus_new_page", False)),
        download_dir=str(
            kwargs.get("download_dir") or Path(DEFAULT_DOWNLOAD_DIR) / "oneshot"
        ),
        kwargs=kwargs,
    )
    try:
        return await run_actions(actions, runtime, stop_trace_at_end=bool(trace_opts))
    finally:
        try:
            await context.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _start_session_worker(session: BrowserSession) -> None:
    loop = asyncio.new_event_loop()
    session.loop = loop

    def _runner() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(
        target=_runner, name=f"browser-session-{session.session_id}", daemon=True
    )
    session.thread = thread
    thread.start()


def _run_on_session(session: BrowserSession, coro: Any, timeout: float = 300.0) -> Any:
    if session.loop is None:
        raise RuntimeError("session loop is not running")
    fut = asyncio.run_coroutine_threadsafe(coro, session.loop)
    return fut.result(timeout=timeout)


async def _session_launch(
    session: BrowserSession, kwargs: dict[str, Any]
) -> dict[str, Any] | None:
    launched = await _launch_browser_bundle(headless=session.headless, kwargs=kwargs)
    if isinstance(launched, dict):
        return launched
    pw, browser, context, page = launched
    session.pw = pw
    session.browser = browser
    session.context = context
    session.active_page = page
    session.active_frame = page.main_frame
    _attach_page_listeners(session, page)
    _attach_context_listeners(session)
    if session.trace_opts:
        await context.tracing.start(
            screenshots=session.trace_opts.get("screenshots", True),
            snapshots=session.trace_opts.get("snapshots", True),
        )
    return None


async def _session_close_async(session: BrowserSession) -> None:
    if session.closed:
        return
    session.closed = True
    try:
        if session.trace_opts and session.context is not None:
            try:
                await session.context.tracing.stop(path=session.trace_path)
            except Exception:
                pass
        if session.context is not None:
            await session.context.close()
        if session.browser is not None:
            await session.browser.close()
        if session.pw is not None:
            await session.pw.stop()
    finally:
        session.context = None
        session.browser = None
        session.pw = None
        session.active_page = None
        session.active_frame = None


def _stop_session_worker(session: BrowserSession) -> None:
    if session.loop is not None:
        try:
            session.loop.call_soon_threadsafe(session.loop.stop)
        except Exception:
            pass
    if session.thread is not None and session.thread.is_alive():
        session.thread.join(timeout=5)
    session.loop = None
    session.thread = None


def _session_status_payload(
    session: BrowserSession,
    *,
    session_action: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = result or {}
    expires = session.last_used_at + session.ttl_sec
    hard = session.created_at + session.hard_lifetime_sec
    expires_at = min(expires, hard)

    payload = {
        "ok": result.get("ok", True),
        "session_id": session.session_id,
        "session_action": session_action,
        "session_alive": not session.closed,
        "active_page_index": result.get("active_page_index"),
        "pages": result.get("pages", []),
        "events": result.get("events", []),
        "final_url": result.get("final_url"),
        "title": result.get("title"),
        "results": result.get("results", []),
        "video_path": result.get("video_path"),
        "ttl_sec": session.ttl_sec,
        "expires_at": _iso_from_ts(expires_at),
        "download_dir": session.download_dir,
        "error": result.get("error"),
        "code": result.get("code"),
        "last_url": result.get("last_url"),
    }
    # drop Nones for cleanliness but keep ok/results
    return {
        k: v
        for k, v in payload.items()
        if v is not None or k in ("ok", "results", "pages", "events")
    }


async def _session_snapshot_async(session: BrowserSession) -> dict[str, Any]:
    if session.context is None:
        return {
            "ok": False,
            "error": "No active page in session.",
            "code": "no_active_page",
            "pages": [],
            "events": list(session.pending_events),
        }

    # Recover active page if needed
    try:
        active_dead = session.active_page is None or session.active_page.is_closed()
    except Exception:
        active_dead = True
    if active_dead:
        live = [p for p in session.context.pages if not p.is_closed()]
        if live:
            session.active_page = live[-1]
            session.active_frame = session.active_page.main_frame
        else:
            events = list(session.pending_events)
            session.pending_events.clear()
            return {
                "ok": False,
                "error": "No active page in session.",
                "code": "no_active_page",
                "pages": await _collect_pages(session.context),
                "events": events,
            }

    pages = await _collect_pages(session.context)
    try:
        active_index = session.context.pages.index(session.active_page)
    except Exception:
        active_index = -1
    title = None
    final_url = None
    try:
        if not session.active_page.is_closed():
            final_url = session.active_page.url
            title = await session.active_page.title()
    except Exception:
        pass
    events = list(session.pending_events)
    session.pending_events.clear()
    return {
        "ok": True,
        "results": [],
        "final_url": final_url,
        "title": title,
        "active_page_index": active_index,
        "pages": pages,
        "events": events,
    }


async def _session_act_async(
    session: BrowserSession, actions: list[dict[str, Any]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    if session.closed or session.context is None:
        return {
            "ok": False,
            "error": "Session is dead or has no active page.",
            "code": "session_dead",
        }

    # Recover active page if closed
    try:
        active_dead = session.active_page is None or session.active_page.is_closed()
    except Exception:
        active_dead = True
    if active_dead:
        live = [p for p in session.context.pages if not p.is_closed()]
        if not live:
            return {
                "ok": False,
                "error": "Session is dead or has no active page.",
                "code": "no_active_page",
            }
        session.active_page = live[-1]
        session.active_frame = session.active_page.main_frame

    # refresh kwargs that affect actions (trace_path etc.)
    merged = dict(kwargs)
    if session.trace_path:
        merged.setdefault("trace_path", session.trace_path)
    if session.record_video_dir:
        merged.setdefault("record_video_dir", session.record_video_dir)
    merged.setdefault("download_dir", session.download_dir)

    runtime = ActionRuntime(
        context=session.context,
        page=session.active_page,
        frame=session.active_frame or session.active_page.main_frame,
        console_logs=session.console_logs,
        intercepted_data=session.intercepted_data,
        dialog_listeners=session.dialog_listeners,
        response_listeners=session.response_listeners,
        pending_events=session.pending_events,
        auto_focus_new_page=session.auto_focus_new_page,
        download_dir=session.download_dir,
        kwargs=merged,
    )
    result = await run_actions(actions, runtime, stop_trace_at_end=False)
    # persist active pointers
    session.active_page = runtime.page
    session.active_frame = runtime.current_frame
    # drain events already included
    session.pending_events = []
    return result


def _session_expired(session: BrowserSession, now: float | None = None) -> bool:
    now = now if now is not None else _now()
    if session.closed:
        return True
    if now - session.last_used_at > session.ttl_sec:
        return True
    if now - session.created_at > session.hard_lifetime_sec:
        return True
    return False


def _close_session_sync(session: BrowserSession) -> None:
    with session.lock:
        if session.busy:
            # still try to close
            pass
        try:
            if session.loop is not None and not session.closed:
                _run_on_session(session, _session_close_async(session), timeout=60)
        except Exception:
            session.closed = True
        _stop_session_worker(session)
        with _SESSIONS_LOCK:
            _SESSIONS.pop(session.session_id, None)


def _pin_browser_tool(reason: str = "active browser session") -> None:
    try:
        from ._genre_control_util import pin_tool

        pin_tool("browser_playwright", reason=reason)
    except Exception:
        pass


def _maybe_unpin_browser_tool() -> None:
    """Unpin browser_playwright when no live sessions remain."""
    try:
        with _SESSIONS_LOCK:
            alive = any(not getattr(s, "closed", True) for s in _SESSIONS.values())
        if not alive:
            from ._genre_control_util import unpin_tool

            unpin_tool("browser_playwright")
    except Exception:
        pass


def _touch_all_sessions() -> None:
    """Refresh last_used_at for all live sessions (e.g. during human_ask wait)."""
    now = _now()
    with _SESSIONS_LOCK:
        for session in _SESSIONS.values():
            if not getattr(session, "closed", True):
                session.last_used_at = now


def prune_expired_sessions() -> None:
    now = _now()
    with _SESSIONS_LOCK:
        items = list(_SESSIONS.values())
    closed_any = False
    for session in items:
        if _session_expired(session, now):
            _close_session_sync(session)
            closed_any = True
    if closed_any:
        _maybe_unpin_browser_tool()


def _atexit_close_all() -> None:
    with _SESSIONS_LOCK:
        items = list(_SESSIONS.values())
    for session in items:
        try:
            _close_session_sync(session)
        except Exception:
            pass


def _register_atexit() -> None:
    _session_reg.register_atexit(_atexit_close_all)


def list_sessions_payload() -> dict[str, Any]:
    prune_expired_sessions()
    with _SESSIONS_LOCK:
        items = []
        for s in _SESSIONS.values():
            items.append(
                {
                    "session_id": s.session_id,
                    "created_at": _iso_from_ts(s.created_at),
                    "last_used_at": _iso_from_ts(s.last_used_at),
                    "ttl_sec": s.ttl_sec,
                    "expires_at": _iso_from_ts(
                        min(
                            s.last_used_at + s.ttl_sec,
                            s.created_at + s.hard_lifetime_sec,
                        )
                    ),
                    "headless": s.headless,
                    "closed": s.closed,
                    "busy": s.busy,
                    "download_dir": s.download_dir,
                    "auto_focus_new_page": s.auto_focus_new_page,
                    "dialog_policy": s.dialog_policy,
                }
            )
    return {
        "ok": True,
        "session_action": "list",
        "sessions": items,
        "count": len(items),
    }


def start_session(args: dict[str, Any]) -> dict[str, Any]:
    prune_expired_sessions()
    _register_atexit()

    with _SESSIONS_LOCK:
        if len(_SESSIONS) >= MAX_SESSIONS:
            return {
                "ok": False,
                "error": f"Too many browser sessions (max {MAX_SESSIONS}). Close one first.",
                "code": "session_limit",
            }

    err = _ensure_playwright_installed()
    if err:
        return err

    now = _now()
    session_id = _new_session_id()
    download_dir = str(
        args.get("download_dir") or Path(DEFAULT_DOWNLOAD_DIR) / session_id
    )
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    session = BrowserSession(
        session_id=session_id,
        created_at=now,
        last_used_at=now,
        ttl_sec=int(args.get("session_ttl_sec") or DEFAULT_SESSION_TTL_SEC),
        hard_lifetime_sec=DEFAULT_HARD_LIFETIME_SEC,
        headless=bool(args.get("headless", True)),
        auto_focus_new_page=bool(args.get("auto_focus_new_page", False)),
        dialog_policy=str(args.get("dialog_policy") or "manual"),
        trace_opts=args.get("trace"),
        trace_path=str(args.get("trace_path") or "trace.zip"),
        record_video_dir=args.get("record_video_dir"),
        download_dir=download_dir,
    )

    # kwargs for launch
    launch_kwargs = dict(args)
    for k in [
        "actions",
        "session_id",
        "session_action",
        "session_ttl_sec",
        "keep_alive",
        "auto_focus_new_page",
        "dialog_policy",
        "headless",
        "download_dir",
    ]:
        launch_kwargs.pop(k, None)

    _start_session_worker(session)
    try:
        launch_err = _run_on_session(session, _session_launch(session, launch_kwargs))
        if launch_err:
            _stop_session_worker(session)
            return launch_err
    except Exception as e:
        _stop_session_worker(session)
        return {"ok": False, "error": str(e), "code": "session_dead"}

    with _SESSIONS_LOCK:
        _SESSIONS[session.session_id] = session
    _pin_browser_tool(reason=f"active browser session: {session.session_id}")

    actions = list(args.get("actions") or [])
    result: dict[str, Any]
    if actions:
        with session.lock:
            session.busy = True
            try:
                result = _run_on_session(
                    session, _session_act_async(session, actions, launch_kwargs)
                )
            finally:
                session.busy = False
                session.last_used_at = _now()
    else:
        with session.lock:
            result = _run_on_session(session, _session_snapshot_async(session))
            session.last_used_at = _now()

    return _session_status_payload(session, session_action="start", result=result)


def _get_session(session_id: str) -> BrowserSession | dict[str, Any]:
    prune_expired_sessions()
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        return {
            "ok": False,
            "error": f"session not found: {session_id}",
            "code": "session_not_found",
        }
    if _session_expired(session):
        _close_session_sync(session)
        return {
            "ok": False,
            "error": f"session expired: {session_id}",
            "code": "session_not_found",
        }
    return session


def act_session(args: dict[str, Any]) -> dict[str, Any]:
    session_id = args.get("session_id")
    if not session_id:
        return {
            "ok": False,
            "error": "session_id is required for act",
            "code": "invalid_argument",
        }
    session = _get_session(str(session_id))
    if isinstance(session, dict):
        return session

    actions = list(args.get("actions") or [])
    if not actions:
        return {
            "ok": False,
            "error": "actions is required for session_action=act",
            "code": "invalid_argument",
        }

    kwargs = dict(args)
    for k in [
        "actions",
        "session_id",
        "session_action",
        "session_ttl_sec",
        "keep_alive",
        "auto_focus_new_page",
        "dialog_policy",
        "headless",
        "download_dir",
    ]:
        kwargs.pop(k, None)

    with session.lock:
        if session.busy:
            return {
                "ok": False,
                "error": "session is busy",
                "code": "session_busy",
                "session_id": session.session_id,
            }
        session.busy = True
        try:
            result = _run_on_session(
                session, _session_act_async(session, actions, kwargs)
            )
        except Exception as e:
            # browser likely dead
            try:
                _close_session_sync(session)
            except Exception:
                pass
            return {
                "ok": False,
                "error": str(e),
                "code": "session_dead",
                "session_id": session_id,
            }
        finally:
            session.busy = False
            session.last_used_at = _now()

    if result.get("code") == "session_dead" or (
        not result.get("ok")
        and "Target page, context or browser has been closed"
        in str(result.get("error", ""))
    ):
        _close_session_sync(session)
        result["code"] = "session_dead"
        result["session_alive"] = False
    return _session_status_payload(session, session_action="act", result=result)


def snapshot_session(args: dict[str, Any]) -> dict[str, Any]:
    session_id = args.get("session_id")
    if not session_id:
        return {
            "ok": False,
            "error": "session_id is required for snapshot",
            "code": "invalid_argument",
        }
    session = _get_session(str(session_id))
    if isinstance(session, dict):
        return session
    with session.lock:
        if session.busy:
            return {
                "ok": False,
                "error": "session is busy",
                "code": "session_busy",
                "session_id": session.session_id,
            }
        session.busy = True
        try:
            result = _run_on_session(session, _session_snapshot_async(session))
        except Exception as e:
            _close_session_sync(session)
            return {
                "ok": False,
                "error": str(e),
                "code": "session_dead",
                "session_id": session_id,
            }
        finally:
            session.busy = False
            session.last_used_at = _now()
    return _session_status_payload(session, session_action="snapshot", result=result)


def close_session(args: dict[str, Any]) -> dict[str, Any]:
    session_id = args.get("session_id")
    if not session_id:
        return {
            "ok": False,
            "error": "session_id is required for close",
            "code": "invalid_argument",
        }
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(str(session_id))
    if session is None:
        return {
            "ok": False,
            "error": f"session not found: {session_id}",
            "code": "session_not_found",
        }
    _close_session_sync(session)
    _maybe_unpin_browser_tool()
    return {
        "ok": True,
        "session_id": session_id,
        "session_action": "close",
        "session_alive": False,
        "results": [],
        "pages": [],
        "events": [],
    }


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def _run_async_blocking(coro_factory: Callable[[], Any]) -> Any:
    """Run async Playwright work from sync callers, including active loops."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    import queue
    import threading

    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put((True, asyncio.run(coro_factory())))
        except BaseException as exc:
            result_queue.put((False, exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()
    ok, result = result_queue.get()
    if not ok:
        raise result
    return result


def browser_playwright_run(args: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(args)
    session_action = cleaned.get("session_action")
    session_id = cleaned.get("session_id")
    actions = cleaned.get("actions") or []

    # Session mode
    if session_action or session_id:
        action = session_action
        if not action:
            action = "act" if session_id else "start"
        action = str(action)

        if action == "list":
            return list_sessions_payload()
        if action == "start":
            return start_session(cleaned)
        if action == "act":
            return act_session(cleaned)
        if action == "snapshot":
            return snapshot_session(cleaned)
        if action == "close":
            return close_session(cleaned)
        return {
            "ok": False,
            "error": f"Unknown session_action: {action}",
            "code": "invalid_argument",
        }

    # One-shot mode
    if not actions:
        return {
            "ok": False,
            "error": "actions is required for one-shot mode",
            "code": "invalid_argument",
        }

    headless = cleaned.pop("headless", True)
    # remove session-only keys if present
    for k in [
        "session_id",
        "session_action",
        "session_ttl_sec",
        "keep_alive",
        "dialog_policy",
    ]:
        cleaned.pop(k, None)
    cleaned.pop("actions", None)

    return _run_async_blocking(
        lambda: execute_actions(list(actions), headless, **cleaned)
    )


# Alias for tool loader
run_tool = browser_playwright_run
