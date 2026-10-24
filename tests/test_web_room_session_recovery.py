from __future__ import annotations

import pytest

from uagent.runtime.identity_context import IdentityResolutionError
from uagent.runtime.session_store import SessionStore
from uagent.web_impl.history import _restore_private_room_session
from uagent.web_impl.rooms import WebRoom


def test_private_room_rehydrates_its_bound_sqlite_history(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    room = WebRoom("private-room-1")
    session = store.create_session(
        project="browser-project",
        project_path=tmp_path,
        entry_point="web",
    )
    room.session_id = session.session_id
    room.private_session = True
    store.bind_identity_context(
        session.session_id,
        principal_id="browser:alice",
        room_id=room.room_id,
    )
    store.append_message(session.session_id, "user", "saved question")
    store.append_message(session.session_id, "assistant", "saved answer")

    try:
        assert _restore_private_room_session(
            room, store=store, principal_id="browser:alice"
        )
        assert [
            message["content"]
            for message in room.history
            if message["role"]
            in {
                "user",
                "assistant",
            }
        ] == ["saved question", "saved answer"]
        assert room.history_initialized is True
        assert room.welcome_shown is True
        assert room.responses_state == {}
        assert room.tool_context == {}
    finally:
        store.close()


def test_private_room_restore_rejects_another_principal(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    room = WebRoom("private-room-2")
    session = store.create_session(project="browser-project", entry_point="web")
    room.session_id = session.session_id
    room.private_session = True
    store.bind_identity_context(
        session.session_id,
        principal_id="browser:alice",
        room_id=room.room_id,
    )
    store.append_message(session.session_id, "user", "do not expose")

    try:
        with pytest.raises(IdentityResolutionError, match="binding does not match"):
            _restore_private_room_session(room, store=store, principal_id="browser:bob")
        assert room.history == []
    finally:
        store.close()
