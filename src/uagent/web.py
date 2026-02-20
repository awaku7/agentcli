import asyncio
import json
import os
import re
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# uagent module imports
from . import core as core
from . import runtime_init as _runtime_init
from . import uagent_llm as llm_util
from . import util_providers as providers
from . import util_tools as tools_util
from . import tools
from .i18n import _
from .i18n import set_thread_lang
from .welcome import get_welcome_message

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


class WebRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.lang: str = "en"

        self.active_connections: List[WebSocket] = []
        self.messages: List[Dict[str, Any]] = []  # UI display
        self.status: Dict[str, Any] = {"busy": False, "label": "IDLE", "workdir": ""}

        # history for LLM
        self.history: List[Dict[str, Any]] = []
        self.history_initialized = False

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
                            {
                                "role": m.get("role"),
                                "content": m.get("content", ""),
                                "name": m.get("name"),
                                "tool_calls": m.get("tool_calls"),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                except Exception:
                    msgs = self.messages

            _v = (os.environ.get("UAGENT_WEB_VERBOSE") or "").strip().lower()
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
                    self.add_message({"role": "assistant", "content": welcome_msg})

                try:
                    setattr(self, "welcome_shown", True)
                except Exception:
                    pass

            await websocket.send_json(
                {
                    "type": "init",
                    "messages": msgs,
                    "status": self.status,
                    "web_verbose": web_verbose,
                    "room_id": self.room_id,
                }
            )
        finally:
            set_thread_lang(None)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: Dict[str, Any]):
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

    def add_message(self, msg: Dict[str, Any]):
        display_msg = {
            "role": msg.get("role"),
            "content": msg.get("content", ""),
            "name": msg.get("name"),
            "tool_calls": msg.get("tool_calls"),
            "timestamp": datetime.now().isoformat(),
        }
        self.messages.append(display_msg)
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "message", "message": display_msg}), self.loop
            )


class WebManager:
    def __init__(self):
        self.rooms: Dict[str, WebRoom] = {}
        self.rooms_lock = threading.Lock()

        self.original_log_message = None
        self.original_set_status = None

    def get_room(self, room_id: str) -> WebRoom:
        with self.rooms_lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = WebRoom(room_id)
            return self.rooms[room_id]


web_manager = WebManager()


def web_human_ask(room: WebRoom, args: Dict[str, Any]) -> str:
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
    # room-scoped status updates are handled by WebRoom.set_status in worker.
    return


def _web_console_log_enabled() -> bool:
    v = (os.environ.get("UAGENT_WEB_CONSOLE_LOG") or "").strip().lower()
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

                # Suppress CLI-only multiline input mode guidance in Web UI
                if "複数行" in clean_line:
                    continue

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast({"type": "log", "content": clean_line}),
                        room.loop,
                    )

    def flush(self):
        with self.lock:
            if self.buffer:
                clean_line = ANSI_ESCAPE.sub("", self.buffer)
                try:
                    filtered_lines: List[str] = []
                    for ln in clean_line.splitlines():
                        if "複数行" in ln:
                            continue
                        filtered_lines.append(ln)
                    clean_line = "\n".join(filtered_lines)
                except Exception:
                    pass

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast({"type": "log", "content": clean_line}),
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
                if "複数行" in clean_line:
                    continue

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast({"type": "log", "content": clean_line}),
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


def run_agent_worker(room: WebRoom, user_input: str):
    # Ensure logs go to this room (thread-local)
    _thread_ctx.room = room
    set_thread_lang(getattr(room, "lang", "en"))

    # Serialize per-room runs to avoid history/tool collisions
    if not room.worker_lock.acquire(blocking=False):
        room.add_message(
            {
                "role": "assistant",
                "content": "[WARN] このルームでは別の処理が実行中です。完了してから再送してください。",
            }
        )
        return

    room.set_status(True, "BUSY")

    try:
        setattr(core, "_is_web", True)
    except Exception:
        pass

    # Streaming helpers for Web UI
    stream_state: Dict[str, Any] = {"id": None, "active": False}

    def _web_stream_send(payload: Dict[str, Any]) -> None:
        try:
            if room.loop:
                asyncio.run_coroutine_threadsafe(room.broadcast(payload), room.loop)
        except Exception:
            pass

    def _stream_start() -> str:
        sid = f"asst_{int(time.time() * 1000)}"
        stream_state["id"] = sid
        stream_state["active"] = True
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

    def _patched_log_message(msg: Dict[str, Any]) -> None:
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
        if callable(_orig_log_message):
            setattr(core, "log_message", _patched_log_message)
    except Exception:
        pass

    try:
        if not (os.environ.get("UAGENT_PROVIDER") or "").strip():
            room.add_message(
                {
                    "role": "assistant",
                    "content": "[FATAL] 環境変数 UAGENT_PROVIDER が設定されていません。\nWebサーバ起動時の環境変数を確認してください。",
                }
            )
            return

        provider_name, client, depname = providers.make_client(core)

        print(f"[INFO] model(deployment) = {depname}")

        user_msg = {"role": "user", "content": user_input}
        core.log_message(user_msg)

        if not room.history_initialized:
            room.history = tools_util.build_initial_messages(core=core)
            room.history_initialized = True

            # Long-term memory insertion (align with CLI/GUI)
            from .tools import long_memory as personal_long_memory
            from .tools import shared_memory

            print("[INFO] " + _("Loaded long-term memory."))
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
                    print("[INFO] " + _("Loaded shared long-term memory."))

                for m in room.history[before_len:]:
                    core.log_message(m)

            except Exception as e:
                print(
                    "[WARN] "
                    + _(
                        "Exception occurred while loading shared long-term memory: %(err)s"
                    )
                    % {"err": e}
                )

        room.history.append(user_msg)

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

        msg = "[FATAL] Web worker error.\n" + err
        if (
            isinstance(e, SystemExit)
            and not (os.environ.get("UAGENT_PROVIDER") or "").strip()
        ):
            msg = "[FATAL] 環境変数 UAGENT_PROVIDER が設定されていません。\nWebサーバ起動時の環境変数を確認してください。"
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
    # ensure room exists
    web_manager.get_room(room_id)
    # Single unified template; client-side handles i18n via ?lang=ja|en (or browser language fallback)
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    room_id = websocket.query_params.get("room")
    ws_lang = (websocket.query_params.get("lang") or "").lower().strip()
    if ws_lang not in ("ja", "en"):
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
                threading.Thread(
                    target=run_agent_worker, args=(room, user_text), daemon=True
                ).start()

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
        decision = _runtime_init.decide_workdir(
            env_workdir=os.environ.get("UAGENT_WORKDIR")
        )
        _runtime_init.apply_workdir(decision)
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
    print("Starting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
