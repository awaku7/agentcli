"""Bounded, process-isolated foreground turns for independent Web rooms.

IPC is private to server-created children. Browser input is never unpickled.
The parent owns authentication, sockets and admission; each child owns cwd,
core, tools, callbacks and provider continuation for one turn.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import replace as dataclass_replace
import hashlib
import json
import multiprocessing
import os
import threading
import time
from contextlib import ExitStack, contextmanager
from typing import Any

from .sandbox_rpc import (
    MAX_FRAME_BYTES,
    RPC_SCOPE_REVOKE,
    RPC_TOOL_REQUEST,
    SandboxToolRPCClient,
    decode_rpc_message,
    encode_rpc_message,
    make_tool_response,
    validate_tool_request,
)

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

    # These are parent-selected trusted startup settings, not room/request data.
    # Preserve them in the spawned worker rather than re-deriving or weakening
    # the Web execution profile in the child.
    web_manager.execution_profile = payload.get("execution_profile", "remote")
    web_manager.sandbox_enabled = bool(payload.get("sandbox_enabled", False))

    configure_decision_settings(cli_provider=payload["decision_provider"])
    set_display_reasoning(payload["display_reasoning"])
    send_lock = threading.Lock()
    finished = threading.Event()

    def send(value):
        with send_lock:
            connection.send(value)

    rpc_connection = payload.pop("sandbox_rpc_connection", None)
    rpc_send_lock = threading.Lock()

    def send_rpc(value):
        if rpc_connection is None:
            raise RuntimeError("Sandbox RPC pipe is unavailable")
        frame = encode_rpc_message(value)
        with rpc_send_lock:
            rpc_connection.send_bytes(frame)

    room = WebRoom(payload["room"]["room_id"])
    for name, value in payload["room"].items():
        setattr(room, name, value)
    # Set this after restoring serialized room data so a room field cannot
    # claim that parent-side WebSocket authorization is being enforced.
    room._web_parent_authorizes_connections = True
    sandbox_scope = payload.get("sandbox_scope")
    sandbox_rpc_client = None
    if web_manager.sandbox_enabled:
        from ..runtime.execution_broker import SandboxCapabilities, TrustedSandboxScope
        from ..runtime.mxc_backend import install_session_manager

        sandbox_capabilities = payload.get("sandbox_capabilities")
        if not isinstance(sandbox_scope, TrustedSandboxScope) or not isinstance(
            sandbox_capabilities, SandboxCapabilities
        ):
            raise RuntimeError("trusted parent Sandbox scope/capabilities are missing")
        room._sandbox_scope_generation = sandbox_scope.binding_generation
        sandbox_rpc_client = SandboxToolRPCClient(
            scope=sandbox_scope,
            capabilities=sandbox_capabilities,
            send=send_rpc,
        )
        install_session_manager(sandbox_rpc_client)
        web_manager.sandbox_session_manager = sandbox_rpc_client

        def receive_sandbox_rpc_responses():
            while not finished.is_set():
                try:
                    if rpc_connection is None or not rpc_connection.poll(0.1):
                        continue
                    raw = rpc_connection.recv_bytes(MAX_FRAME_BYTES)
                    sandbox_rpc_client.deliver_response(decode_rpc_message(raw))
                except (EOFError, OSError, ValueError):
                    sandbox_rpc_client.close_all()
                    return

        threading.Thread(
            target=receive_sandbox_rpc_responses,
            name="web-sandbox-rpc-reader",
            daemon=True,
        ).start()
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
    from ..runtime.execution_broker import SecurityProfile, execution_profile
    from ..runtime.runtime_plugins import load_plugins_status_at_startup

    _profile = (
        SecurityProfile.LOCAL_TRUSTED
        if web_manager.execution_profile == "local_trusted"
        else SecurityProfile.REMOTE
    )
    with execution_profile(
        _profile,
        sandbox_enabled=web_manager.sandbox_enabled,
    ):
        load_plugins_status_at_startup(
            activate=(
                web_manager.execution_profile == "local_trusted"
                and not web_manager.sandbox_enabled
            )
        )
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

    async def broadcast(event, *, _connections=None):
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
                if not isinstance(request, dict):
                    continue
                request_type = request.get("type")
                if request_type == "interrupt":
                    with core.interrupt_lock:
                        core.interrupt_requested = True
                    room.human_ask_cancelled = True
                    room.human_ask_sync_event.set()
                elif request_type == "answer" and room.human_ask_pending:
                    room.human_ask_result = request.get("text", "")
                    room.human_ask_cancelled = False
                    room.human_ask_sync_event.set()
                elif request_type == "connected":
                    room.active_connections = [True] if request.get("value") else []
            except (EOFError, OSError):
                with core.interrupt_lock:
                    core.interrupt_requested = True
                break

    threading.Thread(target=controls, daemon=True).start()
    if room.private_session or not room.session_id:
        for name in (
            "responses_state",
            "tool_context",
            "agent_state_manager",
            "mcp_request_generation",
        ):
            if hasattr(room, name):
                setattr(core, name, getattr(room, name))
    try:
        if payload.get("bootstrap_only"):
            from ..runtime.identity_context import call_with_turn_context
            from ..runtime.turn_context_runtime import call_with_resolved_turn_context
            from .history import _ensure_room_history_initialized

            turn_context = payload.get("turn_context")
            identity_context = payload.get("identity_context")
            if turn_context is not None:
                call_with_turn_context(
                    turn_context,
                    _ensure_room_history_initialized,
                    room,
                    identity_context=identity_context,
                )
            else:
                call_with_resolved_turn_context(
                    _ensure_room_history_initialized,
                    room,
                    entry_point="web",
                    room_id=str(room.room_id),
                    project_path=str(room.base_dir),
                    session_id=str(room.session_id or ""),
                )
        else:
            run_agent_worker(
                room,
                payload["input"],
                payload["attachments"],
                turn_context=payload["turn_context"],
                identity_context=payload["identity_context"],
                project_path=payload["project_path"],
                sandbox_scope_override=sandbox_scope,
                client_message_id=payload.get("client_message_id", ""),
            )
        if room.private_session or not room.session_id:
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
        if sandbox_rpc_client is not None:
            sandbox_rpc_client.close_all()
            try:
                from ..runtime.mxc_backend import (
                    current_session_manager,
                    install_session_manager,
                )

                if current_session_manager() is sandbox_rpc_client:
                    install_session_manager(None)
                web_manager.sandbox_session_manager = None
            except Exception:
                pass
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(5)
        connection.close()
        if rpc_connection is not None:
            rpc_connection.close()
        store = getattr(core, "session_store", None)
        if store is not None:
            store.close()


def _spawn_worker_entry(target, connection, payload, rpc_connection) -> None:
    """Start one trusted worker with a separate, bounded JSON Sandbox RPC pipe."""
    payload["sandbox_rpc_connection"] = rpc_connection
    target(connection, payload)


class RoomWorkerPool:
    def __init__(self, workers: int, *, target=_child_turn):
        if workers < 1:
            raise ValueError("room workers must be at least 1")
        self.workers = workers
        self._slots = threading.BoundedSemaphore(workers)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._running: dict[str, tuple[Any, Any, Any, threading.Lock]] = {}
        self._reserved_rooms: set[str] = set()
        self._busy_event = threading.Event()
        self._target = target
        self._context = multiprocessing.get_context("spawn")

    @property
    def busy(self) -> bool:
        return self._busy_event.is_set()

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

    def bootstrap(self, room, **kwargs):
        """Initialize a Web room in its isolated worker before accepting turns."""
        return self.run(room, "", None, _bootstrap_only=True, **kwargs)

    def _sandbox_tool_response(self, room, scope, message):
        from ..runtime.execution_broker import (
            SecurityProfile,
            current_authorization_valid,
            current_profile,
            current_sandbox_enabled,
            current_scope,
        )
        from ..runtime.mxc_backend import current_session_manager
        from .rooms import web_manager

        request_id = message.get("request_id") if isinstance(message, dict) else None
        if not isinstance(request_id, str) or not request_id or len(request_id) > 64:
            return None
        try:
            request_id, name, args = validate_tool_request(message)
        except ValueError:
            return make_tool_response(
                request_id, "[sandbox policy] malformed Sandbox tool request"
            )

        manager = getattr(web_manager, "sandbox_session_manager", None)
        if (
            current_profile()
            not in {SecurityProfile.LOCAL_TRUSTED, SecurityProfile.REMOTE}
            or not current_sandbox_enabled()
            or scope is None
            or current_scope() != scope
            or manager is None
            or current_session_manager() is not manager
        ):
            return make_tool_response(
                request_id, "[sandbox policy] Sandbox tool broker is unavailable"
            )
        if (
            room.current_sandbox_scope() != scope
            or room.sandbox_scope_generation() != scope.binding_generation
        ):
            return make_tool_response(
                request_id, "[sandbox policy] Room Sandbox scope is stale"
            )
        if not current_authorization_valid(require_check=True):
            web_manager.release_room_sandbox_scope(room, expected_scope=scope)
            return make_tool_response(
                request_id,
                "[tool policy] current Room authorization is no longer valid",
            )
        try:
            result = manager.run_tool(scope, name, args)
        except Exception as exc:
            result = f"[sandbox error] broker execution failed: {type(exc).__name__}"
        if not isinstance(result, str):
            result = str(result)
        return make_tool_response(request_id, result)

    def _handle_sandbox_scope_revoke(self, room, scope, message) -> None:
        from .rooms import web_manager

        if (
            scope is None
            or not isinstance(message, dict)
            or set(message) != {"type", "scope_id", "binding_generation"}
            or message.get("type") != RPC_SCOPE_REVOKE
            or message.get("scope_id") != scope.scope_id
            or message.get("binding_generation") != scope.binding_generation
            or room.current_sandbox_scope() != scope
        ):
            return
        web_manager.release_room_sandbox_scope(room, expected_scope=scope)

    def run(self, room, user_input, attachments=None, **kwargs):
        from .. import core
        from ..i18n import _
        from ..decision.settings import get_decision_settings
        from ..util_mode import get_display_reasoning
        from .agent_worker import (
            _ensure_public_room_session,
            _web_turn_execution_context,
        )
        from .rooms import web_manager

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
        with room._lifecycle_lock:
            room._partial_streams = {}
            room._ended_streams.clear()
        acquired = False
        process = None
        parent = child = rpc_parent = rpc_child = None
        sandbox_scope = None
        sandbox_capabilities = None
        sandbox_execution_stack = ExitStack()
        pipe_lock = threading.Lock()
        bootstrap_only = bool(kwargs.pop("_bootstrap_only", False))
        try:
            with self._lock:
                if self._closed.is_set():
                    return
                self._reserved_rooms.add(room.room_id)
                self._busy_event.set()
            acquired = self._slots.acquire(blocking=False)
            if not acquired:
                room.set_status(True, "QUEUED")
                while not self._closed.is_set():
                    if self._slots.acquire(timeout=0.1):
                        acquired = True
                        break
            if not acquired or self._closed.is_set():
                return
            room.set_status(True, "QUEUED")
            store = getattr(core, "session_store", None)
            if store is not None and not room.private_session:
                bound_session_id = _ensure_public_room_session(
                    room, store, room.base_dir
                )
                if kwargs.get("turn_context") is not None:
                    kwargs["turn_context"] = dataclass_replace(
                        kwargs["turn_context"], session_id=bound_session_id
                    )
            if bool(getattr(web_manager, "sandbox_enabled", False)):
                sandbox_execution_stack.enter_context(
                    _web_turn_execution_context(
                        room,
                        kwargs.get("turn_context"),
                        kwargs.get("identity_context"),
                        kwargs.get("project_path"),
                    )
                )
                from ..runtime.execution_broker import current_scope

                sandbox_scope = current_scope()
                manager = getattr(web_manager, "sandbox_session_manager", None)
                sandbox_capabilities = getattr(manager, "capabilities", None)
                if (
                    sandbox_scope is None
                    or manager is None
                    or sandbox_capabilities is None
                ):
                    raise RuntimeError("Web Sandbox broker is not ready")
                web_manager.bind_sandbox_scope(room, sandbox_scope)
            if getattr(
                web_manager, "execution_profile", "remote"
            ) == "local_trusted" and not bool(
                getattr(web_manager, "sandbox_enabled", False)
            ):
                from ..tools._genre_control_util import get_enabled_tool_names

                parent_tools = get_enabled_tool_names()
                tool_names = (
                    room._worker_tool_names
                    if getattr(room, "_worker_parent_tool_names", None) == parent_tools
                    else parent_tools
                )
            else:
                # Remote Web never loads or advertises Host tool runners; with
                # Sandbox off it stays tool-less, while Sandbox-on uses static specs.
                parent_tools = []
                tool_names = []
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
                "connected": bool(
                    room.active_connections or room._bootstrapping_connections
                ),
                "turn_context": kwargs.get("turn_context"),
                "identity_context": kwargs.get("identity_context"),
                "project_path": kwargs.get("project_path"),
                "client_message_id": kwargs.get("client_message_id", ""),
                "bootstrap_only": bootstrap_only,
                "execution_profile": getattr(
                    web_manager, "execution_profile", "remote"
                ),
                "sandbox_enabled": bool(getattr(web_manager, "sandbox_enabled", False)),
                "sandbox_scope": sandbox_scope,
                "sandbox_capabilities": sandbox_capabilities,
            }
            payload["core"].update(getattr(room, "_worker_auto_pilot", {}))
            parent, child = self._context.Pipe()
            rpc_parent, rpc_child = self._context.Pipe()
            process = self._context.Process(
                target=_spawn_worker_entry,
                args=(self._target, child, payload, rpc_child),
                daemon=False,
            )
            with self._lock:
                if self._closed.is_set():
                    return
                with room._lifecycle_lock:
                    room._process_stale_history = room.history
                    room._process_turn_active = True
                process.start()
                self._running[room.room_id] = (room, parent, process, pipe_lock)
            child.close()
            rpc_child.close()
            # Do not expose Stop as available until interrupt() can reach the child.
            room.set_status(True, "BUSY")
            connected = payload["connected"]
            rpc_closed = False
            process_exit_deadline = None
            while True:
                try:
                    event_ready = parent.poll(0.1)
                except (EOFError, OSError):
                    break
                if rpc_closed:
                    rpc_ready = False
                else:
                    try:
                        rpc_ready = rpc_parent.poll(0)
                    except (EOFError, OSError):
                        rpc_closed = True
                        rpc_ready = False
                if rpc_ready:
                    try:
                        raw_rpc = rpc_parent.recv_bytes(MAX_FRAME_BYTES)
                    except EOFError:
                        rpc_closed = True
                    except OSError:
                        if process.is_alive():
                            process.terminate()
                        break
                    else:
                        try:
                            rpc_message = decode_rpc_message(raw_rpc)
                        except ValueError:
                            if process.is_alive():
                                process.terminate()
                            break
                        if rpc_message.get("type") == RPC_TOOL_REQUEST:
                            response = self._sandbox_tool_response(
                                room, sandbox_scope, rpc_message
                            )
                            if response is None:
                                if process.is_alive():
                                    process.terminate()
                                break
                            try:
                                rpc_parent.send_bytes(encode_rpc_message(response))
                            except (EOFError, OSError, ValueError):
                                if process.is_alive():
                                    process.terminate()
                                break
                        elif rpc_message.get("type") == RPC_SCOPE_REVOKE:
                            self._handle_sandbox_scope_revoke(
                                room, sandbox_scope, rpc_message
                            )
                        else:
                            if process.is_alive():
                                process.terminate()
                            break
                if event_ready:
                    try:
                        value = parent.recv()
                    except (EOFError, OSError):
                        break
                    if not isinstance(value, dict):
                        if process.is_alive():
                            process.terminate()
                        break
                    if "state" in value:
                        state = value["state"]
                        if not isinstance(state, dict):
                            room.add_message(
                                {
                                    "role": "assistant",
                                    "content": "[ERROR] Room worker returned malformed state.",
                                }
                            )
                            if process.is_alive():
                                process.terminate()
                            break
                        unexpected = set(state).difference(ROOM_FIELDS)
                        if state.get("room_id") != room.room_id or unexpected:
                            room.add_message(
                                {
                                    "role": "assistant",
                                    "content": (
                                        "[ERROR] Room worker returned mismatched state "
                                        f"(room_id_match={state.get('room_id') == room.room_id}, "
                                        f"unexpected_fields={sorted(unexpected)})."
                                    ),
                                }
                            )
                            if process.is_alive():
                                process.terminate()
                            break
                        with room._lifecycle_lock:
                            for name, item in state.items():
                                if name != "room_id":
                                    setattr(room, name, item)
                        state_received = True
                    elif "event" in value and isinstance(value["event"], dict):
                        self._relay(room, value["event"])
                    else:
                        if process.is_alive():
                            process.terminate()
                        break
                elif not rpc_ready and not process.is_alive():
                    if process_exit_deadline is None:
                        process_exit_deadline = time.monotonic() + 1.0
                    elif time.monotonic() >= process_exit_deadline:
                        break
                else:
                    process_exit_deadline = None
                current_connected = bool(
                    room.active_connections or room._bootstrapping_connections
                )
                if current_connected != connected:
                    self._send(room, {"type": "connected", "value": current_connected})
                    connected = current_connected
            process.join(5)
            if not state_received:
                room.recover_partial_streams(
                    "[ERROR] Room worker exited before returning its state "
                    f"(exit code {process.exitcode})."
                )
        except Exception as exc:
            room.add_message(
                {"role": "assistant", "content": f"[ERROR] Room worker failed: {exc}"}
            )
        finally:
            try:
                sandbox_execution_stack.close()
            except Exception:
                pass
            with self._lock:
                self._running.pop(room.room_id, None)
                self._reserved_rooms.discard(room.room_id)
                if not self._reserved_rooms:
                    self._busy_event.clear()
            if process is not None and process.pid is not None and process.is_alive():
                process.terminate()
                process.join(5)
            for pipe in (parent, child, rpc_parent, rpc_child):
                if pipe is not None:
                    pipe.close()
            with room._lifecycle_lock:
                room._partial_streams = {}
                room._ended_streams.clear()
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
        # This field is private child-to-parent authorization metadata. Never
        # forward it to WebSocket clients.
        event = dict(event)
        ask_principal_id = event.pop("_authorization_principal_id", None)
        ask_job_id = event.pop("_authorization_job_id", None)
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
                room._ended_streams.discard(event["id"])
            elif kind == "assistant_stream_delta":
                stream_id = event.get("id")
                if stream_id in room._partial_streams:
                    room._partial_streams[stream_id] += event.get("delta", "")
            elif kind == "assistant_stream_replace":
                stream_id = event.get("id")
                if stream_id in room._partial_streams:
                    room._partial_streams[stream_id] = event.get("content", "")
            elif kind == "assistant_stream_end":
                # Retain text for crash recovery, but replay its ended state.
                room._ended_streams.add(event["id"])
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
                room._human_ask_expected_principal_id = str(ask_principal_id or "")
                room.human_ask_job_id = str(ask_job_id or "")
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
                process.join(5)
