"""Tests for bitchat turn progress notes.

While a paired peer's DM turn runs, the peer receives the same kind
of progress notes the Nostr remote (NIP-17) requester gets: a
tool-activity note when a tool starts (consecutive repeats of the
same tool sent once) and buffered reasoning notes, flushed at 600
characters, before the next tool note, and before the final reply.
"""

from __future__ import annotations

import queue
import threading

import pytest

from uagent.tools import pybitchat_shared as shared

ROUTE = {"via": "ble", "peer": "0123456789abcdef"}


@pytest.fixture()
def sent(monkeypatch):
    calls: list[tuple[str, object]] = []

    def fake_reply(text, route):
        calls.append((text, route))

    monkeypatch.setattr(shared, "reply_to_bitchat_dm", fake_reply)
    shared.cancel_bitchat_turn()
    yield calls
    shared.cancel_bitchat_turn()


def test_tool_note_sent_to_active_peer(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_tool_action("get_weather", "Getting the weather")
    assert sent == [("🔧 Getting the weather", ROUTE)]


def test_tool_note_dedupes_consecutive_same_tool(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_tool_action("search", "Searching")
    shared.note_bitchat_tool_action("search", "Searching")
    shared.note_bitchat_tool_action("read", "Reading")
    assert [text for text, _ in sent] == ["🔧 Searching", "🔧 Reading"]


def test_no_active_turn_no_notes(sent) -> None:
    shared.note_bitchat_tool_action("search", "Searching")
    shared.note_bitchat_reasoning("thinking" * 200)
    assert sent == []


def test_reasoning_buffered_until_threshold(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_reasoning("x" * 300)
    assert sent == []
    shared.note_bitchat_reasoning("x" * 300)
    assert sent == [("💭 " + "x" * 600, ROUTE)]


def test_tool_note_flushes_reasoning_first(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_reasoning("thinking")
    shared.note_bitchat_tool_action("search", "Searching")
    assert [text for text, _ in sent] == ["💭 thinking", "🔧 Searching"]


def test_finish_flushes_reasoning_before_reply_and_clears(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_reasoning("abc")
    shared.finish_bitchat_turn("done", ROUTE)
    assert [text for text, _ in sent] == ["💭 abc", "done"]
    assert not shared.bitchat_turn_active()
    shared.note_bitchat_tool_action("search", "Searching")
    assert len(sent) == 2


def test_set_active_none_flushes_to_previous_peer(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_reasoning("abc")
    shared.set_active_bitchat_turn(None)
    assert sent == [("💭 abc", ROUTE)]
    assert not shared.bitchat_turn_active()


def test_background_reasoning_not_forwarded(sent, monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.runtime.sub_agent_jobs.current_sub_agent_job_mode",
        lambda: "background",
    )
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_reasoning("x" * 700)
    shared.finish_bitchat_turn("done", ROUTE)
    assert [text for text, _ in sent] == ["done"]


def test_progress_notes_capped_per_turn(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    for i in range(35):
        shared.note_bitchat_tool_action(f"tool{i}", f"Doing {i}")
    assert len(sent) == 30


def test_progress_note_text_truncated(sent) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared.note_bitchat_tool_action("big", "x" * 2000)
    assert len(sent[0][0]) == 1200


# ---------------------------------------------------------------------------
# human_ask bridging
# ---------------------------------------------------------------------------


@pytest.fixture()
def ask_state(monkeypatch):
    from uagent import core

    q = queue.Queue()
    monkeypatch.setattr(core, "human_ask_lock", threading.Lock(), raising=False)
    monkeypatch.setattr(core, "human_ask_active", True, raising=False)
    monkeypatch.setattr(core, "human_ask_is_password", False, raising=False)
    monkeypatch.setattr(core, "human_ask_message", "Which file?", raising=False)
    monkeypatch.setattr(core, "human_ask_queue", q, raising=False)
    return q


def test_ask_question_forwarded_once(sent, ask_state) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    shared._forward_pending_ask_once()
    assert sent == [("❓ Which file?", ROUTE)]


def test_password_ask_never_forwarded(sent, ask_state, monkeypatch) -> None:
    from uagent import core

    monkeypatch.setattr(core, "human_ask_is_password", True, raising=False)
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    assert sent == []


def test_ask_answer_consumed_and_delivered(sent, ask_state) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    assert shared._try_deliver_bitchat_ask_answer(ROUTE, "a.txt")
    assert ask_state.get_nowait() == "a.txt"
    # Routing disarms after one answer: the next DM is a new turn again.
    assert not shared._try_deliver_bitchat_ask_answer(ROUTE, "another")


def test_ask_answer_from_other_peer_not_consumed(sent, ask_state) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    other = {"via": "ble", "peer": "ffeeffeeffeeffee"}
    assert not shared._try_deliver_bitchat_ask_answer(other, "a.txt")
    assert ask_state.empty()


def test_ask_control_text_not_consumed(sent, ask_state) -> None:
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    assert not shared._try_deliver_bitchat_ask_answer(ROUTE, "/uag status")
    assert ask_state.empty()


def test_ask_answer_after_ask_ended_not_consumed(sent, ask_state, monkeypatch) -> None:
    from uagent import core

    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    monkeypatch.setattr(core, "human_ask_active", False, raising=False)
    assert not shared._try_deliver_bitchat_ask_answer(ROUTE, "a.txt")
    assert ask_state.empty()


def test_ask_not_forwarded_when_turn_changes_before_snapshot(
    sent, ask_state, monkeypatch
) -> None:
    other = {"via": "ble", "peer": "ffeeffeeffeeffee"}

    def switching_snapshot():
        # The captured turn ends and another peer's turn starts before
        # the ask state is read, so the snapshot holds the new turn's
        # question; it must not go to the previous turn's peer.
        shared.set_active_bitchat_turn(other)
        return {
            "active": True,
            "is_password": False,
            "message": "Which file?",
            "queue": ask_state,
        }

    monkeypatch.setattr(shared, "_ask_state_snapshot", switching_snapshot)
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    assert sent == []
    assert shared._ASK_FORWARDED_QUEUE is None


def test_ask_not_armed_when_turn_changes_during_send(
    sent, ask_state, monkeypatch
) -> None:
    other = {"via": "ble", "peer": "ffeeffeeffeeffee"}

    def switching_reply(text, route):
        sent.append((text, route))
        shared.set_active_bitchat_turn(other)

    monkeypatch.setattr(shared, "reply_to_bitchat_dm", switching_reply)
    shared.set_active_bitchat_turn(ROUTE)
    shared._forward_pending_ask_once()
    # The question went to the peer whose turn asked it, but answer
    # routing must not arm once the turn has moved on.
    assert sent == [("❓ Which file?", ROUTE)]
    assert shared._ASK_FORWARDED_QUEUE is None
    assert shared._ASK_QUEUED_QUEUE is None
