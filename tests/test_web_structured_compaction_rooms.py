"""Public Web-room source isolation for default-on Structured Compaction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.runtime.identity_context import IdentityResolutionError
from uagent.runtime.session_store import SessionStore
from uagent.web_impl import agent_worker
from uagent.web_impl.agent_worker import _ensure_public_room_session
from uagent.web_impl.rooms import WebRoom


def test_public_web_rooms_persist_to_distinct_sessions(tmp_path):
    with SessionStore(tmp_path / "web-room-isolation.sqlite3") as store:
        first = WebRoom("room-a")
        second = WebRoom("room-b")
        first_id = _ensure_public_room_session(first, store, str(tmp_path))
        second_id = _ensure_public_room_session(second, store, str(tmp_path))

        assert first_id != second_id
        assert first_id != ""
        assert second_id != ""
        assert _ensure_public_room_session(first, store, str(tmp_path)) == first_id

        store.append_message(first_id, "user", "room-a-private-message")
        store.append_message(second_id, "user", "room-b-private-message")
        assert [item["content"] for item in store.list_indexed_messages(first_id)] == [
            "room-a-private-message"
        ]
        assert [item["content"] for item in store.list_indexed_messages(second_id)] == [
            "room-b-private-message"
        ]


def test_public_web_room_rejects_session_bound_to_another_room(tmp_path):
    with SessionStore(tmp_path / "web-room-access.sqlite3") as store:
        first = WebRoom("room-a")
        first_id = _ensure_public_room_session(first, store, str(tmp_path))
        store.bind_identity_context(
            first_id, principal_id="local", room_id=first.room_id
        )

        second = WebRoom("room-b")
        second.session_id = first_id
        with pytest.raises(IdentityResolutionError, match="another room"):
            _ensure_public_room_session(second, store, str(tmp_path))


def test_public_web_room_does_not_silently_reuse_missing_session(tmp_path):
    with SessionStore(tmp_path / "web-room-stale.sqlite3") as store:
        room = WebRoom("room-old")
        old_id = _ensure_public_room_session(room, store, str(tmp_path))
        store.delete_session(old_id)
        with pytest.raises(Exception, match="unknown session"):
            _ensure_public_room_session(room, store, str(tmp_path))
        assert room.session_id == old_id


def test_public_web_workers_write_only_to_their_own_sessions(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    monkeypatch.setattr(agent_worker, "resolve_identity_mode", lambda: "local")
    with SessionStore(tmp_path / "web-room-runtime.sqlite3") as store:
        startup = store.create_session(project="startup", entry_point="web")
        core = SimpleNamespace(
            session_store=store,
            session_id=startup.session_id,
            _session_store_active_id=startup.session_id,
            responses_state={},
            tool_context={},
        )

        def persist(message):
            store.append_message(
                core._session_store_active_id, message["role"], message["content"]
            )

        core.log_message = persist
        monkeypatch.setattr(agent_worker, "core", core)
        rooms = [WebRoom("room-a"), WebRoom("room-b")]
        for room in rooms:
            room.base_dir = str(tmp_path)

            def provider_setup(bound_core):
                assert bound_core.session_id == room.session_id
                bound_core.log_message(
                    {"role": "user", "content": f"{room.room_id}-fact"}
                )
                raise RuntimeError("offline stop after session assertion")

            monkeypatch.setattr(agent_worker.providers, "make_client", provider_setup)
            agent_worker.run_agent_worker(room, "question")
            assert core._session_store_active_id == startup.session_id

        assert rooms[0].session_id != rooms[1].session_id
        assert store.list_messages(startup.session_id) == []
        for room in rooms:
            assert [
                item["content"] for item in store.list_messages(room.session_id)
            ] == [f"{room.room_id}-fact"]

