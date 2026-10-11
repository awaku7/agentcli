"""Bounded, process-isolated foreground turns for independent Web rooms.

IPC is private to server-created children. Browser input is never unpickled.
The parent owns authentication, sockets and admission; each child owns cwd,
core, tools, callbacks and provider continuation for one turn.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import multiprocessing
import os
import threading
import time
from contextlib import contextmanager
from typing import Any

ROOM_FIELDS = (
    "room_id",
    "session_id",
    "private_session",
    "project_id",
    "base_dir",
    "lang",
    "history",
    "history_initialized",
    "portable_history",
    "responses_state",
    "tool_context",
    "agent_state_manager",
    "mcp_request_generation",
    "image_session",
    "_worker_tool_names",
    "_worker_parent_tool_names",
    "_worker_auto_pilot",
)
CORE_FIELDS = (
    "tools_enabled",
    "show_tool_output",
    "auto_pilot_active",
    "auto_pilot_goal",
    "auto_pilot_max_rounds",
    "auto_pilot_complete_regex",
    "memory_owner",
)
AUTO_PILOT_FIELDS = (
    "auto_pilot_active",
    "auto_pilot_goal",
    "auto_pilot_max_rounds",
    "auto_pilot_complete_regex",
    "auto_pilot_round",
    "auto_pilot_exit_requested",
)


@contextmanager
def bind_room_auto_pilot(room, *, enabled: bool):
    """Keep command-created goals on their room rather than server core."""
    if not enabled:
        yield
        return
    from .. import core

    previous = {name: getattr(core, name) for name in AUTO_PILOT_FIELDS}
    try:
        for name, value in getattr(room, "_worker_auto_pilot", {}).items():
            setattr(core, name, value)
        yield
    finally:
        room._worker_auto_pilot = {
            name: getattr(core, name) for name in AUTO_PILOT_FIELDS
        }
        for name, value in previous.items():
            setattr(core, name, value)


def room_state(room) -> dict[str, Any]:
    return {
        name: copy.deepcopy(getattr(room, name))
        for name in ROOM_FIELDS
        if hasattr(room, name)
    }


def room_worker_count(cli_value: int | None = None) -> int:
    from ..env_utils import env_get

    try:
        value = int(
            cli_value
            if cli_value is not None
            else (env_get("UAGENT_WEB_ROOM_WORKERS") or "5")
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("room workers must be a positive integer") from exc
    if value < 1:
        raise ValueError("room workers must be at least 1")
    return value


def _child_turn(connection, payload) -> None:
    """Spawn entry point; no parent locks, SQLite handles or clients are inherited."""
    from .. import core
    from ..decision.settings import configure_decision_settings
    from ..runtime.session_store import attach_opt_in_session_store
    from ..tools._genre_control_util import enable_single_tool
    from .agent_worker import run_agent_worker
    from .init import init_web
    from .rooms import WebRoom, web_manager

    from ..util_mode import set_display_reasoning

    configure_decision_settings(cli_provider=payload["decision_provider"])
    set_display_reasoning(payload["display_reasoning"])
    send_lock = threading.Lock()
    finished = threading.Event()

    def send(value):
        with send_lock:
            connection.send(value)

    room = WebRoom(payload["room"]["room_id"])
    for name, value in payload["room"].items():
        setattr(room, name, value)
    os.chdir(payload["project_path"] or room.base_dir)
    log_key = hashlib.sha256(room.room_id.encode()).hexdigest()[:16]
    core.LOG_FILE = os.path.join(
        core.BASE_LOG_DIR, f"scheck_log_web_{log_key}_{os.getpid()}.jsonl"
    )
    for name, value in payload["core"].items():
        setattr(core, name, value)
    store_path = payload.get("store_path")
    if store_path:
        os.environ["UAGENT_SESSION_STORE"] = "1"
        os.environ["UAGENT_SESSION_STORE_PATH"] = store_path
        attach_opt_in_session_store(
            core,
            project_path=room.base_dir,
            entry_point="web",
            existing_session_id=room.session_id,
        )
    else:
        os.environ["UAGENT_SESSION_STORE"] = "0"
    from ..runtime.runtime_plugins import load_plugins_status_at_startup

    load_plugins_status_at_startup(activate=True)
    original_log = core.log_message

    def log_message(message):
        content = message.get("content") if isinstance(message, dict) else None
        if (
            message.get("role") == "system"
            and isinstance(content, str)
            and content.startswith("[CWD] ")
        ):
            try:
                room.set_base_dir(json.loads(content[6:])["path"])
            except (ValueError, KeyError, OSError):
                pass
        original_log(message)

    core.log_message = log_message
    # Child calls the serial worker directly. It must not spawn grandchildren.
    web_manager.room_worker_pool = None
    init_web()
    # Process-local background Jobs cannot outlive this foreground child.
    # Fail closed rather than returning IDs for jobs that disappear at exit.
    from .sub_agent_jobs import shutdown_web_job_runtime

    shutdown_web_job_runtime()
    for name in payload["tools"]:
        enable_single_tool(name)
    web_manager.rooms[room.room_id] = room
    room.active_connections = [True] if payload["connected"] else []
    loop = asyncio.new_event_loop()
    room.loop = loop

    async def broadcast(event):
        send({"event": event})

    room.broadcast = broadcast
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    def controls():
        while not finished.is_set():
            try:
                if not connection.poll(0.1):
                    continue
                request = connection.recv()
                if request["type"] == "interrupt":
                    with core.interrupt_lock:
                        core.interrupt_requested = True
                    room.human_ask_cancelled = True
                    room.human_ask_sync_event.set()
                elif request["type"] == "answer" and room.human_ask_pending:
                    room.human_ask_result = request["text"]
                    room.human_ask_cancelled = False
                    room.human_ask_sync_event.set()
                elif request["type"] == "connected":
                    room.active_connections = [True] if request["value"] else []
            except (EOFError, OSError):
                with core.interrupt_lock:
                    core.interrupt_requested = True
                break

    threading.Thread(target=controls, daemon=True).start()
    if room.private_session:
        for name in (
            "responses_state",
            "tool_context",
            "agent_state_manager",
            "mcp_request_generation",
        ):
            if hasattr(room, name):
                setattr(core, name, getattr(room, name))
    try:
        run_agent_worker(
            room,
            payload["input"],
            payload["attachments"],
            turn_context=payload["turn_context"],
            identity_context=payload["identity_context"],
            project_path=payload["project_path"],
        )
        if room.private_session:
            for name in (
                "responses_state",
                "tool_context",
                "agent_state_manager",
                "mcp_request_generation",
            ):
                if hasattr(core, name):
                    setattr(room, name, getattr(core, name))
        from ..tools._genre_control_util import get_enabled_tool_names

        room._worker_tool_names = get_enabled_tool_names()
        room._worker_parent_tool_names = payload["parent_tools"]
        room._worker_auto_pilot = {
            name: getattr(core, name) for name in AUTO_PILOT_FIELDS
        }
        # Drain broadcasts already scheduled by the worker before its final state.
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), loop).result(timeout=5)
        send({"state": room_state(room)})
    finally:
        finished.set()
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(5)
        connection.close()
        store = getattr(core, "session_store", None)
        if store is not None:
            store.close()


class RoomWorkerPool:
    def __init__(self, workers: int, *, target=_child_turn):
        if workers < 1:
            raise ValueError("room workers must be at least 1")
        self.workers = workers
        self._slots = threading.BoundedSemaphore(workers)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._running: dict[str, tuple[Any, Any, Any, threading.Lock]] = {}
        self._target = target
        self._context = multiprocessing.get_context("spawn")

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._running)

    def _send(self, room, value) -> bool:
        with self._lock:
            entry = self._running.get(room.room_id)
            if entry is None or entry[0] is not room:
                return False
            try:
                with entry[3]:
                    entry[1].send(value)
                return True
            except (EOFError, OSError):
                return False

    def interrupt(self, room) -> bool:
        return self._send(room, {"type": "interrupt"})

    def answer(self, room, text) -> bool:
        return self._send(room, {"type": "answer", "text": text})

    def run(self, room, user_input, attachments=None, **kwargs):
        from .. import core
        from ..i18n import _
        from ..tools._genre_control_util import get_enabled_tool_names
        from ..decision.settings import get_decision_settings
        from ..util_mode import get_display_reasoning
        from .agent_worker import _ensure_public_room_session

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
        state_received = False
        room._partial_streams = {}
        acquired = False
        process = None
        parent = child = None
        try:
            acquired = self._slots.acquire(blocking=False)
            if not acquired:
                room.set_status(True, "QUEUED")
                while not self._closed.is_set():
                    if self._slots.acquire(timeout=0.1):
                        acquired = True
                        break
            else:
                room.set_status(True, "BUSY")
            if not acquired or self._closed.is_set():
                return
            store = getattr(core, "session_store", None)
            if store is not None and not room.private_session:
                _ensure_public_room_session(room, store, room.base_dir)
            parent_tools = get_enabled_tool_names()
            tool_names = (
                room._worker_tool_names
                if getattr(room, "_worker_parent_tool_names", None) == parent_tools
                else parent_tools
            )
            payload = {
                "room": room_state(room),
                "decision_provider": get_decision_settings().provider,
                "display_reasoning": get_display_reasoning(),
                "input": user_input,
                "attachments": attachments,
                "core": {
                    name: copy.deepcopy(getattr(core, name))
                    for name in CORE_FIELDS
                    if hasattr(core, name)
                },
                "store_path": str(store.path.resolve()) if store is not None else "",
                "tools": tool_names,
                "parent_tools": parent_tools,
                "connected": bool(room.active_connections),
                "turn_context": kwargs.get("turn_context"),
                "identity_context": kwargs.get("identity_context"),
                "project_path": kwargs.get("project_path"),
            }
            payload["core"].update(getattr(room, "_worker_auto_pilot", {}))
            parent, child = self._context.Pipe()
            process = self._context.Process(
                target=self._target, args=(child, payload), daemon=False
            )
            with self._lock:
                if self._closed.is_set():
                    return
                room._process_stale_history = room.history
                room._process_turn_active = True
                process.start()
                self._running[room.room_id] = (room, parent, process, threading.Lock())
            child.close()
            room.set_status(True, "BUSY")
            connected = payload["connected"]
            while True:
                if parent.poll(0.1):
                    try:
                        value = parent.recv()
                    except EOFError:
                        break
                    if "state" in value:
                        for name, item in value["state"].items():
                            if name != "room_id":
                                setattr(room, name, item)
                        state_received = True
                    elif "event" in value:
                        self._relay(room, value["event"])
                elif not process.is_alive():
                    break
                current_connected = bool(room.active_connections)
                if current_connected != connected:
                    self._send(room, {"type": "connected", "value": current_connected})
                    connected = current_connected
            process.join(5)
            if not state_received:
                for content in room._partial_streams.values():
                    if content and not any(
                        m.get("role") == "assistant" and m.get("content") == content
                        for m in room.messages
                    ):
                        room.messages.append({"role": "assistant", "content": content})
                room.add_message(
                    {
                        "role": "assistant",
                        "content": "[ERROR] Room worker exited before returning its state.",
                    }
                )
        except Exception as exc:
            room.add_message(
                {"role": "assistant", "content": f"[ERROR] Room worker failed: {exc}"}
            )
        finally:
            with self._lock:
                self._running.pop(room.room_id, None)
            if process is not None and process.pid is not None and process.is_alive():
                process.terminate()
                process.join(5)
            for pipe in (parent, child):
                if pipe is not None:
                    pipe.close()
            room._partial_streams = {}
            if state_received:
                room._process_stale_history = None
            room._process_turn_active = False
            room.human_ask_pending = False
            try:
                room.set_status(False, "IDLE")
            finally:
                room.worker_lock.release()
                if acquired:
                    self._slots.release()

    @staticmethod
    def _relay(room, event):
        with room._lifecycle_lock:
            kind = event.get("type")
            if kind == "message":
                room.messages.append(event["message"])
                if event["message"].get("role") == "assistant":
                    content = event["message"].get("content")
                    for stream_id, text in list(
                        getattr(room, "_partial_streams", {}).items()
                    ):
                        if text == content:
                            room._partial_streams.pop(stream_id, None)
                            break
            elif kind == "assistant_stream_start":
                room._partial_streams[event["id"]] = ""
            elif kind == "assistant_stream_delta":
                stream_id = event.get("id")
                if stream_id in room._partial_streams:
                    room._partial_streams[stream_id] += event.get("delta", "")
            elif kind == "assistant_stream_replace":
                stream_id = event.get("id")
                if stream_id in room._partial_streams:
                    room._partial_streams[stream_id] = event.get("content", "")
            elif kind == "assistant_stream_end":
                # Keep the text until the child returns a durable final state.
                pass
            elif kind == "status":
                if event["status"].get("label") == "QUEUED":
                    # The child's uncontended serial lock is not server admission.
                    event = {**event, "status": {**event["status"], "label": "BUSY"}}
                room.status = event["status"]
                if not room.status.get("busy"):
                    room.human_ask_pending = False
            elif kind == "human_ask":
                room.human_ask_pending = True
                room.human_ask_message = event["message"]
                room.human_ask_is_password = event.get("is_password", False)
            for queue in room._pending_replays.values():
                queue.append(event.copy())
            recipients = tuple(room.active_connections)
        if room.loop is not None:
            asyncio.run_coroutine_threadsafe(
                room.broadcast(event, _connections=recipients), room.loop
            )

    def shutdown(self):
        self._closed.set()
        with self._lock:
            entries = list(self._running.values())
        for room, _, _, _ in entries:
            self.interrupt(room)
        deadline = time.monotonic() + 5
        for _, _, process, _ in entries:
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                process.terminate()
