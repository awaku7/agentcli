from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from uagent.web_impl import io
from uagent.i18n import (
    get_contextvar_locale,
    reset_contextvar_locale,
    set_contextvar_locale,
)
from uagent.runtime.identity_context import submit_with_current_context
from uagent.web_impl.rooms import (
    WebRoom,
    get_context_web_room,
    reset_context_web_room,
    set_context_web_room,
)


def test_web_human_ask_serializes_requests_within_one_room(monkeypatch):
    room = WebRoom("room-a")
    first_entered = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()

    def fake_unlocked(current_room, args):
        assert current_room is room
        if args["message"] == "first":
            first_entered.set()
            assert release_first.wait(timeout=5)
            return "first-result"
        second_entered.set()
        return "second-result"

    monkeypatch.setattr(io, "_web_human_ask_unlocked", fake_unlocked)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(io.web_human_ask, room, {"message": "first"})
        assert first_entered.wait(timeout=5)

        second = executor.submit(io.web_human_ask, room, {"message": "second"})
        assert not second_entered.wait(timeout=0.2)

        release_first.set()
        assert first.result(timeout=5) == "first-result"
        assert second.result(timeout=5) == "second-result"
        assert second_entered.is_set()


def test_web_human_ask_keeps_different_rooms_parallel(monkeypatch):
    first_room = WebRoom("room-a")
    second_room = WebRoom("room-b")
    barrier = threading.Barrier(2)

    def fake_unlocked(room, args):
        barrier.wait(timeout=5)
        return f"{room.room_id}:{args['message']}"

    monkeypatch.setattr(io, "_web_human_ask_unlocked", fake_unlocked)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            io.web_human_ask,
            first_room,
            {"message": "first"},
        )
        second = executor.submit(
            io.web_human_ask,
            second_room,
            {"message": "second"},
        )

        assert first.result(timeout=5) == "room-a:first"
        assert second.result(timeout=5) == "room-b:second"


def test_parallel_context_propagates_web_room_and_locale():
    room = WebRoom("room-a")
    room.lang = "ja"
    room_token = set_context_web_room(room)
    locale_token = set_contextvar_locale(room.lang)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = submit_with_current_context(
                executor,
                lambda: (
                    get_context_web_room().room_id,
                    get_contextvar_locale(),
                ),
            )
            assert future.result(timeout=5) == ("room-a", "ja")
    finally:
        reset_contextvar_locale(locale_token)
        reset_context_web_room(room_token)
