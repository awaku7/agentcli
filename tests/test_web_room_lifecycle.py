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
