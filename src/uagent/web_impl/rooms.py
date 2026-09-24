"""Web room and manager objects (split from web.py)."""

from __future__ import annotations

import asyncio
from datetime import datetime
import os
import threading
import time
from typing import Any, Optional

from fastapi import WebSocket
from ..i18n import _, set_thread_lang
from .. import core
from ..env_utils import env_get
from ..runtime import runtime_init as _runtime_init
from ..runtime.room_access import private_room_idle_ttl_seconds
from ..runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
)
from ..welcome import get_welcome_message
from .. import util_tools as tools_util
from .helpers import _enrich_message_attachments, _load_input_history


class WebRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.session_id: str = ""
        self.private_session: bool = False
        self.project_id: str = ""
        self.base_dir: str = os.getcwd()
        self.lang: str = "en"

        self.active_connections: list[WebSocket] = []
        self._connection_contexts: dict[int, Any] = {}
        self._lifecycle_lock = threading.Lock()
        self._activity_lock = threading.Lock()
        self.last_activity = time.monotonic()
        self.messages: list[dict[str, Any]] = []  # UI display
        self.status: dict[str, Any] = {"busy": False, "label": "IDLE", "workdir": ""}

        # history for LLM
        self.history: list[dict[str, Any]] = []
        self.history_initialized = False
        self.portable_history: list[dict[str, Any]] = []
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

    def touch(self) -> None:
        with self._activity_lock:
            self.last_activity = time.monotonic()

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

    async def connect(self, websocket: WebSocket, connection_context: Any = None):
        set_thread_lang(getattr(self, "lang", "en"))
        try:
            await self._validate_connection_context(websocket, connection_context)
            await websocket.accept()
            with self._lifecycle_lock:
                self.active_connections.append(websocket)
                if connection_context is not None:
                    self._connection_contexts[id(websocket)] = connection_context
            self.touch()

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
            input_history = [] if self.private_session else _load_input_history()
            await self._validate_connection_context(websocket, connection_context)
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
                    "project_id": self.project_id,
                    "private_session": self.private_session,
                    "authn_kind": getattr(
                        getattr(connection_context, "identity", None),
                        "authn_kind",
                        "local",
                    ),
                }
            )
            # Restore pending human_ask modal after reconnect.
            if getattr(self, "human_ask_pending", False):
                try:
                    await self._validate_connection_context(
                        websocket, connection_context
                    )
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

    async def _validate_connection_context(
        self, websocket: WebSocket, connection_context: Any
    ) -> None:
        if connection_context is None:
            return
        try:
            connection_context.validate_authentication_configuration()
            validate_room_access = getattr(
                connection_context, "validate_room_access", None
            )
            if callable(validate_room_access):
                validate_room_access(touch_activity=False)
        except (IdentityConfigurationError, IdentityResolutionError):
            self.disconnect(websocket)
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            raise

    def disconnect(self, websocket: WebSocket):
        with self._lifecycle_lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            self._connection_contexts.pop(id(websocket), None)
        self.touch()

    async def broadcast(self, data: dict[str, Any]):
        for connection in list(self.active_connections):
            connection_context = self._connection_contexts.get(id(connection))
            if connection_context is not None:
                try:
                    await self._validate_connection_context(
                        connection, connection_context
                    )
                except (IdentityConfigurationError, IdentityResolutionError):
                    continue
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

    def set_status(self, busy: bool, label: str = ""):
        self.touch()
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
        self.touch()
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

    def get_or_create_room(self, room_id: str) -> tuple[WebRoom, bool]:
        with self.rooms_lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = WebRoom(room_id)
                created = True
            else:
                created = False
            room = self.rooms[room_id]
            room.touch()
            return room, created

    def get_room(self, room_id: str) -> WebRoom:
        return self.get_or_create_room(room_id)[0]

    def discard_if_idle(self, room_id: str, expected_room: WebRoom) -> bool:
        """Remove a just-created room if its connection was denied."""
        with self.rooms_lock:
            if self.rooms.get(room_id) is not expected_room:
                return False
            if self._room_is_active(expected_room):
                return False
            self.rooms.pop(room_id, None)
            return True

    def discard_expired_private_room_if_idle(self, room_id: str) -> bool:
        """Forget cached room state only after its durable private binding expired."""
        with self.rooms_lock:
            room = self.rooms.get(room_id)
            if room is None or not room.private_session or self._room_is_active(room):
                return False
            self.rooms.pop(room_id, None)
            return True

    @staticmethod
    def idle_ttl_seconds() -> int:
        """Return the reconnect grace period before an idle room is evicted."""
        return private_room_idle_ttl_seconds()

    @staticmethod
    def _room_is_active(room: WebRoom) -> bool:
        # The worker lock covers agent execution, streaming and human_ask waits.
        # Keep the explicit checks as defense in depth if worker/status contracts
        # change independently in the future.
        with room._lifecycle_lock:
            connected = bool(room.active_connections)
        return bool(
            connected
            or room.worker_lock.locked()
            or room.status.get("busy")
            or room.human_ask_pending
        )

    def evict_idle_rooms(
        self,
        *,
        idle_ttl_seconds: int | None = None,
        now: float | None = None,
        private_only: bool = True,
    ) -> list[str]:
        """Drop disconnected idle private rooms after their reconnect grace period."""
        ttl = max(
            0,
            int(
                self.idle_ttl_seconds()
                if idle_ttl_seconds is None
                else idle_ttl_seconds
            ),
        )
        current = time.monotonic() if now is None else now
        evicted: list[str] = []
        with self.rooms_lock:
            for room_id, room in list(self.rooms.items()):
                if private_only and not room.private_session:
                    continue
                if self._room_is_active(room):
                    continue
                with room._activity_lock:
                    idle_for = current - room.last_activity
                if idle_for >= ttl:
                    self.rooms.pop(room_id, None)
                    evicted.append(room_id)
        return evicted

    def active_room_ids(self) -> set[str]:
        """Return rooms that must not be expired from persistent storage."""
        with self.rooms_lock:
            rooms = list(self.rooms.items())
        return {room_id for room_id, room in rooms if self._room_is_active(room)}


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
