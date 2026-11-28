"""Principal- and room-scoped local messaging adapter for Web rooms."""

from __future__ import annotations

import atexit
import queue
import threading
import time
from typing import Any
from uuid import uuid4

from ..i18n import _
from ..runtime.local_messaging import (
    LocalMessageRuntime,
    accept_incoming_message,
    current_process_key,
    local_messaging_enabled,
    safe_message_preview,
    start_host_local_messaging,
    stop_host_local_messaging,
)
from ..runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
)


def _connection_for_principal(room: Any, principal_id: str) -> Any | None:
    lock = getattr(room, "_lifecycle_lock", None)
    if lock is None:
        connections = tuple(getattr(room, "_connection_contexts", {}).values())
        active = bool(getattr(room, "active_connections", []))
    else:
        with lock:
            connections = tuple(getattr(room, "_connection_contexts", {}).values())
            active = bool(getattr(room, "active_connections", []))
    if not active:
        return None
    for connection in connections:
        identity = getattr(connection, "identity", None)
        if (
            identity is not None
            and bool(getattr(identity, "authenticated", False))
            and str(getattr(identity, "principal_id", "")) == principal_id
            and str(getattr(connection, "room_id", "")) == str(room.room_id)
        ):
            return connection
    return None


def _room_project_scope(room: Any, connection: Any) -> str:
    make_turn = getattr(connection, "make_turn", None)
    if callable(make_turn):
        turn = make_turn(
            project_path=str(getattr(room, "base_dir", "") or ""),
            session_id=str(getattr(room, "session_id", "") or ""),
        )
        project_id = str(getattr(turn, "project_id", "") or "")
        if project_id:
            return project_id
    project_id = str(
        getattr(connection, "project_id", "") or getattr(room, "project_id", "") or ""
    )
    if project_id:
        return project_id
    from ..runtime.session_store import project_id_from_path

    return project_id_from_path(str(getattr(room, "base_dir", "") or ""))


class WebLocalMessagingAdapter:
    """Deliver confirmed messages only to this authenticated private room."""

    def __init__(self, room: Any, principal_id: str, project_id: str) -> None:
        self.room = room
        self.principal_id = str(principal_id)
        self.project_id = str(project_id or "")
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self._ask_cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self.runtime: LocalMessageRuntime | None = None

    def start(self) -> list[dict[str, Any]]:
        if not local_messaging_enabled():
            raise RuntimeError("UAGENT_LOCAL_MESSAGING must be enabled by the server")
        if not bool(getattr(self.room, "private_session", False)):
            raise RuntimeError("Web local messaging is available only in private rooms")
        endpoint_id = f"web:{current_process_key()}:{uuid4().hex}"
        self.runtime, peers = start_host_local_messaging(
            self.room,
            self.events,
            entrypoint="web",
            endpoint_id=endpoint_id,
            principal_id=self.principal_id,
            room_id=str(self.room.room_id),
            project_id=self.project_id,
            receive_messages=True,
            announce_peers=True,
        )
        self._thread = threading.Thread(
            target=self._run,
            name=f"uag-web-local-messaging-{str(self.room.room_id)[:8]}",
            daemon=True,
        )
        self._thread.start()
        return peers

    def stop(self) -> None:
        self._stop.set()
        self._ask_cancel.set()
        try:
            atexit.unregister(self.stop)
        except Exception:
            pass
        stop_host_local_messaging(self.room)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.runtime = None

    def list_peers(self) -> list[dict[str, Any]]:
        return self.runtime.list_peers() if self.runtime is not None else []

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                event = self.events.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self._handle_event(event)
            except Exception as exc:
                try:
                    self.room.add_message(
                        {
                            "role": "assistant",
                            "content": (
                                _("[LOCAL] Web messaging event failed: %(error_type)s.")
                                % {"error_type": type(exc).__name__}
                            ),
                        }
                    )
                except Exception:
                    pass

    def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "local_agent_started":
            peer = event.get("peer") or {}
            endpoint_id = str(peer.get("endpoint_id") or "")
            if self.runtime is None or not self.runtime.is_peer_active(endpoint_id):
                return
            self.room.add_message(
                {
                    "role": "assistant",
                    "content": (
                        _(
                            "[LOCAL] Another UAG peer is online: %(entrypoint)s (PID %(pid)s)."
                        )
                        % {
                            "entrypoint": safe_message_preview(
                                str(peer.get("entrypoint") or "UAG")
                            ),
                            "pid": peer.get("pid", "?"),
                        }
                    ),
                }
            )
            return
        if kind != "local_message_received":
            return
        message = event.get("message")
        if not isinstance(message, dict) or self.runtime is None:
            return
        # Do not interrupt a user turn or contend for its human_ask slot.
        # The runtime renews this message's claim while it remains inflight.
        while not self._stop.is_set() and self.room.worker_lock.locked():
            time.sleep(0.1)
        if self._stop.is_set():
            return
        connection = _connection_for_principal(self.room, self.principal_id)
        if connection is None:
            self.runtime.decide_message(
                str(message.get("message_id") or ""), accepted=False
            )
            return
        try:
            connection.validate_authentication_configuration()
            connection.validate_room_access(touch_activity=False)
            current_turn = connection.make_turn(
                project_path=str(self.room.base_dir),
                session_id=str(self.room.session_id or ""),
            )
            if (
                not self.room.private_session
                or current_turn.project_id != self.project_id
            ):
                raise IdentityResolutionError("Web room binding changed")
        except (IdentityConfigurationError, IdentityResolutionError):
            self.runtime.decide_message(
                str(message.get("message_id") or ""), accepted=False
            )
            return

        accepted = accept_incoming_message(self.runtime, message)
        if accepted is None:
            return
        if self._stop.is_set():
            return
        connection = _connection_for_principal(self.room, self.principal_id)
        if connection is None:
            return
        try:
            connection.validate_authentication_configuration()
            turn = connection.make_turn(
                project_path=str(self.room.base_dir),
                session_id=str(self.room.session_id or ""),
            )
            identity = connection.revalidate_identity()
            if turn.project_id != self.project_id:
                return
        except (IdentityConfigurationError, IdentityResolutionError):
            return
        from .agent_worker import run_agent_worker

        try:
            run_agent_worker(
                self.room,
                accepted["text"],
                None,
                project_path=str(self.room.base_dir),
                turn_context=turn,
                identity_context=identity,
            )
        except Exception as exc:
            self.room.add_message(
                {
                    "role": "assistant",
                    "content": (
                        _(
                            "[LOCAL] Could not start the accepted message turn: %(error_type)s."
                        )
                        % {"error_type": type(exc).__name__}
                    ),
                }
            )


def start_web_local_messaging(
    room: Any, connection: Any
) -> tuple[WebLocalMessagingAdapter, list[dict[str, Any]]]:
    project_scope = _room_project_scope(room, connection)
    current = getattr(room, "_local_messaging_adapter", None)
    if current is not None and current.runtime is not None:
        if (
            current.principal_id != str(connection.identity.principal_id)
            or current.project_id != project_scope
        ):
            raise RuntimeError(
                "This room has an endpoint bound to another identity/project; "
                "turn messaging off before re-enabling it"
            )
        return current, current.list_peers()
    if not bool(getattr(room, "private_session", False)):
        raise RuntimeError("Local messaging requires a private Web room")
    connection.validate_authentication_configuration()
    connection.validate_room_access(touch_activity=False)
    adapter = WebLocalMessagingAdapter(
        room,
        str(connection.identity.principal_id),
        project_scope,
    )
    peers = adapter.start()
    room._local_messaging_adapter = adapter
    atexit.register(adapter.stop)
    return adapter, peers


def stop_web_local_messaging(room: Any) -> bool:
    adapter = getattr(room, "_local_messaging_adapter", None)
    if adapter is None:
        return False
    try:
        adapter.stop()
    finally:
        try:
            delattr(room, "_local_messaging_adapter")
        except Exception:
            pass
    return True


def web_local_messaging_status(room: Any, connection: Any) -> list[dict[str, Any]]:
    adapter = getattr(room, "_local_messaging_adapter", None)
    if adapter is None or adapter.principal_id != str(connection.identity.principal_id):
        return []
    if not bool(getattr(room, "private_session", False)):
        raise RuntimeError("Local messaging is available only in private Web rooms")
    connection.validate_authentication_configuration()
    connection.validate_room_access(touch_activity=False)
    if adapter.project_id != _room_project_scope(room, connection):
        raise RuntimeError("Room project changed; turn messaging off and on again")
    return adapter.list_peers()


__all__ = [
    "WebLocalMessagingAdapter",
    "start_web_local_messaging",
    "stop_web_local_messaging",
    "web_local_messaging_status",
]
