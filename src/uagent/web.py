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
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# uagent module imports
from . import core as core
from . import runtime_init as _runtime_init
from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from . import uagent_llm as llm_util
from .image_session import build_image_session_message
from . import util_providers as providers
from . import util_tools as tools_util
from . import tools
from .welcome import get_welcome_message
from .gui_ansi import ansi_to_html, wrap_pre

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

app = FastAPI(title="uag Web")

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATE_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _enrich_message_attachments(msg: dict[str, Any]) -> dict[str, Any]:
    display_msg = dict(msg or {})
    attachments = display_msg.get("attachments")
    if isinstance(attachments, list) and attachments:
        enriched = []
        for att in attachments:
            if not isinstance(att, dict):
                enriched.append(att)
                continue
            item = dict(att)
            path = item.get("path") or item.get("saved_path") or item.get("file_path")
            mime = str(item.get("mime") or item.get("type") or "").lower()
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
    return display_msg


class WebRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
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

        # per-room worker serialization (avoid history/tool collisions)
        self.worker_lock = threading.Lock()

        # event loop for run_coroutine_threadsafe
        self.loop: Optional[asyncio.AbstractEventLoop] = None

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
                        workdir=os.getcwd(),
                        workdir_source="(server)",
                    )
                except Exception:
                    banner = ""

                try:
                    welcome_text = get_welcome_message()
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

            await websocket.send_json(
                {
                    "type": "init",
                    "messages": msgs,
                    "status": self.status,
                    "modes": {
                        "reasoning": tools_util.get_reasoning_mode(),
                        "verbosity": tools_util.get_verbosity_mode(),
                    },
                    "web_verbose": web_verbose,
                    "room_id": self.room_id,
                }
            )
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
        try:
            workdir = os.getcwd()
        except Exception:
            workdir = ""

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
        display_msg["content"] = msg.get("content", "")
        display_msg["name"] = msg.get("name")
        display_msg["tool_calls"] = msg.get("tool_calls")
        display_msg["saved_path"] = msg.get("saved_path")
        display_msg["saved_files"] = msg.get("saved_files")
        display_msg["timestamp"] = datetime.now().isoformat()
        self.messages.append(display_msg)
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "message", "message": display_msg}), self.loop
            )


class WebManager:
    def __init__(self):
        self.rooms: dict[str, WebRoom] = {}
        self.rooms_lock = threading.Lock()

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

    # notify only this room
    if room.loop:
        asyncio.run_coroutine_threadsafe(
            room.broadcast(
                {"type": "human_ask", "message": message, "is_password": is_password}
            ),
            room.loop,
        )

    room.human_ask_is_password = is_password
    room.human_ask_sync_event.clear()
    room.human_ask_sync_event.wait()

    user_reply = room.human_ask_result
    display_reply = "[SECRET]" if is_password else user_reply
    cancelled = False

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

    # Web UI: if a worker is running in a room (thread-local), forward status updates there.
    try:
        room = getattr(_thread_ctx, "room", None)
    except Exception:
        room = None

    if room is not None:
        try:
            room.set_status(busy, label)
        except Exception:
            pass

    return


def _web_console_log_enabled() -> bool:
    v = (env_get("UAGENT_WEB_CONSOLE_LOG") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


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
                        filtered_lines.append(ln)
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


def run_agent_worker(
    room: WebRoom,
    user_input: str,
    attachments: Optional[list[dict[str, Any]]] = None,
):
    # Ensure logs go to this room (thread-local)
    _thread_ctx.room = room
    set_thread_lang(getattr(room, "lang", "en"))

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
        return

    room.set_status(True, "BUSY")

    try:
        setattr(core, "_is_web", True)
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

    def _stream_delta(delta: str) -> None:
        if not delta:
            return
        if not stream_state.get("active"):
            _stream_start()
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

    # Patch core.log_message during this worker run so streaming deltas can go to WebSocket.
    _orig_log_message = getattr(core, "log_message", None)

    def _patched_log_message(msg: dict[str, Any]) -> None:
        try:
            if isinstance(msg, dict) and msg.get("type") == "assistant_stream_delta":
                _stream_delta(str(msg.get("delta") or ""))
                return
            if isinstance(msg, dict) and msg.get("type") == "assistant_stream_end":
                _stream_end()
                return
        except Exception:
            pass
        if callable(_orig_log_message):
            _orig_log_message(msg)
        try:
            if isinstance(msg, dict) and msg.get("role") in (
                "user",
                "assistant",
                "tool",
            ):
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
            label = os.path.basename(name) or os.path.basename(path) or path
            if is_image:
                attachment_lines.append(
                    _("[Attached Image] %(name)s") % {"name": label}
                )
                attachment_lines.append(_("[Image Path] %(path)s") % {"path": path})
                item["type"] = "image"
            else:
                attachment_lines.append(_("[Attached File] %(name)s") % {"name": label})
                attachment_lines.append(_("[File Path] %(path)s") % {"path": path})
                item["type"] = "file"
            item["saved_path"] = path
            if mime:
                item["mime"] = mime
            clean_attachments.append(item)

        prompt_text = user_input
        if attachment_lines:
            prompt_text = (
                (prompt_text.rstrip() + "\n\n") if prompt_text.strip() else ""
            ) + "\n".join(attachment_lines)

        user_msg = {"role": "user", "content": prompt_text}

        user_msg = {"role": "user", "content": prompt_text}
        if clean_attachments:
            user_msg["attachments"] = clean_attachments
        core.log_message(user_msg)

        if not room.history_initialized:
            room.history = tools_util.build_initial_messages(core=core)
            room.history_initialized = True

            # Long-term memory insertion (align with CLI/GUI)
            from .tools import long_memory as personal_long_memory
            from .tools import shared_memory

            print(_("[INFO] Loaded long-term memory."))
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

                for m in room.history[before_len:]:
                    core.log_message(m)

            except Exception as e:
                print(
                    _(
                        "[WARN] Exception occurred while loading shared long-term memory: %(err)s"
                    )
                    % {"err": e}
                )

        room.history.append(user_msg)
        room.image_session = build_image_session_message(room.history, depname)

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

    except BaseException as e:
        err = repr(e)
        tb = ""
        try:
            tb = traceback.format_exc()
        except Exception:
            tb = ""

        msg = _("[FATAL] Web worker error.\n%(err)s") % {"err": err}
        if isinstance(e, SystemExit) and not (env_get("UAGENT_PROVIDER") or "").strip():
            msg = _(
                "[FATAL] Environment variable UAGENT_PROVIDER is not set.\nPlease check environment variables when starting the web server."
            )
        if tb and tb != "NoneType: None\n":
            msg = msg + "\n\n" + tb

        room.add_message({"role": "assistant", "content": msg})

    finally:
        try:
            if callable(_orig_log_message):
                setattr(core, "log_message", _orig_log_message)
        except Exception:
            pass

        room.set_status(False, "IDLE")
        room.worker_lock.release()
        try:
            set_thread_lang(None)
        except Exception:
            pass

        _thread_ctx.room = None


@app.get("/")
async def get_root():
    room_id = uuid4().hex
    return RedirectResponse(url=f"/room/{room_id}")


@app.get("/room/{room_id}")
async def get_room(request: Request, room_id: str):
    try:
        # ensure room exists
        web_manager.get_room(room_id)
        # Single unified template; client-side handles i18n via ?lang=ja|en|ar (or browser language fallback)
        page_lang = "en"
        try:
            q_lang = (request.query_params.get("lang") or "").strip().lower()
            accept_lang = (request.headers.get("accept-language") or "").strip().lower()
            raw_lang = q_lang or accept_lang
            if raw_lang.startswith("ar"):
                page_lang = "ar"
            elif raw_lang.startswith("ja"):
                page_lang = "ja"
        except Exception:
            pass
        page_dir = "rtl" if page_lang == "ar" else "ltr"
        return templates.TemplateResponse(
            request,
            "index.html",
            {"page_lang": page_lang, "page_dir": page_dir},
        )
    except Exception:
        err = traceback.format_exc()
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>UAGENT WEB - Error</title>
  <style>
    body {{ font-family: sans-serif; background: #f3f4f6; margin: 0; padding: 24px; }}
    .box {{ background: white; border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #111827; color: #f9fafb; padding: 12px; border-radius: 6px; overflow: auto; }}
    h1 {{ margin-top: 0; color: #b91c1c; }}
  </style>
</head>
<body>
  <div class=\"box\">
    <h1>Internal Error</h1>
    <p>room_id: {room_id}</p>
    <pre>{err}</pre>
  </div>
</body>
</html>""",
            status_code=500,
        )


@app.post("/upload")
async def upload_files(
    room: str = Form(""),
    files: list[UploadFile] = File(...),
):
    try:
        cwd = os.path.abspath(os.getcwd())
        room_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(room or "").strip()) or "default"
        upload_root = os.path.join(cwd, ".uagent_web_uploads", room_id)
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
            item: dict[str, Any] = {
                "name": original_name,
                "saved_path": dst_path,
                "path": dst_path,
                "mime": mime,
                "type": "image" if is_image else "file",
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
async def get_local_file(path: str):
    try:
        cwd = os.path.abspath(os.getcwd())
        raw = str(path or "").strip()
        if not raw:
            raise ValueError(_("missing path"))
        full = os.path.abspath(raw)
        if not os.path.isabs(raw):
            full = os.path.abspath(os.path.join(cwd, raw))
        full_norm = os.path.normpath(full)
        cwd_norm = os.path.normpath(cwd)
        if not (full_norm == cwd_norm or full_norm.startswith(cwd_norm + os.sep)):
            raise ValueError(_("path outside workdir"))
        if not os.path.isfile(full_norm):
            raise FileNotFoundError(full_norm)
        return FileResponse(full_norm)
    except Exception:
        raise


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

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "user_input":
                user_text = payload.get("text")
                if _handle_mode_command(str(user_text or "")):
                    continue
                threading.Thread(
                    target=run_agent_worker,
                    args=(room, user_text, payload.get("attachments")),
                    daemon=True,
                ).start()

            elif payload.get("type") == "command":
                cmd_text = payload.get("text")
                _handle_mode_command(str(cmd_text or ""))

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

            elif payload.get("type") == "human_ask_response":
                room.human_ask_result = payload.get("text", "")
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

    web_manager.original_set_status = core.set_status
    web_manager.original_log_message = core.log_message

    core.set_status = web_set_status

    # Web mode: UI message forwarding is handled per-room; keep core.log_message intact.
    # Tools callback init
    tools_util.init_tools_callbacks(core)

    cb = tools.context.get_callbacks()
    cb.is_gui = True

    # Wrap human_ask tool: route to the currently running room (thread-local)
    original_run_tool = tools.run_tool

    def web_run_tool_wrapper(name, args):
        if name == "human_ask":
            room = getattr(_thread_ctx, "room", None)
            if not room:
                # Fallback: no room context
                return json.dumps(
                    {
                        "user_reply": "",
                        "display_reply": "",
                        "cancelled": True,
                    }
                )
            return web_human_ask(room, args)
        return original_run_tool(name, args)

    tools.run_tool = web_run_tool_wrapper


def main():
    try:
        from .readme_util import (
            maybe_print_quickstart_on_first_run,
            maybe_print_readme_on_first_run,
        )

        maybe_print_readme_on_first_run(open_with_os=True)
        maybe_print_quickstart_on_first_run(open_with_os=True)
    except Exception:
        pass

    ensure_mcp_config_template()

    try:
        decision = _runtime_init.decide_workdir(env_workdir=env_get("UAGENT_WORKDIR"))
        _runtime_init.apply_workdir(decision)
        _runtime_init.reload_dotenv_custom()
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

    init_web()
    sys.__stdout__.write(_("Starting server on") + " http://localhost:8000\n")
    sys.__stdout__.flush()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
