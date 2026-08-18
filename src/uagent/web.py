from __future__ import annotations

import asyncio
import json
import os
import shutil

from .env_utils import env_get
import re
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

try:
    import uvicorn
    from fastapi import (
        FastAPI,
        File,
        Form,
        Request,
        UploadFile,
        WebSocket,
        WebSocketDisconnect,
    )
    from fastapi.responses import (
        FileResponse,
        HTMLResponse,
        JSONResponse,
        RedirectResponse,
    )
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ImportError:
    from ._pip_auto import install_with_status as _install

    _install("uvicorn")
    _install("fastapi")
    import uvicorn
    from fastapi import (
        FastAPI,
        File,
        Form,
        Request,
        UploadFile,
        WebSocket,
        WebSocketDisconnect,
    )
    from fastapi.responses import (
        FileResponse,
        HTMLResponse,
        JSONResponse,
        RedirectResponse,
    )
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

# uagent module imports
from . import core as core
from .runtime import runtime_init as _runtime_init
from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from . import uagent_llm as llm_util
from .image_session import build_image_session_message
from .llm_helpers import LLMWaitInterrupted
from .providers import util_providers as providers
from . import util_tools as tools_util
from .utils.paths import get_history_file_path
from . import tools

tools.configure_default_confirmation()
from .runtime.logging_setup import log_event
from .runtime.execution import lifecycle_execution
from .tools.pybitchat_shared import forward_to_mesh, is_chat_mode
from .welcome import get_welcome_message
from .gui_ansi import ansi_to_html, wrap_pre

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Drop whole-line and mid-line [STATE] markers (status is sent via type=status).
_STATE_TOKEN_RE = re.compile(r"\[STATE\]\s+\w+(?:\s+\[[^\]]*\])?")


def _strip_state_markers(text: str) -> str:
    """Remove [STATE] ... tokens from log text; return empty if only status noise."""
    if not text or "[STATE]" not in text:
        return text
    cleaned = _STATE_TOKEN_RE.sub("", text)
    # If the line was only status (plus whitespace), drop it entirely.
    if not cleaned.strip():
        return ""
    return cleaned


def _load_input_history() -> list[str]:
    """Load input history from shared CLI history file."""
    try:
        p = get_history_file_path()
        if p.exists():
            result = []
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("+") and len(line) > 1:
                    result.append(line[1:])
            return result
    except Exception:
        pass
    return []


def _save_input_history(text: str) -> None:
    """Append to the shared CLI history file."""
    try:
        t = text.replace("\r", "").strip()
        if not t:
            return
        p = get_history_file_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        # Read existing entries to avoid duplicates
        existing = set()
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("+") and len(line) > 1:
                    existing.add(line[1:])
        if t not in existing:
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"+{t}\n")
    except Exception:
        pass


app = FastAPI(title="uag Web")

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATE_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _enrich_message_attachments(msg: dict[str, Any]) -> dict[str, Any]:
    display_msg = dict(msg or {})

    # Try to extract attachments from tool result JSON content
    attachments = display_msg.get("attachments")
    if not isinstance(attachments, list) or not attachments:
        content = display_msg.get("content", "")
        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    # make_response format: {"ok": ..., "data": {"attachments": [...]}}
                    data = parsed.get("data")
                    if isinstance(data, dict):
                        data_attachments = data.get("attachments")
                        if isinstance(data_attachments, list) and data_attachments:
                            attachments = data_attachments
                            display_msg["attachments"] = attachments
                    # Also check top-level attachments in parsed
                    top_att = parsed.get("attachments")
                    if isinstance(top_att, list) and top_att:
                        attachments = top_att
                        display_msg["attachments"] = attachments
            except (json.JSONDecodeError, TypeError):
                pass

    if isinstance(attachments, list) and attachments:
        enriched = []
        for att in attachments:
            if not isinstance(att, dict):
                enriched.append(att)
                continue
            item = dict(att)
            path = item.get("path") or item.get("saved_path") or item.get("file_path")
            mime = str(item.get("mime") or item.get("type") or "").lower()
            b64 = item.get("data_base64") or item.get("base64")
            if isinstance(b64, str) and b64 and not item.get("data_url"):
                item["data_url"] = (
                    f"data:{mime if mime.startswith('image/') else 'image/png'};base64,{b64}"
                )
            if (
                path
                and not item.get("data_url")
                and (mime.startswith("image/") or mime in ("image", ""))
            ):
                try:
                    item["data_url"] = tools_util.image_file_to_data_url(str(path))
                except Exception:
                    pass
            enriched.append(item)
        display_msg["attachments"] = enriched
        # Simplify content for tool messages with image attachments
        role = display_msg.get("role")
        if role == "tool":
            c = display_msg.get("content", "")
            if isinstance(c, str) and c.strip().startswith("{"):
                try:
                    parsed = json.loads(c)
                    if isinstance(parsed, dict):
                        msg_text = parsed.get("message", "")
                        if msg_text:
                            display_msg["content"] = msg_text
                except (json.JSONDecodeError, TypeError):
                    pass
    return display_msg


class WebRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.base_dir: str = os.getcwd()
        self.lang: str = "en"

        self.active_connections: list[WebSocket] = []
        self.messages: list[dict[str, Any]] = []  # UI display
        self.status: dict[str, Any] = {"busy": False, "label": "IDLE", "workdir": ""}

        # history for LLM
        self.history: list[dict[str, Any]] = []
        self.history_initialized = False
        self.image_session: Optional[dict[str, Any]] = None

        # human_ask sync (room-scoped)
        self.human_ask_sync_event = threading.Event()
        self.human_ask_result = ""
        self.human_ask_is_password = False
        self.human_ask_pending = False
        self.human_ask_message = ""
        self.human_ask_cancelled = False

        # per-room worker serialization (avoid history/tool collisions)
        self.worker_lock = threading.Lock()

        # event loop for run_coroutine_threadsafe
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_base_dir(self, path: str) -> None:
        """Change this room's base directory. Does NOT call os.chdir()."""
        expanded = os.path.expandvars(os.path.expanduser(path))
        resolved = os.path.abspath(expanded)
        if not os.path.isdir(resolved):
            raise NotADirectoryError(f"Not a directory: {resolved}")
        old = self.base_dir
        self.base_dir = resolved
        # Notify connected clients
        try:
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(
                        {
                            "type": "status",
                            "status": {
                                "busy": self.status.get("busy", False),
                                "label": self.status.get("label", "IDLE"),
                                "workdir": resolved,
                            },
                        }
                    ),
                    self.loop,
                )
        except Exception:
            pass
        print(
            _("[cd] workdir changed: %(old)s -> %(new)s")
            % {"old": old, "new": resolved}
        )

    async def connect(self, websocket: WebSocket):
        set_thread_lang(getattr(self, "lang", "en"))
        try:
            await websocket.accept()
            self.active_connections.append(websocket)

            msgs = self.messages
            if self.history:
                try:
                    msgs = []
                    for m in self.history:
                        msgs.append(
                            _enrich_message_attachments(
                                {
                                    "role": m.get("role"),
                                    "content": m.get("content", ""),
                                    "name": m.get("name"),
                                    "tool_calls": m.get("tool_calls"),
                                    "attachments": m.get("attachments"),
                                    "saved_path": m.get("saved_path"),
                                    "saved_files": m.get("saved_files"),
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )
                except Exception:
                    msgs = self.messages

            _v = (env_get("UAGENT_WEB_VERBOSE") or "").strip().lower()
            web_verbose = _v in ("1", "true", "yes", "on")

            # Per-room startup/welcome message (shown once per room)
            # Show it in the chat pane as an assistant message.
            if not getattr(self, "welcome_shown", False):
                try:
                    banner = _runtime_init.build_startup_banner(
                        core=core,
                        workdir=self.base_dir,
                        workdir_source=_("(room: %(id)s)") % {"id": self.room_id[:8]},
                    )
                except Exception:
                    banner = ""

                try:
                    # The browser renders the branded SVG in its header.
                    # Do not send the terminal ASCII masthead as chat content.
                    welcome_text = get_welcome_message(include_ascii=False)
                except Exception:
                    welcome_text = ""

                welcome_msg = welcome_text or ""
                if banner:
                    welcome_msg = welcome_msg + "\n" + banner

                if welcome_msg.strip():
                    welcome_display = _enrich_message_attachments(
                        {"role": "assistant", "content": welcome_msg}
                    )
                    welcome_display["role"] = "assistant"
                    welcome_display["content"] = welcome_msg
                    welcome_display["timestamp"] = datetime.now().isoformat()
                    self.messages.append(welcome_display)
                    msgs = self.messages

                try:
                    setattr(self, "welcome_shown", True)
                except Exception:
                    pass

            # Bootstrap input history from persisted file
            input_history = _load_input_history()
            await websocket.send_json(
                {
                    "type": "init",
                    "messages": msgs,
                    "input_history": input_history,
                    "status": self.status,
                    "modes": {
                        "reasoning": tools_util.get_reasoning_mode(),
                        "verbosity": tools_util.get_verbosity_mode(),
                        "display_reasoning": tools_util.get_display_reasoning(),
                    },
                    "web_verbose": web_verbose,
                    "room_id": self.room_id,
                }
            )
            # Restore pending human_ask modal after reconnect.
            if getattr(self, "human_ask_pending", False):
                try:
                    await websocket.send_json(
                        {
                            "type": "human_ask",
                            "message": getattr(self, "human_ask_message", "") or "",
                            "is_password": bool(
                                getattr(self, "human_ask_is_password", False)
                            ),
                        }
                    )
                except Exception:
                    pass
        finally:
            set_thread_lang(None)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                pass

    def set_status(self, busy: bool, label: str = ""):
        workdir = self.base_dir
        try:
            label = core.normalize_status_label(busy, label)
        except Exception:
            pass

        self.status = {
            "busy": busy,
            "label": label or ("BUSY" if busy else "IDLE"),
            "workdir": workdir,
        }
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "status", "status": self.status}), self.loop
            )

    def add_message(self, msg: dict[str, Any]):
        display_msg = _enrich_message_attachments(msg)
        display_msg["role"] = msg.get("role")
        # Normalize content: list -> plain text for frontend
        raw_content = msg.get("content", "")
        if isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            display_msg["content"] = " ".join(text_parts)
        else:
            display_msg["content"] = raw_content
        display_msg["name"] = msg.get("name")
        display_msg["tool_calls"] = msg.get("tool_calls")
        display_msg["saved_path"] = msg.get("saved_path")
        display_msg["saved_files"] = msg.get("saved_files")
        if msg.get("reasoning_content"):
            display_msg["reasoning_content"] = msg.get("reasoning_content")
        display_msg["timestamp"] = datetime.now().isoformat()
        self.messages.append(display_msg)
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "message", "message": display_msg}), self.loop
            )


class WebManager:
    def __init__(self):
        self.rooms: dict[str, WebRoom] = {}
        self.global_worker_lock = threading.Lock()
        self.rooms_lock = threading.Lock()
        # Room currently executing a worker. Used when thread-local room is
        # missing (e.g. parallel tool pool threads calling set_status).
        self.active_room: WebRoom | None = None
        self.active_room_lock = threading.Lock()

        self.original_log_message = None
        self.original_set_status = None

    def broadcast_all(self, data: dict[str, Any]) -> None:
        # Best-effort broadcast to all active rooms
        try:
            with self.rooms_lock:
                rooms = list(self.rooms.values())
        except Exception:
            rooms = []

        for room in rooms:
            try:
                if room.loop:
                    asyncio.run_coroutine_threadsafe(room.broadcast(data), room.loop)
            except Exception:
                pass

    def get_room(self, room_id: str) -> WebRoom:
        with self.rooms_lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = WebRoom(room_id)
            return self.rooms[room_id]


web_manager = WebManager()


def _broadcast_modes_all() -> None:
    try:
        web_manager.broadcast_all(
            {
                "type": "modes",
                "modes": {
                    "reasoning": tools_util.get_reasoning_mode(),
                    "verbosity": tools_util.get_verbosity_mode(),
                    "display_reasoning": tools_util.get_display_reasoning(),
                },
            }
        )
    except Exception:
        pass


def _handle_mode_command(text: str) -> bool:
    t = (text or "").strip()
    if not t.startswith(":"):
        return False

    body = t.lstrip(":").strip()
    if not body:
        return False

    parts = body.split(maxsplit=1)
    cmd = parts[0].strip().lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("r", "reasoning"):
        try:
            tools_util.apply_reasoning_arg(arg)
            _broadcast_modes_all()
        except Exception:
            pass
        return True

    if cmd in ("v", "verbosity"):
        try:
            tools_util.apply_verbosity_arg(arg)
            _broadcast_modes_all()
        except Exception:
            pass
        return True

    return False


def web_human_ask(room: WebRoom, args: dict[str, Any]) -> str:
    message = args.get("message", "")
    is_password = bool(args.get("is_password", False))
    allow_empty = bool(args.get("allow_empty", False))

    # Fresh event per ask so a stale set() cannot complete immediately.
    sync_event = threading.Event()
    room.human_ask_sync_event = sync_event
    room.human_ask_is_password = is_password
    room.human_ask_message = str(message or "")
    room.human_ask_result = None  # None = no answer yet
    room.human_ask_cancelled = False
    room.human_ask_pending = True
    room.human_ask_allow_empty = allow_empty

    try:
        _web_server_log(
            f"[web-ask] start room={str(room.room_id)[:8]} "
            f"loop={bool(room.loop)} conns={len(room.active_connections)} "
            f"msg_len={len(str(message or ''))}"
        )
    except Exception:
        pass

    # notify only this room (retry a few times; browser may still be mounting)
    sent = False
    if room.loop:
        payload = {
            "type": "human_ask",
            "message": str(message or ""),
            "is_password": is_password,
        }
        for attempt in range(5):
            try:
                # Also surface in chat so the user notices even if modal CSS fails.
                if attempt == 0:
                    try:
                        room.add_message(
                            {
                                "role": "assistant",
                                "content": str(message or ""),
                            }
                        )
                    except Exception:
                        pass
                fut = asyncio.run_coroutine_threadsafe(
                    room.broadcast(payload),
                    room.loop,
                )
                fut.result(timeout=2.0)
                sent = True
                try:
                    _web_server_log(
                        f"[web-ask] broadcast ok room={str(room.room_id)[:8]} "
                        f"attempt={attempt+1} conns={len(room.active_connections)}"
                    )
                except Exception:
                    pass
                break
            except Exception as e:
                try:
                    _web_server_log(
                        f"[web-ask] broadcast retry room={str(room.room_id)[:8]} "
                        f"attempt={attempt+1} err={e!r}"
                    )
                except Exception:
                    pass
                time.sleep(0.2)
        if not sent:
            try:
                _web_server_log(
                    f"[web-ask] broadcast failed room={str(room.room_id)[:8]}"
                )
            except Exception:
                pass
    else:
        try:
            _web_server_log("[web-ask] no room.loop; client will not see modal")
        except Exception:
            pass

    cancelled = False
    try:
        # Poll so Stop/interrupt can unblock without a reply.
        while True:
            if sync_event.wait(0.2):
                # Answer or cancel signaled.
                if getattr(room, "human_ask_cancelled", False):
                    cancelled = True
                    break
                result = room.human_ask_result
                if result is None:
                    # Spurious wake; keep waiting.
                    sync_event.clear()
                    continue
                if (not allow_empty) and str(result).strip() == "":
                    # Empty submit is ignored (common UI accident).
                    try:
                        _web_server_log(
                            f"[web-ask] ignore empty reply room={str(room.room_id)[:8]}"
                        )
                    except Exception:
                        pass
                    room.human_ask_result = None
                    sync_event.clear()
                    # Re-show modal in case UI closed itself.
                    if room.loop:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                room.broadcast(
                                    {
                                        "type": "human_ask",
                                        "message": message,
                                        "is_password": is_password,
                                    }
                                ),
                                room.loop,
                            )
                        except Exception:
                            pass
                    continue
                break
            try:
                with core.interrupt_lock:
                    if core.interrupt_requested:
                        cancelled = True
                        room.human_ask_cancelled = True
                        room.human_ask_result = ""
                        break
            except Exception:
                pass
            if getattr(room, "human_ask_cancelled", False):
                cancelled = True
                room.human_ask_result = ""
                break
            if not room.active_connections:
                # Browser gone; do not hang the worker forever.
                cancelled = True
                room.human_ask_cancelled = True
                room.human_ask_result = ""
                try:
                    _web_server_log(
                        f"[web-ask] no connections; cancel room={str(room.room_id)[:8]}"
                    )
                except Exception:
                    pass
                break
    finally:
        room.human_ask_pending = False

    if getattr(room, "human_ask_cancelled", False):
        cancelled = True

    user_reply = "" if cancelled else str(room.human_ask_result or "")
    display_reply = "[SECRET]" if is_password else user_reply

    try:
        _web_server_log(
            f"[web-ask] end room={str(room.room_id)[:8]} "
            f"cancelled={cancelled} reply_len={len(user_reply)}"
        )
    except Exception:
        pass

    return json.dumps(
        {
            "user_reply": user_reply,
            "display_reply": display_reply,
            "cancelled": cancelled,
        }
    )


def web_set_status(busy: bool, label: str = ""):
    # Keep original behavior for CLI/server console (if any)
    if web_manager.original_set_status:
        web_manager.original_set_status(busy, label)

    # Web UI: prefer thread-local room; fall back to active worker room so
    # parallel tool threads still update the correct room status.
    room = None
    try:
        room = getattr(_thread_ctx, "room", None)
    except Exception:
        room = None
    if room is None:
        try:
            with web_manager.active_room_lock:
                room = web_manager.active_room
        except Exception:
            room = None

    if room is not None:
        try:
            room.set_status(busy, label)
        except Exception:
            pass

    return


def _web_console_log_enabled() -> bool:
    """Mirror captured stdout/stderr to the real server console.

    Default OFF. Set UAGENT_WEB_CONSOLE_LOG=1 to enable.
    """
    v = (env_get("UAGENT_WEB_CONSOLE_LOG") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _web_debug_enabled() -> bool:
    """Lifecycle/debug lines ([web-ask], [web-init], ...).

    Default OFF. Set UAGENT_WEB_DEBUG=1 (or UAGENT_WEB_CONSOLE_LOG=1) to enable.
    """
    v = (env_get("UAGENT_WEB_DEBUG") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return _web_console_log_enabled()


def _web_server_log(msg: str) -> None:
    """Write a compact line to the real server console when debug is on."""
    if not _web_debug_enabled():
        return
    try:
        line = str(msg or "").rstrip() + chr(10)
        sys.__stderr__.write(line)
        sys.__stderr__.flush()
    except Exception:
        try:
            sys.__stdout__.write(str(msg or "").rstrip() + chr(10))
            sys.__stdout__.flush()
        except Exception:
            pass


def _lang_from_accept_language(v: str | None) -> str:
    """Parse Accept-Language and return 'ja' or 'en'.

    Web policy (B): browser language is authoritative.
    """
    if not v:
        return "en"
    s = str(v)
    # Simple parse: split by comma, take primary tags, keep order
    parts: list[str] = []
    for item in s.split(","):
        item = item.strip()
        if not item:
            continue
        tag = item.split(";", 1)[0].strip().lower()
        if tag:
            parts.append(tag)
    for tag in parts:
        if tag.startswith("ja"):
            return "ja"
    return "en"


class WebStdout:
    """Capture stdout and stream it to the *currently running room*.

    NOTE: This is inherently process-global. We only stream logs during a worker run,
    by setting a thread-local 'room' (see _thread_ctx).
    """

    def __init__(self):
        self.buffer = ""
        self.lock = threading.Lock()

    def write(self, text):
        if _web_console_log_enabled():
            sys.__stdout__.write(text)

        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = ANSI_ESCAPE.sub("", line)
                content_html = wrap_pre(ansi_to_html(line))

                # Suppress CLI-only multiline input mode guidance in Web UI
                if "multiline" in (clean_line or "").lower():
                    continue
                # Status is delivered via type=status; drop [STATE] log noise
                # (including mid-line injections mixed into assistant/tool text).
                clean_line = _strip_state_markers(clean_line or "")
                if not clean_line.strip():
                    continue

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast(
                            {
                                "type": "log",
                                "content": clean_line,
                                "content_html": content_html,
                            }
                        ),
                        room.loop,
                    )

    def flush(self):
        with self.lock:
            if self.buffer:
                clean_line = ANSI_ESCAPE.sub("", self.buffer)
                content_html = wrap_pre(ansi_to_html(self.buffer))
                try:
                    filtered_lines: list[str] = []
                    for ln in clean_line.splitlines():
                        if "multiline" in (ln or "").lower():
                            continue
                        ln2 = _strip_state_markers(ln or "")
                        if not ln2.strip():
                            continue
                        filtered_lines.append(ln2)
                    clean_line = "\n".join(filtered_lines)
                except Exception:
                    pass

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast(
                            {
                                "type": "log",
                                "content": clean_line,
                                "content_html": content_html,
                            }
                        ),
                        room.loop,
                    )
                self.buffer = ""

        if _web_console_log_enabled():
            sys.__stdout__.flush()

    def isatty(self):
        return sys.__stdout__.isatty()


class WebStderr(WebStdout):
    def write(self, text):
        if _web_console_log_enabled():
            sys.__stderr__.write(text)

        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = ANSI_ESCAPE.sub("", line)
                content_html = wrap_pre(ansi_to_html(line))
                if "multiline" in (clean_line or "").lower():
                    continue
                clean_line = _strip_state_markers(clean_line or "")
                if not clean_line.strip():
                    continue

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast(
                            {
                                "type": "log",
                                "content": clean_line,
                                "content_html": content_html,
                            }
                        ),
                        room.loop,
                    )

    def flush(self):
        super().flush()
        if _web_console_log_enabled():
            sys.__stderr__.flush()

    def isatty(self):
        return sys.__stderr__.isatty()


_thread_ctx = threading.local()

sys.stdout = WebStdout()
sys.stderr = WebStderr()


def _ensure_room_history_initialized(room: WebRoom) -> None:
    """Initialize room.history once (system prompt, AGENTS.md prompt, memory).

    Safe to call from connect-time bootstrap or the first worker turn.
    Web instruction selection uses human_ask and therefore requires room.loop
    plus thread-local/active room binding.
    """
    if getattr(room, "history_initialized", False):
        return

    # Bind room context so human_ask / status updates reach this room.
    prev_room = getattr(_thread_ctx, "room", None)
    _thread_ctx.room = room
    prev_active = None
    try:
        with web_manager.active_room_lock:
            prev_active = web_manager.active_room
            web_manager.active_room = room
    except Exception:
        prev_active = None

    _orig_cwd = os.getcwd()
    try:
        try:
            os.chdir(room.base_dir)
        except Exception:
            pass
        try:
            set_thread_lang(getattr(room, "lang", "en"))
        except Exception:
            pass
        try:
            setattr(core, "_is_web", True)
        except Exception:
            pass

        try:
            _web_server_log(f"[web-init] history start room={str(room.room_id)[:8]}")
        except Exception:
            pass

        # Keep UI responsive indicator while prompting.
        try:
            room.set_status(True, "INIT")
            if web_manager.original_set_status:
                web_manager.original_set_status(True, "INIT")
        except Exception:
            pass

        room.history = tools_util.build_initial_messages(core=core)
        room.history_initialized = True

        # Surface instruction-load result in the Web chat (print alone is console-only).
        # Prefer session-tracked paths (I18N-safe) over parsing translated headers.
        try:
            from .runtime.runtime_instructions import (
                _find_instruction_files,
                get_loaded_instruction_paths,
            )

            loaded_abs = get_loaded_instruction_paths()
            loaded_files: list[str] = []
            base = os.path.abspath(room.base_dir or ".")
            for p in loaded_abs:
                try:
                    loaded_files.append(os.path.relpath(p, base))
                except Exception:
                    loaded_files.append(os.path.basename(p) or p)
            if loaded_files:
                lines = [
                    _("[INFO] Loading %(n)d project instruction file(s).")
                    % {"n": len(loaded_files)}
                ]
                for rel in loaded_files:
                    lines.append(f"  - {rel}")
                room.add_message({"role": "assistant", "content": chr(10).join(lines)})
            else:
                # Distinguish "none found" vs "user skipped";
                # only show skip notice when AGENTS/CLAUDE exists in workdir tree.
                try:
                    cands = _find_instruction_files(room.base_dir)
                except Exception:
                    cands = []
                if cands:
                    room.add_message(
                        {
                            "role": "assistant",
                            "content": _(
                                "[INFO] No project instruction files selected."
                            ),
                        }
                    )
        except Exception:
            pass

        # Surface enabled-plugins status in Web chat (print alone is console-only).
        # Format here so room locale (set_thread_lang) is applied.
        try:
            if not getattr(room, "_plugins_status_shown", False):
                from .runtime.runtime_plugins import format_enabled_plugins_status

                _plugins_line = format_enabled_plugins_status(
                    getattr(web_manager, "plugins_startup_list", None) or []
                )
                if _plugins_line:
                    room.add_message({"role": "assistant", "content": _plugins_line})
                try:
                    setattr(room, "_plugins_status_shown", True)
                except Exception:
                    pass
        except Exception:
            pass

        # Apply SessionStart hook stdout stashed at server boot (if any)
        try:
            from .hooks_engine import inject_pending_session_hook_context

            inject_pending_session_hook_context(room.history)
        except Exception:
            pass

        # Long-term memory insertion (align with CLI/GUI)
        from .tools import long_memory as personal_long_memory
        from .tools import shared_memory

        print(_("[INFO] Loaded long-term memory."))
        try:
            room.add_message(
                {
                    "role": "assistant",
                    "content": _("[INFO] Loaded long-term memory."),
                }
            )
        except Exception:
            pass
        try:
            before_len = len(room.history)
            flags = _runtime_init.append_long_memory_system_messages(
                core=core,
                messages=room.history,
                build_long_memory_system_message_fn=tools_util.build_long_memory_system_message,
                personal_long_memory_mod=personal_long_memory,
                shared_memory_mod=shared_memory,
            )

            if flags.get("shared_enabled"):
                print(_("[INFO] Loaded shared long-term memory."))
                try:
                    room.add_message(
                        {
                            "role": "assistant",
                            "content": _("[INFO] Loaded shared long-term memory."),
                        }
                    )
                except Exception:
                    pass

            for m in room.history[before_len:]:
                core.log_message(m)

        except Exception as e:
            print(
                _(
                    "[WARN] Exception occurred while loading shared long-term memory: %(err)s"
                )
                % {"err": e}
            )

        try:
            _web_server_log(
                f"[web-init] history done room={str(room.room_id)[:8]} msgs={len(room.history)}"
            )
        except Exception:
            pass
    finally:
        try:
            room.set_status(False, "IDLE")
            if web_manager.original_set_status:
                web_manager.original_set_status(False, "")
        except Exception:
            pass
        try:
            os.chdir(_orig_cwd)
        except Exception:
            pass
        try:
            with web_manager.active_room_lock:
                if web_manager.active_room is room:
                    web_manager.active_room = prev_active
        except Exception:
            pass
        try:
            _thread_ctx.room = prev_room
        except Exception:
            pass
        try:
            set_thread_lang(None)
        except Exception:
            pass


def _bootstrap_room_on_connect(room: WebRoom) -> None:
    """Run once after first websocket connect so AGENTS.md is asked immediately."""
    if getattr(room, "history_initialized", False):
        return
    if getattr(room, "_bootstrap_started", False):
        return
    try:
        setattr(room, "_bootstrap_started", True)
    except Exception:
        pass

    def _runner() -> None:
        try:
            # Wait briefly for room.loop assignment from websocket endpoint.
            for _ in range(50):
                if getattr(room, "loop", None) is not None:
                    break
                time.sleep(0.02)
            # Give the browser time to process the init frame and mount Svelte
            # before the human_ask modal arrives.
            time.sleep(0.6)
            if getattr(room, "history_initialized", False):
                return
            # Wait until at least one websocket is actually connected.
            for _ in range(50):
                if room.active_connections:
                    break
                time.sleep(0.05)
            if not room.active_connections:
                # Client already gone; skip prompt.
                return
            _ensure_room_history_initialized(room)
        except Exception as e:
            try:
                _web_server_log(
                    f"[web-init] bootstrap error room={str(getattr(room, 'room_id', ''))[:8]} err={e!r}"
                )
            except Exception:
                pass

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"uagent-web-init-{str(getattr(room, 'room_id', ''))[:8]}",
    ).start()


def run_agent_worker(
    room: WebRoom,
    user_input: str,
    attachments: Optional[list[dict[str, Any]]] = None,
):
    """Run one user turn for a room.

    Lock/status contract:
    - room.worker_lock: per-room serialization (non-blocking acquire)
    - global_worker_lock: process-wide cwd/tool safety
    - room status BUSY is set only after both locks are held
    - finally always clears room/core status and releases locks
    """
    # Ensure logs/status go to this room (thread-local). Parallel tool workers
    # inherit room via tools.run_tool wrapper (see init_web).
    _thread_ctx.room = room
    set_thread_lang(getattr(room, "lang", "en"))
    log_event(
        "web.room.task.started",
        room_id=getattr(room, "room_id", ""),
        locale=getattr(room, "lang", "en"),
    )

    # Serialize per-room runs to avoid history/tool collisions
    if not room.worker_lock.acquire(blocking=False):
        room.add_message(
            {
                "role": "assistant",
                "content": _(
                    "[WARN] Another task is already running in this room. Please retry after it completes."
                ),
            }
        )
        try:
            set_thread_lang(None)
        except Exception:
            pass
        _thread_ctx.room = None
        return

    acquired_global = False
    _orig_cwd = os.getcwd()
    _orig_log_message = getattr(core, "log_message", None)

    try:
        # Switch to this room's base_dir for the duration of the worker
        try:
            os.chdir(room.base_dir)
        except Exception:
            pass

        # Acquire global lock BEFORE marking BUSY so a blocked waiter never
        # appears BUSY while still queued on the lock.
        web_manager.global_worker_lock.acquire()
        acquired_global = True

        with web_manager.active_room_lock:
            web_manager.active_room = room

        # Suppress CLI [STATE] before first status update (Windows WriteConsoleW
        # bypasses sys.stderr redirection and leaks to the server console).
        try:
            setattr(core, "_is_web", True)
        except Exception:
            pass

        room.set_status(True, "BUSY")
        try:
            # Keep core.status_busy in sync for interrupt / genre guards.
            # Call original directly to avoid recursive room.set_status.
            if web_manager.original_set_status:
                web_manager.original_set_status(True, "BUSY")
            else:
                core.status_busy = True
                core.status_label = "BUSY"
        except Exception:
            pass
        try:
            _web_server_log(
                f"[web-worker] start room={str(room.room_id)[:8]} busy=1 label=BUSY"
            )
        except Exception:
            pass

        # Streaming helpers for Web UI
        stream_state: dict[str, Any] = {
            "id": None,
            "active": False,
            "suppress_next_assistant_message": False,
        }

        def _web_stream_send(payload: dict[str, Any]) -> None:
            try:
                if room.loop:
                    asyncio.run_coroutine_threadsafe(room.broadcast(payload), room.loop)
            except Exception:
                pass

        def _stream_start() -> str:
            sid = f"asst_{int(time.time() * 1000)}"
            stream_state["id"] = sid
            stream_state["active"] = True
            stream_state["suppress_next_assistant_message"] = True
            _web_stream_send({"type": "assistant_stream_start", "id": sid})
            return sid

        def _stream_delta(delta: str, *, reasoning: bool = False) -> None:
            if not delta:
                return
            if not stream_state.get("active"):
                _stream_start()
            if reasoning:
                _web_stream_send({"type": "reasoning", "content": delta})
            else:
                _web_stream_send(
                    {
                        "type": "assistant_stream_delta",
                        "id": stream_state.get("id"),
                        "delta": delta,
                    }
                )

        def _stream_end() -> None:
            if stream_state.get("active"):
                _web_stream_send(
                    {"type": "assistant_stream_end", "id": stream_state.get("id")}
                )
            stream_state["active"] = False
            stream_state["suppress_next_assistant_message"] = False

        # Patch core.log_message during this worker run so streaming deltas can go to WebSocket.
        _orig_log_message = getattr(core, "log_message", None)

        def _patched_log_message(msg: dict[str, Any]) -> None:
            try:
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_reasoning_delta"
                ):
                    _stream_delta(str(msg.get("delta") or ""), reasoning=True)
                    return
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_stream_delta"
                ):
                    _stream_delta(str(msg.get("delta") or ""))
                    return
                if isinstance(msg, dict) and msg.get("type") == "assistant_stream_end":
                    _stream_end()
                    return
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_stream_interrupted"
                ):
                    _stream_end()
                    return
            except Exception:
                pass
            if callable(_orig_log_message):
                try:
                    _orig_log_message(msg)
                except Exception:
                    pass
            try:
                if isinstance(msg, dict):
                    role = msg.get("role")
                    # UI-only assistant (e.g. empty-no-tool WARN) must be visible in Web,
                    # but must not enter room.history (model prompt).
                    if role == "assistant" and msg.get("_uagent_ui_only"):
                        room.add_message(dict(msg))
                    elif role in ("user", "tool") and not msg.get("_uagent_internal"):
                        room.add_message(dict(msg))
            except Exception:
                pass

        try:
            if callable(_orig_log_message):
                setattr(core, "log_message", _patched_log_message)
        except Exception:
            pass

        try:
            if not (env_get("UAGENT_PROVIDER") or "").strip():
                room.add_message(
                    {
                        "role": "assistant",
                        "content": _(
                            "[FATAL] Environment variable UAGENT_PROVIDER is not set.\nPlease check environment variables when starting the web server."
                        ),
                    }
                )
                return

            provider_name, client, depname = providers.make_client(core)

            user_input = str(user_input or "")
            attachment_lines: list[str] = []
            clean_attachments: list[dict[str, Any]] = []
            for att in attachments or []:
                if not isinstance(att, dict):
                    continue
                item = dict(att)
                path = str(
                    item.get("saved_path")
                    or item.get("path")
                    or item.get("file_path")
                    or ""
                ).strip()
                if not path:
                    continue
                name = str(item.get("name") or os.path.basename(path) or path).strip()
                mime = (
                    str(
                        item.get("mime")
                        or item.get("content_type")
                        or item.get("type")
                        or ""
                    )
                    .lower()
                    .strip()
                )
                is_image = mime.startswith("image/") or mime == "image"
                is_video = (
                    mime.startswith("video/") and os.path.getsize(path) <= 50_000_000
                )
                label = os.path.basename(name) or os.path.basename(path) or path
                if is_image:
                    attachment_lines.append(
                        _("[Attached Image] %(name)s") % {"name": label}
                    )
                    attachment_lines.append(_("[Image Path] %(path)s") % {"path": path})
                    item["type"] = "image"
                else:
                    attachment_lines.append(
                        _("[Attached File] %(name)s") % {"name": label}
                    )
                    attachment_lines.append(_("[File Path] %(path)s") % {"path": path})
                    item["type"] = "file"
                item["saved_path"] = path
                if mime:
                    item["mime"] = mime
                # Ensure data_url is set for images if missing
                if is_image and not item.get("data_url"):
                    try:
                        item["data_url"] = tools_util.image_file_to_data_url(path)
                    except Exception:
                        pass
                if is_video and not item.get("data_url"):
                    try:
                        item["data_url"] = tools_util.media_file_to_data_url(
                            path, max_bytes=50_000_000
                        )
                    except Exception:
                        item["type"] = "file"
                clean_attachments.append(item)

            # Build multimodal content for images and guarded llama.cpp videos.
            has_image = any(
                att.get("type") == "image" for att in (clean_attachments or [])
            )
            has_video = provider_name == "llama_cpp" and any(
                att.get("type") == "video" and att.get("data_url")
                for att in (clean_attachments or [])
            )
            if has_image or has_video:
                # Use multimodal format (Chat Completions standard image_url)
                parts: list[dict[str, Any]] = (
                    [{"type": "text", "text": user_input}] if user_input.strip() else []
                )
                for att in clean_attachments or []:
                    data_url = att.get("data_url")
                    if data_url and att.get("type") == "image":
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            }
                        )
                    elif (
                        data_url
                        and att.get("type") == "video"
                        and provider_name == "llama_cpp"
                    ):
                        parts.append(
                            {
                                "type": "input_video",
                                "input_video": {"url": data_url},
                            }
                        )
                user_msg = {"role": "user", "content": parts}
            else:
                # Fallback: text-only with attachment lines
                prompt_text = user_input
                if attachment_lines:
                    prompt_text = (
                        (prompt_text.rstrip() + "\n\n") if prompt_text.strip() else ""
                    ) + "\n".join(attachment_lines)
                user_msg = {"role": "user", "content": prompt_text}

            if clean_attachments:
                user_msg["attachments"] = clean_attachments
            core.log_message(user_msg)

            # History/instructions may already be initialized on websocket connect.
            _ensure_room_history_initialized(room)

            # UserPromptSubmit: stdin JSON + optional block (skip LLM turn)
            try:
                from .hooks_engine import (
                    fire_user_prompt_submit,
                    inject_hook_context,
                    collect_hook_block_decision,
                )

                _ups_results = fire_user_prompt_submit(user_input)
                _ups_block = collect_hook_block_decision(_ups_results)
                if _ups_block is not None:
                    _reason = (_ups_block.get("reason") or "").strip()
                    if not _reason:
                        _reason = "Blocked by UserPromptSubmit hook."
                    room.add_message({"role": "assistant", "content": _reason})
                    return
                inject_hook_context(
                    room.history,
                    _ups_results,
                    event_name="UserPromptSubmit",
                    replace_event=True,
                )
            except Exception:
                pass

            # Strip attachments from user_msg before saving to history to avoid
            # accumulating large data_urls that cause API context overflow on subsequent turns.
            history_msg = dict(user_msg)
            history_msg.pop("attachments", None)
            room.history.append(history_msg)
            _save_input_history(user_input)
            room.image_session = build_image_session_message(room.history, depname)

            # Inject Generative UI instructions into the system prompt for Web mode
            generative_ui_prompt = _("""

    ## Generative UI (Artifacts) Instructions
    When the user asks for a UI, dashboard, interactive tool, or visualization:
    1. Write a complete, self-contained HTML page inside a single ```html code block.
    2. Use Tailwind CSS (via CDN: <script src="https://cdn.tailwindcss.com"></script>) for styling and Lucide Icons or FontAwesome for icons.
    3. Include interactive JavaScript (e.g., Chart.js for charts, or simple state management).
    4. Do not split the code into multiple blocks; keep it in one unified ```html block.
    """)
            if room.history and room.history[0].get("role") == "system":
                sys_content = room.history[0].get("content") or ""
                if "Generative UI (Artifacts) Instructions" not in sys_content:
                    room.history[0]["content"] = sys_content + generative_ui_prompt
            else:
                room.history.insert(
                    0, {"role": "system", "content": generative_ui_prompt.strip()}
                )

            # Track history length before LLM round to sync new messages to room after
            _before_hist_len = len(room.history)

            def _on_lifecycle(snapshot) -> None:
                payload = {
                    "type": "lifecycle",
                    "status": snapshot.status.value,
                    "updated_at": snapshot.updated_at,
                }
                _web_stream_send(payload)
                try:
                    room.set_status(
                        snapshot.status.value
                        not in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"},
                        snapshot.status.value,
                    )
                except Exception:
                    pass

            with lifecycle_execution(
                cancel_exceptions=(LLMWaitInterrupted,),
                on_transition=_on_lifecycle,
            ) as lifecycle:
                try:
                    room.agent_lifecycle = lifecycle
                except Exception:
                    pass
                llm_util.run_llm_rounds(
                    provider_name,
                    client,
                    depname,
                    room.history,
                    core=core,
                    make_client_fn=providers.make_client,
                    append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                    try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                )
                # Auto-pilot loop
                if core.auto_pilot_active:
                    tools_util._run_auto_pilot_loop(
                        provider_name,
                        client,
                        depname,
                        room.history,
                        core=core,
                        make_client_fn=providers.make_client,
                        append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                        try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                    )
            # Sync new assistant messages missed due to skip_log_when_web in _append_assistant_message.
            for m in room.history[_before_hist_len:]:
                if isinstance(m, dict) and m.get("role") == "assistant":
                    room.add_message(dict(m))

        except LLMWaitInterrupted:
            # Clean Stop during blocking LLM wait: no FATAL banner.
            try:
                with core.interrupt_lock:
                    core.interrupt_requested = False
            except Exception:
                pass
            try:
                room.add_message(
                    {
                        "role": "assistant",
                        "content": "[INTERRUPT] Stopped by user.",
                    }
                )
            except Exception:
                pass
        except BaseException as e:
            err = repr(e)
            tb = ""
            try:
                tb = traceback.format_exc()
            except Exception:
                tb = ""

            msg = _("[FATAL] Web worker error.\n%(err)s") % {"err": err}
            if (
                isinstance(e, (SystemExit, ValueError))
                and not (env_get("UAGENT_PROVIDER") or "").strip()
            ):
                msg = _(
                    "[FATAL] Environment variable UAGENT_PROVIDER is not set.\nPlease check environment variables when starting the web server."
                )
            if tb and tb != "NoneType: None\n":
                msg = msg + "\n\n" + tb

            room.add_message({"role": "assistant", "content": msg})

    finally:
        log_event("web.room.task.completed", room_id=getattr(room, "room_id", ""))
        # Best-effort cleanup; never let one failure skip lock release / IDLE.
        try:
            if callable(_orig_log_message):
                setattr(core, "log_message", _orig_log_message)
        except Exception:
            pass

        try:
            room.set_status(False, "IDLE")
        except Exception:
            pass
        try:
            _web_server_log(
                f"[web-worker] end room={str(room.room_id)[:8]} busy=0 label=IDLE"
            )
        except Exception:
            pass

        # Always clear core busy even if room broadcast failed.
        # Call original directly (not core.set_status=web_set_status) to avoid
        # re-broadcast races after active_room is cleared.
        try:
            if web_manager.original_set_status:
                web_manager.original_set_status(False, "")
            else:
                core.status_busy = False
                core.status_label = ""
        except Exception:
            try:
                core.status_busy = False
                core.status_label = ""
            except Exception:
                pass

        # Unblock any leftover human_ask waiter for this room.
        try:
            room.human_ask_pending = False
            room.human_ask_cancelled = True
            room.human_ask_sync_event.set()
        except Exception:
            pass

        # End any open assistant stream so the UI does not stay mid-stream.
        try:
            _stream_end()
        except Exception:
            pass

        try:
            with web_manager.active_room_lock:
                if web_manager.active_room is room:
                    web_manager.active_room = None
        except Exception:
            pass

        try:
            os.chdir(_orig_cwd)
        except Exception:
            pass

        if acquired_global:
            try:
                web_manager.global_worker_lock.release()
            except Exception:
                pass

        try:
            room.worker_lock.release()
        except Exception:
            pass

        try:
            set_thread_lang(None)
        except Exception:
            pass

        _thread_ctx.room = None


@app.get("/")
async def get_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # Fallback: create room and redirect (legacy template)
    room_id = uuid4().hex
    return RedirectResponse(url=f"/room/{room_id}")


@app.get("/room/{room_id}")
async def get_room(room_id: str):
    # Ensure room exists
    web_manager.get_room(room_id)
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("Room created. SPA not built.", status_code=200)


@app.post("/upload")
async def upload_files(
    room: str = Form(""),
    files: list[UploadFile] = File(...),
):
    try:
        raw_room_id = (
            re.sub(r"[^A-Za-z0-9._-]+", "_", str(room or "").strip()) or "default"
        )
        room_obj = web_manager.get_room(raw_room_id)
        base = os.path.abspath(room_obj.base_dir)
        upload_root = os.path.join(base, ".uagent_web_uploads", raw_room_id)
        os.makedirs(upload_root, exist_ok=True)

        saved: list[dict[str, Any]] = []
        for upload in files or []:
            if upload is None:
                continue
            original_name = os.path.basename(
                str(getattr(upload, "filename", "") or "upload")
            )
            safe_name = (
                re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._") or "upload"
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dst_path = os.path.join(upload_root, f"{stamp}_{safe_name}")
            with open(dst_path, "wb") as out_f:
                shutil.copyfileobj(upload.file, out_f)

            mime = str(getattr(upload, "content_type", "") or "").lower().strip()
            is_image = mime.startswith("image/")
            is_video = (
                mime.startswith("video/") and os.path.getsize(dst_path) <= 50_000_000
            )
            item: dict[str, Any] = {
                "name": original_name,
                "saved_path": dst_path,
                "path": dst_path,
                "mime": mime,
                "type": "image" if is_image else ("video" if is_video else "file"),
            }
            if is_image:
                try:
                    item["data_url"] = tools_util.image_file_to_data_url(dst_path)
                except Exception:
                    pass
            saved.append(item)

        return {"ok": True, "files": saved}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


@app.get("/local-file")
async def get_local_file(path: str, room_id: str = ""):
    try:
        raw_room_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(room_id or "").strip())
        if raw_room_id:
            room_obj = web_manager.get_room(raw_room_id)
            base_dir = os.path.abspath(room_obj.base_dir)
        else:
            base_dir = os.path.abspath(os.getcwd())
        raw = str(path or "").strip()
        if not raw:
            raise ValueError(_("missing path"))
        full = os.path.abspath(raw)
        if not os.path.isabs(raw):
            full = os.path.abspath(os.path.join(base_dir, raw))
        full_norm = os.path.normpath(full)
        base_norm = os.path.normpath(base_dir)
        if not (full_norm == base_norm or full_norm.startswith(base_norm + os.sep)):
            raise ValueError(_("path outside workdir"))
        if not os.path.isfile(full_norm):
            raise FileNotFoundError(full_norm)
        return FileResponse(full_norm)
    except Exception:
        raise


# Tool genre state (initially all disabled; toggled via API)
_genre_enabled: dict[str, bool] = {}


@app.get("/api/tool-genres")
async def get_tool_genres():
    """Return list of available genres and their current enabled state."""
    return {
        "genres": [
            {
                "key": "basic",
                "label": _("Basic (env, time, prompts, skills, memory, tools control)"),
                "enabled": _genre_enabled.get("basic", False),
            },
            {
                "key": "file",
                "label": _(
                    "File (create, delete, read, write, search, zip, rename, hash, grep, list dir)"
                ),
                "enabled": _genre_enabled.get("file", False),
            },
            {
                "key": "comm",
                "label": _("Communication (Teams, Discord, Bluesky)"),
                "enabled": _genre_enabled.get("comm", False),
            },
            {
                "key": "office",
                "label": _("Office (Excel, Word, PDF, PPT, document extraction)"),
                "enabled": _genre_enabled.get("office", False),
            },
            {
                "key": "devel",
                "label": _(
                    "Development (lint, test, git, DB, screenshot, browser, binary, compile)"
                ),
                "enabled": _genre_enabled.get("devel", False),
            },
            {
                "key": "iot",
                "label": _(
                    "IoT (Bluetooth/BLE, ECHONET, Matter, SwitchBot, UPnP, camera, geo-IP)"
                ),
                "enabled": _genre_enabled.get("iot", False),
            },
            {
                "key": "exec",
                "label": _("Execution (cmd, python, pwsh, bash, sub-agent)"),
                "enabled": _genre_enabled.get("exec", False),
            },
            {
                "key": "external",
                "label": _("External (A2A, MCP, fetch, search web)"),
                "enabled": _genre_enabled.get("external", False),
            },
            {
                "key": "media",
                "label": _("Media (image gen/edit/analyze, audio, QR code)"),
                "enabled": _genre_enabled.get("media", False),
            },
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
    from .tools.genre_control_tool import (
        _set_basic_tools_enabled,
        _set_comm_tools_enabled,
        _set_devel_tools_enabled,
        _set_exec_tools_enabled,
        _set_external_tools_enabled,
        _set_file_tools_enabled,
        _set_index_tools_enabled,
        _set_iot_tools_enabled,
        _set_media_tools_enabled,
        _set_office_tools_enabled,
    )

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

    setters = {
        "basic": _set_basic_tools_enabled,
        "comm": _set_comm_tools_enabled,
        "office": _set_office_tools_enabled,
        "devel": _set_devel_tools_enabled,
        "iot": _set_iot_tools_enabled,
        "exec": _set_exec_tools_enabled,
        "external": _set_external_tools_enabled,
        "media": _set_media_tools_enabled,
        "file": _set_file_tools_enabled,
        "index": _set_index_tools_enabled,
    }

    setter = setters.get(genre)
    if not setter:
        return JSONResponse(
            status_code=400, content={"error": f"Unknown genre: {genre}"}
        )

    try:
        msg = setter(enabled)
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


# ---- Memories API ----
from .tools import long_memory as _long_memory_mod


@app.get("/api/memories")
async def get_memories():
    """Return all long-term memory entries as structured JSON."""
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
    body = await req.json()
    note = str(body.get("note", "")).strip()
    if not note:
        return JSONResponse(status_code=400, content={"error": "note is required"})
    _long_memory_mod.append_long_memory(note)
    return {"ok": True}


@app.put("/api/memories/{index}")
async def update_memory(index: int, req: Request):
    """Update a long-term memory entry in-place (preserves order)."""
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
async def delete_memory(index: int):
    """Delete a long-term memory entry."""
    ok = _long_memory_mod.delete_long_memory_entry(index)
    if not ok:
        return JSONResponse(
            status_code=404, content={"error": f"index {index} out of range"}
        )
    return {"ok": True}


# ---- Profile API ----
from . import profile_manager as _profile_mod


@app.get("/api/profile")
async def get_profile():
    """Return current profile data."""
    profile = _profile_mod.load_profile()
    return {"ok": True, "profile": profile}


@app.post("/api/profile/clear")
async def clear_profile():
    """Clear profile file."""
    try:
        path = _profile_mod.get_profile_file_path()
        if os.path.exists(path):
            os.remove(path)
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/profile/fromlog")
async def profile_from_logs():
    """Rebuild profile from past logs."""
    from . import core as _core_mod

    result = _profile_mod.profile_from_logs(_core_mod, max_log_files=100)
    if result:
        return {"ok": True, "profile": result}
    return {"ok": False, "error": "Failed to build profile from logs"}


@app.put("/api/profile")
async def update_profile(req: Request):
    """Update profile in-place. Body: {"environment": {...}, "preferences": [...], "constraints": [...]}"""
    body = await req.json()
    current = _profile_mod.load_profile()
    # Merge: only update provided keys
    for key in ("environment", "preferences", "constraints"):
        if key in body:
            current[key] = body[key]
    _profile_mod.save_profile(current)
    return {"ok": True, "profile": current}


# ---- Logs API ----
@app.get("/api/logs")
async def get_logs(page: int = 1, per_page: int = 15):
    """Return paginated list of log files (excluding current session log)."""
    files = core.find_log_files(exclude_current=True)
    items = []
    for f in files:
        try:
            st = os.stat(f)
            items.append(
                {
                    "path": f,
                    "name": os.path.basename(f),
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
async def get_log_preview_by_path(path: str = ""):
    """Return first/last messages of a log file by path."""
    if not path:
        return JSONResponse(status_code=400, content={"error": _("path is required")})
    files = core.find_log_files(exclude_current=True)
    norm = os.path.normpath(path)
    matches = [i for i, f in enumerate(files) if os.path.normpath(f) == norm]
    if not matches:
        return JSONResponse(status_code=404, content={"error": _("File not found")})
    idx = matches[0]
    return await get_log_preview(idx)


@app.get("/api/logs/{index}/preview")
async def get_log_preview(index: int):
    """Return first/last messages of a log file (like CLI :logs)."""
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
    """Execute a :command via REST API. Body: {"room_id": "...", "command": ":cd /path"}"""
    try:
        body = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": _("Invalid JSON body")})
    room_id = str(body.get("room_id", "")).strip()
    cmd_line = str(body.get("command", "")).strip()
    if not room_id or not cmd_line:
        return JSONResponse(
            status_code=400,
            content={"error": _("room_id and command are required")},
        )
    room = web_manager.get_room(room_id)
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
            threading.Thread(
                target=run_agent_worker,
                args=(room, _result.prompt, None),
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    room_id = websocket.query_params.get("room")
    ws_lang = (websocket.query_params.get("lang") or "").lower().strip()
    if ws_lang not in ("ja", "en", "ar"):
        ws_lang = "en"
    if not room_id:
        # require explicit room for safety
        await websocket.close(code=1008)
        return
    room = web_manager.get_room(room_id)
    try:
        room.lang = ws_lang
    except Exception:
        pass
    await room.connect(websocket)
    room.loop = asyncio.get_event_loop()
    # Ask AGENTS.md / init history immediately (no user message required).
    _bootstrap_room_on_connect(room)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "user_input":
                user_text = payload.get("text")
                if _handle_mode_command(str(user_text or "")):
                    continue
                forward_to_mesh(str(user_text or ""))
                if is_chat_mode() == "on":
                    continue
                threading.Thread(
                    target=run_agent_worker,
                    args=(room, user_text, payload.get("attachments")),
                    daemon=True,
                ).start()

            elif payload.get("type") == "command":
                cmd_text = str(payload.get("text") or "").strip()
                if _handle_mode_command(cmd_text):
                    continue
                # Route all other :commands through handle_command()
                try:
                    _cmd_line = cmd_text if cmd_text.startswith(":") else f":{cmd_text}"
                    # :cd -> room.set_base_dir() (room-scoped, no os.chdir())
                    if _cmd_line.lstrip(":").strip().startswith("cd"):
                        _cd_arg = _cmd_line.lstrip(":").strip()[3:].strip()
                        try:
                            room.set_base_dir(_cd_arg or ".")
                        except Exception as _cd_e:
                            room.add_message(
                                {
                                    "role": "assistant",
                                    "content": _("[Error] :cd failed: %(err)s")
                                    % {"err": _cd_e},
                                }
                            )
                        continue
                    _wc_client, _wc_depname = None, ""
                    try:
                        _wc_pname, _wc_client, _wc_depname = providers.make_client(core)
                    except Exception:
                        pass
                    import io as _io
                    import sys as _sys

                    _capture = _io.StringIO()
                    _old_stdout = _sys.stdout
                    try:
                        _sys.stdout = _capture
                        _result = tools_util.handle_command(
                            _cmd_line, room.history, _wc_client, _wc_depname, core=core
                        )
                    finally:
                        _sys.stdout = _old_stdout
                    _output = _capture.getvalue().strip()
                    if (
                        isinstance(_result, tools_util.CommandResult)
                        and _result.run_llm
                    ):
                        threading.Thread(
                            target=run_agent_worker,
                            args=(room, _result.prompt, None),
                            daemon=True,
                        ).start()
                    elif _output:
                        room.add_message(
                            {
                                "role": "assistant",
                                "content": _output,
                            }
                        )
                except Exception as _e:
                    room.add_message(
                        {
                            "role": "assistant",
                            "content": _("[Command Error] %(err)s") % {"err": _e},
                        }
                    )

            elif payload.get("type") == "set_modes":
                r = payload.get("reasoning")
                v = payload.get("verbosity")
                try:
                    if r is not None:
                        tools_util.apply_reasoning_arg(str(r))
                except Exception:
                    pass
                try:
                    if v is not None:
                        tools_util.apply_verbosity_arg(str(v))
                except Exception:
                    pass
                _broadcast_modes_all()

            elif payload.get("type") == "interrupt":
                from uagent import core as _core

                try:
                    _web_server_log(
                        f"[web-interrupt] room={str(room.room_id)[:8]} "
                        f"core_busy={bool(getattr(_core, 'status_busy', False))} "
                        f"ask_pending={bool(getattr(room, 'human_ask_pending', False))} "
                        f"label={getattr(_core, 'status_label', '')}"
                    )
                except Exception:
                    pass

                # Unblock pending human_ask even if status was cleared to WAIT.
                if getattr(room, "human_ask_pending", False):
                    try:
                        room.human_ask_cancelled = True
                        room.human_ask_result = ""
                        room.human_ask_sync_event.set()
                    except Exception:
                        pass

                # NOP if not busy and no pending ask
                if not getattr(_core, "status_busy", False) and not getattr(
                    room, "human_ask_pending", False
                ):
                    # human_ask_pending may already be cleared by the waiter;
                    # still allow interrupt flag for in-flight LLM.
                    if not getattr(room, "human_ask_cancelled", False):
                        continue
                with _core.interrupt_lock:
                    _core.interrupt_requested = True
                try:
                    if room.loop:
                        asyncio.run_coroutine_threadsafe(
                            room.broadcast(
                                {
                                    "type": "log",
                                    "content": "[INTERRUPT] Stop requested by user.",
                                }
                            ),
                            room.loop,
                        )
                except Exception:
                    pass

            elif payload.get("type") == "human_ask_response":
                if not getattr(room, "human_ask_pending", False):
                    try:
                        _web_server_log(
                            f"[web-ask] drop late response room={str(room.room_id)[:8]}"
                        )
                    except Exception:
                        pass
                    continue
                room.human_ask_cancelled = False
                room.human_ask_result = payload.get("text", "")
                try:
                    _web_server_log(
                        f"[web-ask] response room={str(room.room_id)[:8]} "
                        f"len={len(str(room.human_ask_result or ''))}"
                    )
                except Exception:
                    pass
                room.human_ask_sync_event.set()

                try:
                    is_pw = bool(payload.get("is_password", False))
                    display = "[SECRET]" if is_pw else room.human_ask_result
                    if room.loop:
                        asyncio.run_coroutine_threadsafe(
                            room.broadcast(
                                {"type": "log", "content": f"[REPLY] > {display}"}
                            ),
                            room.loop,
                        )
                except Exception:
                    pass

    except WebSocketDisconnect:
        room.disconnect(websocket)


def init_web():
    print(get_welcome_message())

    # Web process: suppress CLI [STATE] console output for the whole lifetime.
    # Must be set before any set_status() call (including first BUSY).
    try:
        setattr(core, "_is_web", True)
    except Exception:
        pass

    web_manager.original_set_status = core.set_status
    web_manager.original_log_message = core.log_message

    core.set_status = web_set_status

    # Web mode: UI message forwarding is handled per-room; keep core.log_message intact.
    # Tools callback init
    tools_util.init_tools_callbacks(core)

    cb = tools.context.get_callbacks()
    cb.is_gui = True

    # Register ask-user hook for project instruction selection (AGENTS.md).
    # runtime_instructions must not import web (circular); use this callback.
    try:
        from .runtime.runtime_instructions import set_ask_user_hook

        def _web_ask_user(message: str) -> str:
            room = getattr(_thread_ctx, "room", None)
            if room is None:
                try:
                    with web_manager.active_room_lock:
                        room = web_manager.active_room
                except Exception:
                    room = None
            if room is None:
                return json.dumps(
                    {
                        "user_reply": "",
                        "display_reply": "",
                        "cancelled": True,
                    }
                )
            return web_human_ask(room, {"message": message})

        set_ask_user_hook(_web_ask_user)
    except Exception as e:
        try:
            _web_server_log(f"[web-init] ask hook register failed: {e!r}")
        except Exception:
            pass

    # Wrap tools: bind room context for parallel workers + route human_ask.
    original_run_tool = tools.run_tool

    def _resolve_web_room():
        room = getattr(_thread_ctx, "room", None)
        if room is not None:
            return room
        try:
            with web_manager.active_room_lock:
                return web_manager.active_room
        except Exception:
            return None

    def web_run_tool_wrapper(name, args):
        room = _resolve_web_room()
        # Parallel tool pool threads do not inherit thread-local room.
        # Bind it for the duration of the tool so set_status/logs reach UI.
        prev_room = getattr(_thread_ctx, "room", None)
        if room is not None and prev_room is None:
            _thread_ctx.room = room
        try:
            if name == "human_ask":
                if not room:
                    return json.dumps(
                        {
                            "user_reply": "",
                            "display_reply": "",
                            "cancelled": True,
                        }
                    )
                # Keep room busy while waiting for human input so Stop stays available
                # and reconnect clients see WAIT instead of a false IDLE.
                try:
                    room.set_status(True, "WAIT")
                    if web_manager.original_set_status:
                        # core.status_busy stays True for interrupt path.
                        web_manager.original_set_status(True, "WAIT")
                except Exception:
                    pass
                try:
                    return web_human_ask(room, args)
                finally:
                    try:
                        room.set_status(True, "LLM")
                        if web_manager.original_set_status:
                            web_manager.original_set_status(True, "LLM")
                    except Exception:
                        pass
            return original_run_tool(name, args)
        finally:
            if room is not None and prev_room is None:
                try:
                    _thread_ctx.room = None
                except Exception:
                    pass

    tools.run_tool = web_run_tool_wrapper


def main():
    from .runtime.logging_setup import bind_event_context

    bind_event_context(session_id="web", correlation_id="web")
    log_event("web.start")
    sys.__stdout__.reconfigure(encoding="utf-8")
    import argparse

    from .i18n import _

    parser = argparse.ArgumentParser(prog="uagw", add_help=False)
    parser.add_argument(
        "--tool-genre-mask",
        type=int,
        default=None,
        help=_(
            "Tool genre bitmask (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,256=file,512=index,1023=all). Skips the interactive genre prompt when specified."
        ),
    )
    parser.add_argument(
        "--use-tool",
        dest="use_tool",
        action="store_true",
        default=None,
        help=_("Enable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--no-use-tool",
        dest="use_tool",
        action="store_false",
        default=None,
        help=_("Disable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--computer-use",
        dest="computer_use",
        action="store_true",
        default=None,
        help=_("Enable Computer Use (overrides UAGENT_COMPUTER_USE env var)."),
    )
    parser.add_argument(
        "--no-computer-use",
        dest="computer_use",
        action="store_false",
        default=None,
        help=_("Disable Computer Use (overrides UAGENT_COMPUTER_USE env var)."),
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help=_("Bind address (default: 127.0.0.1). Overrides UAGENT_WEB_HOST env var."),
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        default=False,
        help=_(
            "Run in API-only mode without frontend (no HTML templates or static files)."
        ),
    )
    web_args, _web_unknown = parser.parse_known_args()

    # readme/quickstart first-run display removed (files no longer bundled)
    ensure_mcp_config_template()

    # Load and activate enabled plugins (MCP / agents / hooks); status for chat later
    try:
        from .runtime.runtime_plugins import load_plugins_status_at_startup

        _plugins, _plugins_status = load_plugins_status_at_startup(activate=True)
        if _plugins_status:
            print(_plugins_status, file=sys.stderr)
        try:
            # Keep raw list so each room can format with its own locale.
            setattr(web_manager, "plugins_startup_list", _plugins)
        except Exception:
            pass
    except Exception:
        try:
            setattr(web_manager, "plugins_startup_list", [])
        except Exception:
            pass

    try:
        decision = _runtime_init.decide_workdir(env_workdir=env_get("UAGENT_WORKDIR"))
        _runtime_init.apply_workdir(decision)
        _runtime_init.reload_dotenv_custom()
        if getattr(web_args, "computer_use", None) is not None:
            os.environ["UAGENT_COMPUTER_USE"] = "1" if web_args.computer_use else "0"
        # Fail-fast env validation (aggregate missing vars)
        _runtime_init.validate_or_exit_startup_env(context="web")
        banner = _runtime_init.build_startup_banner(
            core=core,
            workdir=decision.chosen_expanded,
            workdir_source=decision.chosen_source,
        )
        print(banner, end="")

    except Exception as e:
        print(_("[FATAL] Failed to set workdir: %(err)s") % {"err": e}, file=sys.stderr)
        sys.exit(1)

    if web_args.tool_genre_mask is not None:
        from .cli_startup import _apply_startup_tool_genre_mask

        _apply_startup_tool_genre_mask(web_args.tool_genre_mask)
    else:
        from .cli_startup import _apply_startup_tool_genre_mask

        _apply_startup_tool_genre_mask(0)

    # Initialize runtime tools_enabled flag.
    # Priority: --use-tool / --no-use-tool CLI arg > UAGENT_USE_TOOL env var > default ON.
    _use_tool_arg = getattr(web_args, "use_tool", None)
    if _use_tool_arg is not None:
        core.tools_enabled = bool(_use_tool_arg)
    else:
        _use_tool_env = (env_get("UAGENT_USE_TOOL") or "").strip().lower()
        core.tools_enabled = _use_tool_env not in ("0", "false", "no", "off")

    init_web()
    try:
        tools.start_tools_warmup()
    except Exception:
        pass

    if web_args.no_frontend:
        # Remove frontend routes (/, /room/{room_id}, /static) for API-only mode
        _routes_to_remove = []
        for _route in list(app.router.routes):
            _path = getattr(_route, "path", "")
            if _path in ("/", "/room/{room_id}"):
                _routes_to_remove.append(_route)
            if type(_route).__name__ == "Mount" and _path == "/static":
                _routes_to_remove.append(_route)
        for _route in _routes_to_remove:
            app.router.routes.remove(_route)
        print(_("Starting in API-only mode (no frontend)."))
    import socket

    # Resolve bind host: --host arg > UAGENT_WEB_HOST env > default 127.0.0.1
    bind_host = "127.0.0.1"
    _env_host = (env_get("UAGENT_WEB_HOST") or "").strip()
    if _env_host:
        bind_host = _env_host
    if web_args.host:
        bind_host = web_args.host

    def get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    local_ip = get_local_ip()
    port = 8000
    sys.__stdout__.write(_("Starting server on") + f" http://localhost:{port}\n")
    if bind_host == "0.0.0.0" and local_ip and local_ip != "127.0.0.1":
        sys.__stdout__.write(_("External URL:") + f" http://{local_ip}:{port}\n")
    sys.__stdout__.flush()
    # Fire SessionStart hook
    try:
        from .hooks_engine import fire_session_start

        fire_session_start()
    except Exception:
        pass

    config = uvicorn.Config(app, host=bind_host, port=port, ws_max_size=10_000_000)
    server = uvicorn.Server(config)
    try:
        server.run()
    finally:
        # Fire Stop hook
        try:
            from .hooks_engine import fire_stop

            fire_stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
