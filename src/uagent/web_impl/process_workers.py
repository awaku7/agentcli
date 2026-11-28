"""Bounded, process-isolated foreground turns for independent Web rooms.

IPC is private to server-created children. Browser input is never unpickled.
The parent owns authentication, sockets and admission; each child owns cwd,
core, tools, callbacks and provider continuation for one turn. Non-sandbox
turns may run on a pooled worker that stays bound to one room across turns,
so the interpreter, imports and catalog are paid once per room instead of
once per turn; the worker is recycled on room retirement, settings change,
failure, or a turn limit, and never serves a second room.
"""

from __future__ import annotations

import atexit
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


# A pooled worker is recycled after this many turns for one room, so a
# long-lived room cannot accumulate unbounded child-process state.
_MAX_POOLED_TURNS = 200


def warm_worker_count(workers: int, cli_value: int | None = None) -> int:
    """How many pre-warmed pooled workers to keep ready (0 disables pooling)."""
    from ..env_utils import env_get

    raw = cli_value if cli_value is not None else env_get("UAGENT_WEB_WARM_WORKERS")
    if raw is None or str(raw).strip() == "":
        return min(1, workers)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("warm workers must be a non-negative integer") from exc
    if value < 0:
        raise ValueError("warm workers must be a non-negative integer")
    return min(value, workers)


class _WorkerHandle:
    """One pooled child process and its parent-side pipe."""

    __slots__ = (
        "process",
        "conn",
        "lock",
        "fingerprint",
        "turns",
        "room",
        "ready",
        "last_used",
    )

    def __init__(self, process, conn):
        self.process = process
        self.conn = conn
        self.lock = threading.Lock()
        self.fingerprint = None
        self.turns = 0
        self.room = None
        self.ready = False
        self.last_used = time.monotonic()


def _pooled_child_turn(connection, payload, pending) -> None:
    _child_turn(connection, payload, pooled=True, pending_payloads=pending)


def _external_tools_dirs_deferred() -> bool:
    """True when external-tool discovery depends on the working directory.

    Plugin discovery resolves UAGENT_EXTERNAL_TOOLS_DIRS entries
    against the process working directory, and a pooled worker only
    changes into the room's project directory when its first turn
    starts. A relative entry would therefore load the server
    directory's plugins (and cache that catalog for the worker's
    life), so discovery must wait for the first turn.
    """
    raw = (
        os.environ.get("UAGENT_EXTERNAL_TOOLS_DIRS")
        or os.environ.get("UAGENT_EXTERNAL_TOOLS_DIR")
        or ""
    )
    for entry in raw.split(os.pathsep):
        entry = entry.strip()
        if entry and not os.path.isabs(entry):
            return True
    return False


def _prewarm_child_imports(
    *, sandbox_enabled: bool = False, execution_profile: str | None = None
) -> None:
    """Load what a turn needs so a warm worker only pays for the turn.

    Importing the core modules is not enough: the first turn also loads
    the tool plugins (every tool module and its catalog) and builds a
    provider client (the provider SDK import, its optional-dependency
    check, and the model catalog lookup). Both are one-time,
    process-global costs with the same result for every later turn, so
    pay them here, before the ready signal. Each step is best-effort —
    a failure here surfaces again, unchanged, on the first real turn.
    The warmed client is discarded; turns build their own.

    The tool load is skipped when it would not match the first turn's:
    the server only warms Host tools for the local_trusted profile
    (init.py gates start_tools_warmup the same way), with server-level
    Sandbox the pooled child is only a spare (Sandbox turns use
    one-shot workers) and Host plugins must never load, and with a
    relative external-tools directory the discovery belongs to the
    room's project directory, which is only applied at turn start.
    """
    from .. import core  # noqa: F401
    from . import agent_worker, init, rooms  # noqa: F401

    if (
        not sandbox_enabled
        and execution_profile == "local_trusted"
        and not _external_tools_dirs_deferred()
    ):
        try:
            from ..tools import get_tool_specs

            get_tool_specs()
        except Exception:
            pass
    try:
        from ..providers import util_providers

        util_providers.make_client(core)
    except Exception:
        pass


def _pooled_worker_entry(
    connection,
    target=_pooled_child_turn,
    sandbox_enabled: bool = False,
    execution_profile: str | None = None,
) -> None:
    try:
        _pooled_worker_loop(
            connection,
            target,
            sandbox_enabled=sandbox_enabled,
            execution_profile=execution_profile,
        )
    finally:
        # The per-turn finish only flushes in pooled mode; the process
        # backend is shut down once, when this worker exits.
        _shutdown_worker_observability()
        _close_worker_session_store()


_POOLED_SPAWN_ENV_KEYS: set[str] | None = None
_POOLED_SYNCED_ENV_KEYS: set[str] = set()


def _apply_pooled_env_sync(payload) -> None:
    """Apply the parent's current UAGENT_* settings inside a pooled worker.

    The parent ships its UAGENT_* environment with every pooled turn
    (mode commands and :env set change only the parent's environment,
    while a pooled worker would otherwise keep its spawn-time values
    forever). Keys the worker itself set after spawn are left alone;
    only keys from its spawn-time environment or from an earlier sync
    can be removed, namely when the parent has since unset them.
    """
    sync = payload.get("uagent_env")
    if not isinstance(sync, dict):
        return
    removable = (_POOLED_SPAWN_ENV_KEYS or set()) | _POOLED_SYNCED_ENV_KEYS
    for key in removable:
        if key not in sync:
            os.environ.pop(key, None)
    for key, value in sync.items():
        if (
            isinstance(key, str)
            and key.startswith("UAGENT_")
            and isinstance(value, str)
        ):
            os.environ[key] = value
            _POOLED_SYNCED_ENV_KEYS.add(key)


def _pooled_worker_loop(
    connection,
    target,
    *,
    sandbox_enabled: bool = False,
    execution_profile: str | None = None,
) -> None:
    """Serve turns for one room at a time until stopped or recycled.

    The heavy imports run before the ready signal, so a turn claimed from
    the warm pool starts at the turn itself instead of at interpreter
    startup. Turn payloads are the same dicts the one-shot path receives
    through spawn arguments; control messages never arrive here because
    the parent only sends them while a turn is running, and the child's
    per-turn control reader hands stray payloads back through ``pending``.
    """
    import queue as queue_module

    global _POOLED_SPAWN_ENV_KEYS
    _POOLED_SPAWN_ENV_KEYS = {key for key in os.environ if key.startswith("UAGENT_")}
    pending: queue_module.SimpleQueue = queue_module.SimpleQueue()
    try:
        _prewarm_child_imports(
            sandbox_enabled=sandbox_enabled, execution_profile=execution_profile
        )
    except Exception:
        # A failed prewarm must not wedge the pool; turns will surface the
        # same failure through the normal error path.
        pass
    try:
        connection.send({"ready": True})
    except (EOFError, OSError):
        return
    while True:
        try:
            payload = pending.get_nowait()
        except queue_module.Empty:
            try:
                payload = connection.recv()
            except (EOFError, OSError):
                return
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "stop":
            return
        if "room" not in payload or "input" not in payload:
            # Stray control message between turns; nothing to do with it.
            continue
        _apply_pooled_env_sync(payload)
        try:
            target(connection, payload, pending)
        except Exception:
            # _child_turn reports turn failures itself; an exception here
            # means the child is in an unknown state, so exit and let the
            # parent recycle this worker.
            return


def _initialize_worker_observability(settings) -> bool:
    """Initialize the same resolved OTel policy in an isolated Room worker."""
    if settings is None:
        return False
    try:
        from ..runtime.observability.bootstrap import initialize_observability

        initialize_observability(settings)
        return True
    except Exception:
        return False


def _finish_worker_observability(
    send, *, initialized: bool, pooled: bool = False
) -> None:
    """Flush child spans and report the process-local export outcome to parent.

    A pooled worker keeps its process-level backend across turns, so it
    only flushes here; the worker loop shuts the backend down when the
    worker exits. A one-shot worker shuts the backend down because its
    process is about to end.
    """
    if not initialized:
        return
    try:
        from ..runtime.observability.bootstrap import get_observability_backend
        from ..runtime.observability.delivery_status import delivery_status_snapshot

        backend = get_observability_backend()
        if pooled:
            force_flush = getattr(backend, "force_flush", None)
            if callable(force_flush):
                force_flush()
        else:
            shutdown = getattr(backend, "shutdown", None)
            if callable(shutdown):
                shutdown()
        send({"otel_status": delivery_status_snapshot()})
    except Exception:
        pass


def _shutdown_worker_observability() -> None:
    """Shut the process-level backend down once, at pooled worker exit."""
    try:
        from ..runtime.observability.bootstrap import get_observability_backend

        shutdown = getattr(get_observability_backend(), "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception:
        pass


def _detach_worker_session_store(core) -> None:
    """Detach a worker's session store, restoring the log callback.

    Closing the store alone leaves the wrapper attach installed as
    ``core.log_message``; the next attach would wrap that stale callback
    and route logging into the closed store, silently losing messages.
    """
    try:
        from ..runtime.session_store import detach_opt_in_session_store

        detach_opt_in_session_store(core)
    except Exception:
        pass


def _close_worker_session_store() -> None:
    """Detach the pooled worker's session store, if one is attached."""
    try:
        from .. import core

        if getattr(core, "session_store", None) is not None:
            _detach_worker_session_store(core)
    except Exception:
        pass


def _apply_worker_observability_status(snapshot) -> None:
    """Mirror a trusted child status into the Web server's :otel snapshot."""
    if not isinstance(snapshot, dict):
        return
    state = snapshot.get("state")
    enabled = snapshot.get("enabled")
    if not isinstance(state, str) or not isinstance(enabled, bool):
        return
    try:
        from ..runtime.observability.delivery_status import update_delivery_status

        update_delivery_status(state, enabled=enabled)
    except Exception:
        pass


def _child_turn(
    connection, payload, *, pooled: bool = False, pending_payloads=None
) -> None:
    """Spawn entry point; no parent locks, SQLite handles or clients are inherited.

    With ``pooled`` the child survives the turn: the connection stays open,
    a ``turn_complete`` marker ends the turn for the parent, and the session
    store is kept open when the next turn for the same room and session can
    reuse it. ``pending_payloads`` collects turn payloads the control
    reader receives at a turn boundary so the pooled loop can run them.
    """
    from .. import core
    from ..decision.settings import configure_decision_settings
    from ..runtime.session_store import attach_opt_in_session_store
    from ..tools._tool_load_util import enable_single_tool
    from .agent_worker import run_agent_worker
    from .init import init_web
    from .rooms import WebRoom, web_manager

    from ..util_mode import set_display_reasoning

    observability_initialized = _initialize_worker_observability(
        payload.get("observability_settings")
    )

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
        existing_store = getattr(core, "session_store", None)
        reuse_store = (
            pooled
            and existing_store is not None
            and room.session_id
            and getattr(core, "session_id", None) == room.session_id
            and str(getattr(existing_store, "path", "")) == str(store_path)
        )
        if not reuse_store:
            if pooled and existing_store is not None:
                # Detach rather than just closing: attach installed a log
                # wrapper on core, and leaving it in place would route
                # the next attach's logging into the closed store.
                _detach_worker_session_store(core)
            attach_opt_in_session_store(
                core,
                project_path=room.base_dir,
                entry_point="web",
                existing_session_id=room.session_id,
            )
    else:
        os.environ["UAGENT_SESSION_STORE"] = "0"
        if pooled and getattr(core, "session_store", None) is not None:
            session_id = getattr(core, "session_id", None)
            _detach_worker_session_store(core)
            if session_id is not None:
                core.session_id = session_id
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
                if (
                    pending_payloads is not None
                    and "room" in request
                    and "input" in request
                ):
                    # A turn payload that landed at the turn boundary
                    # belongs to the pooled loop, not the control reader.
                    pending_payloads.put(request)
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

    controls_thread = threading.Thread(target=controls, daemon=True)
    controls_thread.start()
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
        from ..tools._tool_load_util import get_enabled_tool_names

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
        if pooled:
            # The control reader must be done before the pooled loop
            # resumes reading this connection: a payload it captured at
            # the turn boundary is already queued in pending_payloads,
            # and a second concurrent reader could swallow the next
            # payload into that queue while the loop blocks on recv().
            controls_thread.join(5)
        _finish_worker_observability(
            send, initialized=observability_initialized, pooled=pooled
        )
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
        loop.close()
        if pooled:
            # Drop this turn's log wrapper so the next turn does not
            # chain onto it: each wrapper retains its turn's room (and
            # its history and event loop) for the worker's whole life.
            # original_log is the session-store wrapper installed by
            # attach, which must survive across turns.
            core.log_message = original_log
            # The Sandbox RPC pipe is per turn even for a pooled worker;
            # only the control connection and the session store outlive
            # the turn. The store is not closed here: its log wrapper is
            # installed on core, and closing it would silently break the
            # next turn's persistence. It is detached when a different
            # store attaches and when the worker exits.
            if rpc_connection is not None:
                rpc_connection.close()
            try:
                send({"turn_complete": True})
            except (EOFError, OSError):
                pass
        else:
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
    def __init__(
        self,
        workers: int,
        *,
        target=_child_turn,
        pooled_target=_pooled_child_turn,
        warm_workers: int | None = None,
    ):
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
        # Pooling reuses a child process across one room's turns. It only
        # engages for the real child entry: test doubles keep the one-shot
        # behaviour, and UAGENT_WEB_WARM_WORKERS=0 is the escape hatch.
        self._pooled_target = pooled_target
        self._warm_target = (
            warm_worker_count(workers)
            if warm_workers is None
            else min(max(int(warm_workers), 0), workers)
        )
        self._pooling_enabled = (
            target is _child_turn
            and pooled_target is not None
            and self._warm_target >= 1
        )
        self._warm: list[_WorkerHandle] = []
        self._bound: dict[str, _WorkerHandle] = {}
        self._warm_lock = threading.Lock()
        self._refill_in_flight = False
        self._atexit_registered = False
        if self._pooling_enabled:
            # Pooled children wait on their pipe indefinitely and are not
            # daemonic, so interpreter exit would join them forever. The
            # atexit hook terminates them first; it is registered again
            # after the first pooled spawn (see _spawn_pooled_handle)
            # because multiprocessing registers its own exit function when
            # the first child is created, and atexit runs LIFO.
            atexit.register(self._terminate_pooled_workers)
            self._refill_async()

    def _terminate_pooled_workers(self) -> None:
        self._closed.set()
        with self._warm_lock:
            warm = list(self._warm)
            self._warm.clear()
        with self._lock:
            bound = list(self._bound.values())
            self._bound.clear()
        for handle in warm + bound:
            self._terminate_handle(handle)

    @staticmethod
    def _fingerprint(payload) -> tuple:
        return (
            payload.get("execution_profile"),
            bool(payload.get("sandbox_enabled")),
            payload.get("decision_provider"),
        )

    def _spawn_pooled_handle(self) -> _WorkerHandle:
        from .rooms import web_manager

        parent, child = self._context.Pipe()
        process = self._context.Process(
            target=_pooled_worker_entry,
            args=(
                child,
                self._pooled_target,
                bool(getattr(web_manager, "sandbox_enabled", False)),
                str(getattr(web_manager, "execution_profile", "") or "") or None,
            ),
            daemon=False,
        )
        process.start()
        child.close()
        if not self._atexit_registered:
            # Register only now: creating the first child made
            # multiprocessing register its own atexit function, and this
            # later registration is what makes the cleanup run before it.
            self._atexit_registered = True
            atexit.register(self._terminate_pooled_workers)
        return _WorkerHandle(process, parent)

    def _refill_async(self) -> None:
        with self._warm_lock:
            if (
                self._closed.is_set()
                or self._refill_in_flight
                or len(self._warm) >= self._warm_target
            ):
                return
            self._refill_in_flight = True

        def refill():
            appended = False
            try:
                handle = self._spawn_pooled_handle()
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if self._closed.is_set() or not handle.process.is_alive():
                        self._terminate_handle(handle)
                        return
                    if handle.conn.poll(0.1):
                        try:
                            message = handle.conn.recv()
                        except (EOFError, OSError):
                            self._terminate_handle(handle)
                            return
                        if isinstance(message, dict) and message.get("ready"):
                            handle.ready = True
                            with self._warm_lock:
                                if self._closed.is_set():
                                    self._terminate_handle(handle)
                                else:
                                    self._warm.append(handle)
                                    appended = True
                            return
                        self._terminate_handle(handle)
                        return
                self._terminate_handle(handle)
            except Exception:
                pass
            finally:
                with self._warm_lock:
                    self._refill_in_flight = False
                if appended:
                    # One refill adds one worker; chain until the warm
                    # target is reached (the guard in _refill_async
                    # stops the chain there, and a failed spawn does not
                    # chain, so this cannot spin).
                    self._refill_async()

        threading.Thread(target=refill, name="web-worker-refill", daemon=True).start()

    def _claim_warm(self) -> _WorkerHandle | None:
        claimed = None
        with self._warm_lock:
            while self._warm:
                handle = self._warm.pop(0)
                if handle.ready and handle.process.is_alive():
                    claimed = handle
                    break
                self._terminate_handle(handle)
        self._refill_async()
        return claimed

    def _obtain_worker(self, room, payload) -> _WorkerHandle:
        fingerprint = self._fingerprint(payload)
        with self._lock:
            handle = self._bound.get(room.room_id)
        if handle is not None:
            if (
                handle.room is room
                and handle.fingerprint == fingerprint
                and handle.process.is_alive()
            ):
                handle.last_used = time.monotonic()
                return handle
            self._unbind(room.room_id, handle)
        handle = self._claim_warm()
        if handle is None:
            handle = self._spawn_pooled_handle()
            handle.ready = True
        handle.fingerprint = fingerprint
        handle.room = room
        handle.turns = 0
        handle.last_used = time.monotonic()
        with self._lock:
            self._bound[room.room_id] = handle
        self._evict_bound_workers(keep=room.room_id)
        return handle

    def _bound_worker_cap(self) -> int:
        """How many rooms may retain a pooled worker at once."""
        return max(1, self._warm_target) + max(1, self.workers)

    def _evict_bound_workers(self, *, keep: str) -> None:
        """Evict least-recently-used idle bound workers above the cap.

        Public rooms are never retired, so without a bound their workers
        would accumulate for the life of the server. An evicted room
        keeps its history; its next turn simply claims a worker again.
        Workers running a turn are never evicted, and neither are rooms
        reserved by a run that is about to obtain their worker; the
        victim is detached under the same lock hold as its selection,
        so a concurrent acquisition can no longer hand it out.
        """
        while True:
            with self._lock:
                if len(self._bound) <= self._bound_worker_cap():
                    return
                candidates = [
                    (handle.last_used, room_id)
                    for room_id, handle in self._bound.items()
                    if room_id != keep
                    and room_id not in self._running
                    and room_id not in self._reserved_rooms
                ]
                if not candidates:
                    return
                candidates.sort()
                victim = self._bound.pop(candidates[0][1])
            self._terminate_handle(victim)

    def _terminate_handle(self, handle: _WorkerHandle) -> None:
        try:
            if handle.process.is_alive():
                handle.process.terminate()
                handle.process.join(5)
        except Exception:
            pass
        try:
            handle.conn.close()
        except Exception:
            pass

    def _unbind(self, room_id: str, handle: _WorkerHandle | None = None) -> None:
        with self._lock:
            bound = self._bound.get(room_id)
            if handle is not None and bound is not handle:
                return
            self._bound.pop(room_id, None)
        if bound is not None:
            self._terminate_handle(bound)

    def release_room(self, room) -> None:
        """Recycle the pooled worker bound to this room incarnation, if any.

        Room retirement drops the room from the manager before calling
        this, so a replacement room with the same ID may already be
        bound; only the handle bound to this exact room object goes.
        """
        with self._lock:
            handle = self._bound.get(room.room_id)
        if handle is not None and handle.room is room:
            self._unbind(room.room_id, handle)

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
        from ..runtime.observability.settings import get_observability_settings
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
        pooled_handle = None
        turn_complete_received = False
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
                from ..tools._tool_load_util import get_enabled_tool_names

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
                "observability_settings": get_observability_settings(),
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
            # Pooled workers serve one room across turns on the non-sandbox
            # path. Sandbox turns keep the one-shot spawn: their scope and
            # RPC pipe are issued per turn for a fresh child.
            if self._pooling_enabled and not payload["sandbox_enabled"]:
                pooled_handle = self._obtain_worker(room, payload)
                process = pooled_handle.process
                parent = pooled_handle.conn
                pipe_lock = pooled_handle.lock
                if self._closed.is_set():
                    # _unbind takes the pool lock; never call it under it.
                    self._unbind(room.room_id, pooled_handle)
                    return
                with self._lock:
                    with room._lifecycle_lock:
                        room._process_stale_history = room.history
                        room._process_turn_active = True
                    self._running[room.room_id] = (room, parent, process, pipe_lock)
                try:
                    with pipe_lock:
                        # Pooled workers keep the environment they were
                        # spawned with; mode commands (:r, :v) and :env set
                        # change only the parent's environment. Ship the
                        # current UAGENT_* settings with every pooled turn
                        # so the child applies them at the turn boundary.
                        payload["uagent_env"] = {
                            key: value
                            for key, value in os.environ.items()
                            if key.startswith("UAGENT_")
                        }
                        parent.send(payload)
                except (EOFError, OSError):
                    self._unbind(room.room_id, pooled_handle)
                    pooled_handle = None
                    raise
            else:
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
            rpc_closed = rpc_parent is None
            turn_complete_received = False
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
                    elif "otel_status" in value:
                        _apply_worker_observability_status(value["otel_status"])
                    elif "turn_complete" in value:
                        turn_complete_received = True
                    elif "ready" in value:
                        # A synchronously spawned pooled worker announces
                        # readiness on the same pipe before its first turn.
                        pass
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
                if pooled_handle is not None and turn_complete_received:
                    break
            if pooled_handle is None:
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
            if pooled_handle is not None:
                # A pooled worker that returned its state and the completion
                # marker stays bound to this room for the next turn; any
                # other outcome recycles it.
                keep_pooled = (
                    state_received
                    and turn_complete_received
                    and process is not None
                    and process.is_alive()
                )
                if keep_pooled:
                    pooled_handle.turns += 1
                    pooled_handle.last_used = time.monotonic()
                    if pooled_handle.turns >= _MAX_POOLED_TURNS:
                        self._unbind(room.room_id, pooled_handle)
                else:
                    self._unbind(room.room_id, pooled_handle)
            else:
                if (
                    process is not None
                    and process.pid is not None
                    and process.is_alive()
                ):
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
            elif kind == "tool_activity":
                room.current_tool = str(event.get("name") or "")[:64]
            elif kind == "status":
                if event["status"].get("label") == "QUEUED":
                    # The child's uncontended serial lock is not server admission.
                    event = {**event, "status": {**event["status"], "label": "BUSY"}}
                room.status = event["status"]
                if not room.status.get("busy"):
                    room.human_ask_pending = False
                    room.current_tool = ""
            elif kind == "human_ask":
                room.human_ask_pending = True
                room.human_ask_message = event["message"]
                room.human_ask_choices = list(event.get("choices") or [])
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
        self._terminate_pooled_workers()
