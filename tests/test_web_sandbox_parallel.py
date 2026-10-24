from __future__ import annotations

import threading

import pytest


def _sandbox_real_worker_child(connection, payload):
    """Exercise _child_turn, the real tool dispatcher, and parent MXC RPC."""
    from uagent import core
    from uagent.runtime import runtime_plugins
    from uagent.web_impl import agent_worker
    from uagent.web_impl.process_workers import _child_turn

    runtime_plugins.load_plugins_status_at_startup = lambda **kwargs: ([], "")
    agent_worker._web_turn_authorization_valid = lambda *args: True
    agent_worker.providers.make_client = lambda bound_core: ("openai", None, "offline")

    def run_rounds(provider, client, model, history, **kwargs):
        from uagent import tools

        result = tools.run_tool("file_exists", {"path": "parallel-smoke.txt"})
        message = {"role": "assistant", "content": result}
        core.log_message(message)
        history.append(message)

    agent_worker.llm_util.run_llm_rounds = run_rounds
    _child_turn(connection, payload)


class _ParallelSandboxManager:
    def __init__(self):
        from uagent.runtime.execution_broker import (
            IsolationLevel,
            SandboxCapabilities,
            SandboxCapability,
        )

        self.capabilities = SandboxCapabilities(
            isolation_level=IsolationLevel.CONTAINER,
            available=frozenset(SandboxCapability),
        )
        self.barrier = threading.Barrier(2, timeout=8)
        self._lock = threading.Lock()
        self._scopes = set()
        self._active_calls = 0
        self.peak_active_calls = 0
        self.seen_scopes = []

    def activate_scope(self, scope):
        with self._lock:
            self._scopes.add(scope)

    def revoke_scope(self, scope):
        with self._lock:
            self._scopes.discard(scope)
        return None

    def run_tool(self, scope, name, args):
        if name != "file_exists" or args != {"path": "parallel-smoke.txt"}:
            return "[sandbox policy] unexpected test request"
        with self._lock:
            if scope not in self._scopes:
                return "[sandbox error] test scope is not active"
            self._active_calls += 1
            self.peak_active_calls = max(self.peak_active_calls, self._active_calls)
            self.seen_scopes.append(scope)
        try:
            self.barrier.wait()
            return f"brokered:{scope.scope_id}"
        except threading.BrokenBarrierError:
            return "[test error] Room tool requests did not overlap"
        finally:
            with self._lock:
                self._active_calls -= 1


def _trusted_turn(room_id: str, project_id: str, *, authn_kind: str = "local"):
    from uagent.runtime.identity_context import IdentityContext, TurnContext

    identity = IdentityContext(
        principal_id="local-smoke-user",
        authenticated=True,
        authn_kind=authn_kind,
    )
    turn = TurnContext.from_identity(
        identity,
        room_id=room_id,
        project_id=project_id,
        session_id="",
        entry_point="web",
        private_session=True,
        server_bound_project=True,
    )
    return turn, identity


def test_local_web_sandbox_workers_broker_tools_in_parallel_across_rooms(
    monkeypatch, tmp_path
):
    from uagent import core
    from uagent.runtime import mxc_backend
    from uagent.web_impl import agent_worker
    from uagent.web_impl.process_workers import RoomWorkerPool
    from uagent.web_impl.rooms import WebRoom, web_manager

    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    manager = _ParallelSandboxManager()
    monkeypatch.setattr(
        web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)
    monkeypatch.setattr(web_manager, "sandbox_session_manager", manager, raising=False)
    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: manager)
    monkeypatch.setattr(
        agent_worker, "_web_turn_authorization_valid", lambda *args: True
    )

    pool = RoomWorkerPool(2, target=_sandbox_real_worker_child)
    rooms = [WebRoom("parallel-room-a"), WebRoom("parallel-room-b")]
    contexts = []
    for index, room in enumerate(rooms):
        room.private_session = True
        room.base_dir = str(tmp_path)
        turn, identity = _trusted_turn(room.room_id, f"project-{index}")
        contexts.append((turn, identity))

    results = [None, None]
    failures = []

    def run_room(index):
        room = rooms[index]
        turn, identity = contexts[index]
        try:
            pool.run(
                room,
                "check sandbox RPC",
                [],
                turn_context=turn,
                identity_context=identity,
                project_path=str(tmp_path),
            )
            results[index] = next(
                (
                    message.get("content")
                    for message in reversed(room.messages)
                    if message.get("role") == "assistant"
                ),
                None,
            )
        except Exception as exc:  # pragma: no cover - diagnostic on thread failure
            failures.append(exc)

    threads = [threading.Thread(target=run_room, args=(index,)) for index in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        assert not any(thread.is_alive() for thread in threads)
        assert failures == []
        assert all(isinstance(result, str) for result in results), [
            room.messages for room in rooms
        ]
        assert all(result.startswith("brokered:") for result in results), results
        assert manager.peak_active_calls == 2
        assert len({scope.scope_id for scope in manager.seen_scopes}) == 2
        assert rooms[0].current_sandbox_scope() != rooms[1].current_sandbox_scope()
    finally:
        pool.shutdown()
        for room in rooms:
            web_manager.release_room_sandbox_scope(room)


def test_parent_sandbox_broker_revalidates_room_authorization(monkeypatch, tmp_path):
    from uagent import core
    from uagent.runtime import mxc_backend
    from uagent.web_impl import agent_worker
    from uagent.web_impl.process_workers import RoomWorkerPool
    from uagent.web_impl.rooms import WebRoom, web_manager

    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    manager = _ParallelSandboxManager()
    monkeypatch.setattr(
        web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)
    monkeypatch.setattr(web_manager, "sandbox_session_manager", manager, raising=False)
    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: manager)
    monkeypatch.setattr(
        agent_worker, "_web_turn_authorization_valid", lambda *args: False
    )

    room = WebRoom("authorization-revoked-room")
    room.private_session = True
    room.base_dir = str(tmp_path)
    turn, identity = _trusted_turn(room.room_id, "authorization-project")
    pool = RoomWorkerPool(1, target=_sandbox_real_worker_child)
    try:
        pool.run(
            room,
            "try sandbox tool",
            [],
            turn_context=turn,
            identity_context=identity,
            project_path=str(tmp_path),
        )
        assistant_result = next(
            message.get("content")
            for message in reversed(room.messages)
            if message.get("role") == "assistant"
        )
        assert "authorization is no longer valid" in assistant_result
        assert manager.seen_scopes == []
        assert room.current_sandbox_scope() is None
    finally:
        pool.shutdown()
        web_manager.release_room_sandbox_scope(room)


def test_remote_web_sandbox_workers_use_authenticated_mxc_scopes(monkeypatch, tmp_path):
    from uagent import core
    from uagent.runtime import mxc_backend
    from uagent.web_impl import agent_worker
    from uagent.web_impl.process_workers import RoomWorkerPool
    from uagent.web_impl.rooms import WebRoom, web_manager

    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    manager = _ParallelSandboxManager()
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)
    monkeypatch.setattr(web_manager, "sandbox_session_manager", manager, raising=False)
    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: manager)
    monkeypatch.setattr(
        agent_worker, "_web_turn_authorization_valid", lambda *args: True
    )

    pool = RoomWorkerPool(2, target=_sandbox_real_worker_child)
    rooms = [WebRoom("remote-room-a"), WebRoom("remote-room-b")]
    contexts = []
    for index, room in enumerate(rooms):
        room.private_session = True
        room.base_dir = str(tmp_path)
        turn, identity = _trusted_turn(
            room.room_id, f"remote-project-{index}", authn_kind="oidc"
        )
        contexts.append((turn, identity))

    results = [None, None]
    failures = []

    def run_room(index):
        room = rooms[index]
        turn, identity = contexts[index]
        try:
            pool.run(
                room,
                "check remote sandbox RPC",
                [],
                turn_context=turn,
                identity_context=identity,
                project_path=str(tmp_path),
            )
            results[index] = next(
                (
                    message.get("content")
                    for message in reversed(room.messages)
                    if message.get("role") == "assistant"
                ),
                None,
            )
        except Exception as exc:  # pragma: no cover - diagnostic on thread failure
            failures.append(exc)

    threads = [threading.Thread(target=run_room, args=(index,)) for index in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        assert not any(thread.is_alive() for thread in threads)
        assert failures == []
        assert all(isinstance(result, str) for result in results), [
            room.messages for room in rooms
        ]
        assert all(result.startswith("brokered:") for result in results), results
        assert manager.peak_active_calls == 2
        assert len({scope.scope_id for scope in manager.seen_scopes}) == 2
        assert all(scope.scope_kind == "web-room" for scope in manager.seen_scopes)
    finally:
        pool.shutdown()
        for room in rooms:
            web_manager.release_room_sandbox_scope(room)


def _malformed_room_state_child(connection, payload):
    connection.send(
        {
            "state": {
                "room_id": payload["room"]["room_id"],
                "is_admin": True,
            }
        }
    )
    connection.close()


def test_spawned_worker_cannot_mutate_unlisted_room_state(monkeypatch, tmp_path):
    from uagent import core
    from uagent.web_impl.process_workers import RoomWorkerPool
    from uagent.web_impl.rooms import WebRoom, web_manager

    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)
    monkeypatch.setattr(core, "session_store", None, raising=False)
    room = WebRoom("malformed-worker-state")
    room.private_session = True
    room.base_dir = str(tmp_path)
    pool = RoomWorkerPool(1, target=_malformed_room_state_child)
    try:
        pool.run(room, "state validation")
        assert not hasattr(room, "is_admin")
        assert any(
            "unexpected_fields=['is_admin']" in message.get("content", "")
            for message in room.messages
        )
    finally:
        pool.shutdown()
    assert not room.worker_lock.locked()


def test_sandbox_room_workers_are_capped_by_mxc_session_capacity():
    from uagent.runtime.mxc_backend import MAX_ACTIVE_SESSIONS
    from uagent.web_impl.init import _sandbox_room_worker_limit

    assert _sandbox_room_worker_limit(2) == 2
    assert _sandbox_room_worker_limit(MAX_ACTIVE_SESSIONS + 1) == (MAX_ACTIVE_SESSIONS)


def test_sandbox_rpc_rejects_unapproved_tools_and_oversized_frames(monkeypatch):
    from uagent.runtime.mxc_backend import MAX_FRAME_BYTES
    from uagent.web_impl.sandbox_rpc import (
        decode_rpc_message,
        encode_rpc_message,
        make_tool_response,
        validate_tool_request,
    )

    oversized_response = make_tool_response("r" * 64, "x" * MAX_FRAME_BYTES)
    assert oversized_response["result"].startswith("[sandbox error]")
    assert len(encode_rpc_message(oversized_response)) <= MAX_FRAME_BYTES

    with pytest.raises(ValueError, match="UTF-8 JSON"):
        decode_rpc_message(b"\x80\x04N.")

    with pytest.raises(ValueError, match="invalid sandbox RPC request fields"):
        validate_tool_request(
            {
                "type": "sandbox_tool_request",
                "request_id": "rpc-1",
                "name": "pwsh_exec",
                "args": {"command": "whoami"},
            }
        )

    with pytest.raises(ValueError, match="IPC frame limit"):
        validate_tool_request(
            {
                "type": "sandbox_tool_request",
                "request_id": "rpc-2",
                "name": "create_file",
                "args": {"content": "x" * (MAX_FRAME_BYTES + 1)},
            }
        )

    from uagent.web_impl import sandbox_rpc

    original_dumps = sandbox_rpc.json.dumps

    def raise_recursion(*args, **kwargs):
        raise RecursionError("test recursion boundary")

    monkeypatch.setattr(sandbox_rpc.json, "dumps", raise_recursion)
    with pytest.raises(ValueError, match="JSON values"):
        validate_tool_request(
            {
                "type": "sandbox_tool_request",
                "request_id": "rpc-3",
                "name": "file_exists",
                "args": {"path": "safe.txt"},
            }
        )

    monkeypatch.setattr(sandbox_rpc.json, "dumps", original_dumps)
    monkeypatch.setattr(sandbox_rpc.json, "loads", raise_recursion)
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        decode_rpc_message(b"{}")
