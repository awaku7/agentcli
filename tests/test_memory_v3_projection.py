from __future__ import annotations

from types import SimpleNamespace

from uagent.profile_manager import get_profile_file_path, load_profile, save_profile
from uagent.runtime.identity_context import TurnContext, bind_turn_context
from uagent.runtime.memory_access import MemoryAccessContext, ScopedMemoryStore
from uagent.runtime.memory_projection import (
    apply_memory_projection,
    prepare_memory_projection,
)
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.room_access import RoomAccessPolicy, RoomMemoryService


def _access(principal_id: str) -> MemoryAccessContext:
    return MemoryAccessContext(
        principal_id=principal_id,
        project_id="demo",
        authenticated=True,
        private_session=True,
    )


def _turn(principal_id: str) -> TurnContext:
    return TurnContext(
        principal_id=principal_id,
        room_id="",
        project_id="demo",
        session_id=f"session-{principal_id}",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )


def test_identity_bound_projection_attributes_sharing_and_invalidates_revocation(
    tmp_path, monkeypatch
) -> None:
    memory_path = tmp_path / "memory.sqlite3"
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(memory_path))
    monkeypatch.setenv("UAGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")

    store = MemoryStore(memory_path)
    owner = ScopedMemoryStore(store, _access("alice"))
    record = owner.append("release checklist uses signed tags")
    grant_id = owner.share(record["memory_id"], "bob", expected_revision=1)
    store.close()

    save_profile(
        {"environment": {}, "preferences": ["Alice preference"], "constraints": []},
        "alice",
    )
    save_profile(
        {"environment": {}, "preferences": ["Bob preference"], "constraints": []},
        "bob",
    )
    core = SimpleNamespace(memory_private_session_principal="bob")
    messages = [{"role": "user", "content": "show the release checklist"}]

    with bind_turn_context(_turn("bob")):
        snapshot = prepare_memory_projection(messages, core)
        projected = apply_memory_projection(messages, snapshot, core)

    assert snapshot is not None
    rendered = "\n".join(str(message.get("content", "")) for message in projected)
    assert "Bob preference" in rendered
    assert "Alice preference" not in rendered
    assert "[shared-from:alice] release checklist uses signed tags" in rendered
    assert f"memory:{record['memory_id']}@1;grant:{grant_id}" in rendered

    store = MemoryStore(memory_path)
    ScopedMemoryStore(store, _access("alice")).revoke(record["memory_id"], grant_id)
    store.close()
    with bind_turn_context(_turn("bob")):
        assert apply_memory_projection(messages, snapshot, core) == messages
    with bind_turn_context(_turn("charlie")):
        assert apply_memory_projection(messages, snapshot, core) == messages


def test_profiles_are_separate_and_paths_do_not_expose_principal_ids(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("UAGENT_LOG_DIR", str(tmp_path))
    save_profile(
        {"environment": {}, "preferences": ["Alice"], "constraints": []},
        "alice@example.test",
    )
    save_profile(
        {"environment": {}, "preferences": ["Bob"], "constraints": []},
        "bob@example.test",
    )

    alice_path = get_profile_file_path("alice@example.test")
    bob_path = get_profile_file_path("bob@example.test")
    assert alice_path != bob_path
    assert "alice@example.test" not in alice_path
    assert "bob@example.test" not in bob_path
    assert load_profile("alice@example.test")["preferences"] == ["Alice"]
    assert load_profile("bob@example.test")["preferences"] == ["Bob"]


def test_room_policy_feeds_projection_and_membership_revocation_invalidates_it(
    tmp_path, monkeypatch
) -> None:
    memory_path = tmp_path / "memory.sqlite3"
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(memory_path))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    store = MemoryStore(memory_path)
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.set_membership("root", "room-x", "alice", "admin")
    policy.set_membership("alice", "room-x", "bob", "member")
    room_memory = RoomMemoryService(
        store,
        policy,
        principal_id="alice",
        project_id="demo",
        room_id="room-x",
    ).append("room deployment checklist")
    store.close()
    turn = TurnContext(
        principal_id="bob",
        room_id="room-x",
        project_id="demo",
        session_id="session-bob",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    messages = [{"role": "user", "content": "show deployment checklist"}]
    core = SimpleNamespace()

    with bind_turn_context(turn):
        snapshot = prepare_memory_projection(messages, core)
        projected = apply_memory_projection(messages, snapshot, core)
    assert snapshot is not None
    rendered = "\n".join(str(message.get("content", "")) for message in projected)
    assert "[room:room-x] room deployment checklist" in rendered
    assert f"memory:{room_memory['memory_id']}@1" in rendered

    store = MemoryStore(memory_path)
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.revoke_membership("alice", "room-x", "bob")
    store.close()
    with bind_turn_context(turn):
        assert apply_memory_projection(messages, snapshot, core) == messages
