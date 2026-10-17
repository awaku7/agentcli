from __future__ import annotations

import sqlite3
import time

import pytest

from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.room_access import RoomAccessPolicy
from uagent.runtime.session_store import SessionStore, SessionStoreError
from uagent.web_impl.rooms import WebManager


def test_idle_room_eviction_preserves_reconnect_grace_period():
    manager = WebManager()
    room = manager.get_room("room-a")
    room.private_session = True
    room.last_activity = 100.0

    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=129.0) == []
    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=130.0) == ["room-a"]
    assert "room-a" not in manager.rooms


def test_recreated_web_room_gets_a_distinct_sandbox_scope_generation():
    from uagent.runtime.mxc_backend import local_web_room_scope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    old_room = manager.get_room("reused-room-id")
    old_room.private_session = True
    old_room.last_activity = 100.0
    old_scope = local_web_room_scope(
        principal_id="alice",
        project_id="project-a",
        room_id=old_room.room_id,
        room_generation=old_room._sandbox_scope_generation,
    )
    manager.bind_sandbox_scope(old_room, old_scope)

    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=130.0) == [
        "reused-room-id"
    ]
    new_room = manager.get_room("reused-room-id")
    new_scope = local_web_room_scope(
        principal_id="alice",
        project_id="project-a",
        room_id=new_room.room_id,
        room_generation=new_room._sandbox_scope_generation,
    )
    manager.bind_sandbox_scope(new_room, new_scope)

    assert old_scope.scope_id != new_scope.scope_id
    assert closed_scopes == [old_scope]
    assert new_room.current_sandbox_scope() == new_scope


def test_idle_public_room_cleanup_releases_lease_but_preserves_room_history():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    active_scopes = set()
    closed_scopes = []

    class FakeSandboxManager:
        def run_tool(self, scope, _name, _args):
            if scope not in active_scopes and len(active_scopes) >= 4:
                return "active session limit reached; restart UAG"
            active_scopes.add(scope)
            return "isolated"

        def close_scope(self, scope):
            active_scopes.discard(scope)
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    public_rooms = []
    for index in range(4):
        room = manager.get_room(f"public-room-{index}")
        room.messages.append({"role": "user", "content": f"history-{index}"})
        room.active_connections.append(object())
        room.disconnect(room.active_connections[0])
        room.last_activity = 100.0
        scope = TrustedSandboxScope(
            deployment_id="web",
            principal_id="local-user",
            project_id="project-a",
            scope_kind="web-room",
            scope_id=f"public-room-{index}-scope",
        )
        manager.bind_sandbox_scope(room, scope)
        assert manager.sandbox_session_manager.run_tool(scope, "file_exists", {}) == (
            "isolated"
        )
        public_rooms.append((room, scope))

    fifth_scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="public-room-fifth-scope",
    )
    assert "active session limit" in manager.sandbox_session_manager.run_tool(
        fifth_scope, "file_exists", {}
    )

    assert (
        manager.release_idle_public_room_sandbox_scopes(idle_ttl_seconds=30, now=129.0)
        == 0
    )
    assert (
        manager.release_idle_public_room_sandbox_scopes(idle_ttl_seconds=30, now=130.0)
        == 4
    )
    assert len(closed_scopes) == 4
    assert (
        manager.sandbox_session_manager.run_tool(fifth_scope, "file_exists", {})
        == "isolated"
    )
    for index, (room, scope) in enumerate(public_rooms):
        assert manager.rooms[room.room_id] is room
        assert room.messages == [{"role": "user", "content": f"history-{index}"}]
        assert room.current_sandbox_scope() is None
        assert scope in closed_scopes


def test_idle_public_room_scope_is_retained_while_job_is_running():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    class FakeJobs:
        def running_count_for_room(self, room_id):
            assert room_id == "public-room"
            return 1

    manager.sandbox_session_manager = FakeSandboxManager()
    manager.sub_agent_job_manager = FakeJobs()
    room = manager.get_room("public-room")
    room.last_activity = 100.0
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="public-room-scope",
    )
    manager.bind_sandbox_scope(room, scope)

    assert (
        manager.release_idle_public_room_sandbox_scopes(idle_ttl_seconds=30, now=1000.0)
        == 0
    )
    assert room.current_sandbox_scope() == scope
    assert closed_scopes == []


@pytest.mark.parametrize("sqlite_backend", [False, True])
def test_periodic_room_cleanup_releases_idle_public_leases(monkeypatch, sqlite_backend):
    import asyncio

    from uagent.runtime.execution_broker import TrustedSandboxScope
    from uagent.web_impl import routes_api

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    room = manager.get_room("public-room")
    room.last_activity = time.monotonic() - 3600
    monkeypatch.setattr(manager, "idle_ttl_seconds", lambda: 30)
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="public-room-scope",
    )
    manager.bind_sandbox_scope(room, scope)
    monkeypatch.setattr(routes_api, "web_manager", manager)
    monkeypatch.setattr(
        routes_api._long_memory_mod,
        "is_sqlite_backend",
        lambda: sqlite_backend,
    )
    monkeypatch.setattr(routes_api, "_cleanup_expired_private_rooms", lambda: [])

    async def stop_after_one_pass(_delay):
        raise asyncio.CancelledError

    monkeypatch.setattr(routes_api.asyncio, "sleep", stop_after_one_pass)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(routes_api._private_room_cleanup_loop())

    assert closed_scopes == [scope]
    assert manager.rooms["public-room"] is room
    assert room.current_sandbox_scope() is None


def test_idle_private_room_eviction_leaves_non_private_rooms_unchanged():
    manager = WebManager()
    room = manager.get_room("local-room")
    room.last_activity = 100.0

    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=1000.0) == []
    assert manager.rooms["local-room"] is room


def test_get_room_refreshes_idle_activity():
    manager = WebManager()
    room = manager.get_room("room-a")
    room.private_session = True
    room.last_activity = time.monotonic() - 1000

    assert manager.get_room("room-a") is room
    assert manager.evict_idle_rooms(idle_ttl_seconds=60) == []


@pytest.mark.parametrize("protection", ["connection", "worker", "busy", "human_ask"])
def test_idle_room_eviction_preserves_active_work(protection):
    manager = WebManager()
    room = manager.get_room("room-a")
    room.private_session = True
    room.last_activity = 100.0
    if protection == "connection":
        room.active_connections.append(object())
    elif protection == "worker":
        room.worker_lock.acquire()
    elif protection == "busy":
        room.status["busy"] = True
    elif protection == "human_ask":
        room.human_ask_pending = True

    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=1000.0) == []
    assert manager.rooms["room-a"] is room
    if protection == "worker":
        room.worker_lock.release()


def test_expired_private_room_cleanup_removes_session_and_room_binding(
    tmp_path, monkeypatch
):
    from uagent.web_impl import routes_api

    memory_path = tmp_path / "memory.sqlite3"
    sessions_path = tmp_path / "sessions.sqlite3"
    memory = MemoryStore(memory_path)
    sessions = SessionStore(sessions_path)
    session = sessions.create_session(project="demo", entry_point="web")
    RoomAccessPolicy(memory).create_private_room(
        "alice", "private-room", session_id=session.session_id
    )
    memory.db.execute(
        "UPDATE private_rooms SET last_activity_at = 1 WHERE room_id = ?",
        ("private-room",),
    )
    memory.close()

    manager = WebManager()
    room = manager.get_room("private-room")
    room.private_session = True
    room.last_activity = time.monotonic() - 3600
    monkeypatch.setattr(routes_api, "web_manager", manager)
    monkeypatch.setattr(routes_api, "_memory_store", lambda: MemoryStore(memory_path))
    monkeypatch.setattr(routes_api.core, "session_store", sessions, raising=False)
    monkeypatch.setenv("UAGENT_WEB_ROOM_IDLE_TTL_SECONDS", "60")

    removed = routes_api._cleanup_expired_private_rooms(now=time.time() + 120)

    assert removed == ["private-room"]
    assert "private-room" not in manager.rooms
    check = MemoryStore(memory_path)
    assert RoomAccessPolicy(check).private_room_owner("private-room") is None
    check.close()
    with pytest.raises(SessionStoreError, match="unknown session"):
        sessions.get_session(session.session_id)
    sessions.close()


def test_web_room_scope_survives_disconnect_and_is_closed_after_idle_ttl():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    room = manager.get_room("room-sandbox")
    room.private_session = True
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="room-sandbox-process-1",
    )
    manager.bind_sandbox_scope(room, scope)

    connection = object()
    room.active_connections.append(connection)
    room.disconnect(connection)
    room.last_activity = 100.0

    manager.bind_sandbox_scope(room, scope)
    assert room.current_sandbox_scope() == scope
    assert closed_scopes == []
    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=129.0) == []
    assert closed_scopes == []
    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=130.0) == ["room-sandbox"]
    assert closed_scopes == [scope]
    assert room.take_sandbox_scope() is None


def test_rebinding_web_room_scope_closes_previous_principal_or_project():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    room = manager.get_room("shared-room")
    first = TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="shared-room-process-1",
    )
    second = TrustedSandboxScope(
        deployment_id="web",
        principal_id="bob",
        project_id="project-b",
        scope_kind="web-room",
        scope_id="shared-room-process-1",
    )

    manager.bind_sandbox_scope(room, first)
    manager.bind_sandbox_scope(room, second)

    assert closed_scopes == [first]
    assert not manager.release_room_sandbox_scope(room, expected_scope=first)
    assert room.current_sandbox_scope() == second
    assert closed_scopes == [first]
    assert room.take_sandbox_scope() == second


def test_discarding_expired_private_room_releases_its_sandbox_scope():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    room = manager.get_room("expired-private-room")
    room.private_session = True
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="expired-private-room-process-1",
    )
    manager.bind_sandbox_scope(room, scope)

    assert manager.discard_expired_private_room_if_idle("expired-private-room")
    assert closed_scopes == [scope]
    assert not manager.discard_expired_private_room_if_idle("expired-private-room")


def test_running_room_jobs_block_scope_rebind_and_room_eviction():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    class FakeJobs:
        def running_count_for_room(self, room_id):
            assert room_id == "shared-room"
            return 1

    manager.sandbox_session_manager = FakeSandboxManager()
    manager.sub_agent_job_manager = FakeJobs()
    room = manager.get_room("shared-room")
    room.private_session = True
    room.last_activity = 100.0
    first = TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="shared-room-process-1",
    )
    second = TrustedSandboxScope(
        deployment_id="web",
        principal_id="bob",
        project_id="project-b",
        scope_kind="web-room",
        scope_id="shared-room-process-1",
    )
    manager.bind_sandbox_scope(room, first)

    with pytest.raises(RuntimeError, match="jobs are running"):
        manager.bind_sandbox_scope(room, second)
    assert room.current_sandbox_scope() == first
    assert closed_scopes == []
    assert manager.evict_idle_rooms(idle_ttl_seconds=30, now=1000.0) == []
    assert manager.rooms["shared-room"] is room


def test_membership_revocation_releases_only_matching_room_scopes():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    manager = WebManager()
    closed_scopes = []

    class FakeSandboxManager:
        def close_scope(self, scope):
            closed_scopes.append(scope)

    manager.sandbox_session_manager = FakeSandboxManager()
    cases = [
        ("room-a", "alice", "project-a"),
        ("room-b", "bob", "project-a"),
        ("room-c", "alice", "project-b"),
    ]
    scopes = []
    for room_id, principal_id, project_id in cases:
        room = manager.get_room(room_id)
        scope = TrustedSandboxScope(
            deployment_id="web",
            principal_id=principal_id,
            project_id=project_id,
            scope_kind="web-room",
            scope_id=f"{room_id}-process-1",
        )
        manager.bind_sandbox_scope(room, scope)
        scopes.append(scope)

    assert (
        manager.release_sandbox_scopes(principal_id="alice", project_id="project-a")
        == 1
    )
    assert closed_scopes == [scopes[0]]
    assert manager.rooms["room-a"].current_sandbox_scope() is None
    assert manager.rooms["room-b"].current_sandbox_scope() == scopes[1]
    assert manager.rooms["room-c"].current_sandbox_scope() == scopes[2]

    with pytest.raises(ValueError, match="at least one"):
        manager.release_sandbox_scopes()


def test_migrated_private_room_gets_a_fresh_reconnect_grace_period(tmp_path):
    memory_path = tmp_path / "legacy-memory.sqlite3"
    connection = sqlite3.connect(memory_path)
    connection.execute(
        "CREATE TABLE private_rooms ("
        "room_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, "
        "session_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)"
    )
    connection.execute(
        "INSERT INTO private_rooms(room_id, principal_id, session_id, created_at) "
        "VALUES ('legacy-room', 'alice', 'session-a', ?)",
        (time.time() - 90 * 24 * 60 * 60,),
    )
    connection.commit()
    connection.close()

    before_upgrade = time.time()
    memory = MemoryStore(memory_path)
    row = memory.db.execute(
        "SELECT last_activity_at FROM private_rooms WHERE room_id = 'legacy-room'"
    ).fetchone()

    assert row["last_activity_at"] >= before_upgrade
    assert row["last_activity_at"] > time.time() - 60 * 60
    memory.close()


def test_persistent_private_room_touch_preserves_cached_room_state(
    tmp_path, monkeypatch
):
    from uagent.web_impl import routes_api

    memory_path = tmp_path / "memory.sqlite3"
    memory = MemoryStore(memory_path)
    RoomAccessPolicy(memory).create_private_room("alice", "private-room")
    memory.close()

    manager = WebManager()
    room = manager.get_room("private-room")
    room.private_session = True
    room.last_activity = time.monotonic() - 3600
    room.messages.append({"role": "assistant", "content": "keep this history"})
    memory = MemoryStore(memory_path)
    assert RoomAccessPolicy(memory).touch_private_room("private-room")
    memory.close()
    monkeypatch.setattr(routes_api, "web_manager", manager)
    monkeypatch.setattr(routes_api, "_memory_store", lambda: MemoryStore(memory_path))
    monkeypatch.setattr(routes_api.core, "session_store", None, raising=False)
    monkeypatch.setenv("UAGENT_WEB_ROOM_IDLE_TTL_SECONDS", "60")

    assert routes_api._cleanup_expired_private_rooms() == []
    assert manager.rooms["private-room"] is room
    assert room.messages == [{"role": "assistant", "content": "keep this history"}]


def test_expired_private_room_rejects_reconnect_before_cleanup_runs(
    tmp_path, monkeypatch
):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    policy = RoomAccessPolicy(memory)
    policy.create_private_room("alice", "private-room")
    memory.db.execute(
        "UPDATE private_rooms SET last_activity_at = ? WHERE room_id = ?",
        (time.time() - 61, "private-room"),
    )
    memory.db.commit()
    monkeypatch.setenv("UAGENT_WEB_ROOM_IDLE_TTL_SECONDS", "60")

    assert not policy.is_private_room_for("alice", "private-room")
    memory.close()


def test_active_private_room_is_not_expired_from_persistent_storage(
    tmp_path, monkeypatch
):
    from uagent.web_impl import routes_api

    memory_path = tmp_path / "memory.sqlite3"
    memory = MemoryStore(memory_path)
    RoomAccessPolicy(memory).create_private_room("alice", "private-room")
    memory.db.execute(
        "UPDATE private_rooms SET last_activity_at = 1 WHERE room_id = ?",
        ("private-room",),
    )
    memory.close()

    manager = WebManager()
    room = manager.get_room("private-room")
    room.private_session = True
    room.last_activity = time.monotonic() - 3600
    room.human_ask_pending = True
    monkeypatch.setattr(routes_api, "web_manager", manager)
    monkeypatch.setattr(routes_api, "_memory_store", lambda: MemoryStore(memory_path))
    monkeypatch.setattr(routes_api.core, "session_store", None, raising=False)
    monkeypatch.setenv("UAGENT_WEB_ROOM_IDLE_TTL_SECONDS", "60")

    assert routes_api._cleanup_expired_private_rooms(now=time.time() + 120) == []
    check = MemoryStore(memory_path)
    assert RoomAccessPolicy(check).private_room_owner("private-room") == "alice"
    check.close()


def test_private_room_activity_touch_does_not_invalidate_memory_projections(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    policy = RoomAccessPolicy(memory)
    policy.create_private_room("alice", "private-room")
    memory.db.execute("DROP TRIGGER private_rooms_generation_UPDATE")
    memory.db.execute(
        "CREATE TRIGGER private_rooms_generation_UPDATE "
        "AFTER UPDATE ON private_rooms BEGIN "
        "UPDATE memory_metadata SET value = "
        "CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
        "WHERE key = 'access_generation'; END"
    )
    memory.close()

    # Reopening an existing store upgrades the old broad UPDATE trigger so that
    # an idle timestamp refresh does not invalidate active Memory snapshots.
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    policy = RoomAccessPolicy(memory)
    before = int(
        memory.db.execute(
            "SELECT value FROM memory_metadata WHERE key = 'access_generation'"
        ).fetchone()[0]
    )

    assert policy.touch_private_room("private-room", now=time.time() + 1)
    after = int(
        memory.db.execute(
            "SELECT value FROM memory_metadata WHERE key = 'access_generation'"
        ).fetchone()[0]
    )

    assert after == before
    memory.close()


def test_room_cleanup_callback_failure_preserves_private_room_binding(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    policy = RoomAccessPolicy(memory)
    policy.create_private_room("alice", "private-room", session_id="session-a")

    def fail_session_delete(session_id: str) -> None:
        assert session_id == "session-a"
        raise RuntimeError("session store unavailable")

    with pytest.raises(RuntimeError, match="session store unavailable"):
        policy.delete_private_room_if_expired(
            "private-room",
            session_id="session-a",
            cutoff=time.time() + 10,
            before_delete=fail_session_delete,
        )

    assert policy.private_room_owner("private-room") == "alice"
    memory.close()
