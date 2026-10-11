"""Public Web-room source isolation for default-on Structured Compaction."""

from __future__ import annotations

import pytest

from uagent.runtime.identity_context import IdentityResolutionError
from uagent.runtime.session_store import SessionStore
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
