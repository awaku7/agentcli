"""Web room and manager objects (split from web.py)."""

from __future__ import annotations

import asyncio
from datetime import datetime
import os
import threading
from typing import Any, Optional

from fastapi import WebSocket
from ..i18n import _, set_thread_lang
from .. import core
from ..env_utils import env_get
from ..runtime import runtime_init as _runtime_init
from ..welcome import get_welcome_message
from .. import util_tools as tools_util
from .helpers import _enrich_message_attachments, _load_input_history


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


_thread_ctx = threading.local()
