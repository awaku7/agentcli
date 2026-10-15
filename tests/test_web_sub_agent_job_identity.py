from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.runtime.sub_agent_jobs import SubAgentJobOwner
from uagent.web_impl import io
from uagent.web_impl.rooms import WebRoom, web_manager
from uagent.web_impl.routes_ws import _human_ask_response_is_authorized
from uagent.web_impl.sub_agent_jobs import _web_confirmation_handler, web_job_owner


def test_web_job_owner_captures_trusted_principal():
    room = WebRoom("shared-room")
    room.session_id = "room-session"

    owner = web_job_owner(room, principal_id="alice")

    assert owner == SubAgentJobOwner(
        entry_point="web",
        session_id="room-session",
        room_id="shared-room",
        principal_id="alice",
    )


def test_background_confirmation_uses_job_principal_without_foreground_turn(
    monkeypatch,
):
    room = WebRoom("shared-room")
    owner = SubAgentJobOwner(
        entry_point="web",
        session_id="room-session",
        room_id=room.room_id,
        principal_id="alice",
    )
    context = SimpleNamespace(
        owner=owner,
        job_id="job-alice",
        agent_name="reviewer",
        cancel_event=SimpleNamespace(is_set=lambda: False),
        raise_if_cancelled=lambda: None,
        set_waiting_for_user=lambda _waiting: None,
    )
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "get_room", lambda _room_id: room)

    def fake_ask(_room, args):
        assert args["_expected_principal_id"] == "alice"
        assert _human_ask_response_is_authorized(room, "alice")
        assert not _human_ask_response_is_authorized(room, "bob")
        return json.dumps({"user_reply": "approved", "cancelled": False})

    monkeypatch.setattr(io, "_web_human_ask_unlocked", fake_ask)

    # No foreground TurnContext is active here: the immutable Job owner is the
    # only identity used to authorize the confirmation response.
    assert _web_confirmation_handler(context, "Proceed?", False) == "approved"
    assert room._human_ask_expected_principal_id == ""
