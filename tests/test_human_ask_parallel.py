from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from uagent.tools import human_ask_tool


def test_parallel_human_asks_are_serialized(monkeypatch):
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    def fake_run(args):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            if args["message"] == "first":
                first_entered.set()
                assert release_first.wait(timeout=5)
            else:
                second_entered.set()
            return args["message"]
        finally:
            with state_lock:
                active -= 1

    monkeypatch.setattr(human_ask_tool, "_run_tool_unserialized", fake_run)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(human_ask_tool.run_tool, {"message": "first"})
        assert first_entered.wait(timeout=5)

        second = executor.submit(human_ask_tool.run_tool, {"message": "second"})
        assert not second_entered.wait(timeout=0.1)

        release_first.set()
        assert first.result(timeout=5) == "first"
        assert second.result(timeout=5) == "second"

    assert max_active == 1


def test_human_ask_exposes_and_clears_question_message(monkeypatch):
    import json
    import queue as queue_module

    from uagent.tools.context import ToolCallbacks

    # The test runner disables interactive tools globally; this test exercises
    # the interactive hand-off path explicitly.
    monkeypatch.delenv("UAGENT_NON_INTERACTIVE", raising=False)

    state = {"active": False, "message": None, "queue": None, "lines": []}
    message_seen = threading.Event()

    def set_message(value):
        state["message"] = value
        if value:
            message_seen.set()

    callbacks = ToolCallbacks(
        human_ask_lock=threading.RLock(),
        human_ask_active_ref=lambda: state["active"],
        human_ask_set_active=lambda v: state.__setitem__("active", bool(v)),
        human_ask_queue_ref=lambda: state["queue"],
        human_ask_set_queue=lambda q: state.__setitem__("queue", q),
        human_ask_lines_ref=lambda: state["lines"],
        human_ask_multiline_active_ref=lambda: False,
        human_ask_set_multiline_active=lambda v: None,
        human_ask_set_password=lambda v: None,
        human_ask_set_message=set_message,
        is_auto_pilot_active=lambda: False,
    )
    monkeypatch.setattr(human_ask_tool, "get_callbacks", lambda: callbacks)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(human_ask_tool.run_tool, {"message": "which branch?"})
        assert message_seen.wait(timeout=5)
        assert state["message"] == "which branch?"
        answer_queue = state["queue"]
        assert isinstance(answer_queue, queue_module.Queue)
        answer_queue.put("main")
        result = json.loads(future.result(timeout=5))

    assert result["user_reply"] == "main"
    assert state["message"] == ""


def test_clean_choices_validates_labels():
    from uagent.tools.human_ask_tool import clean_choices

    assert clean_choices({"choices": [" Red ", "Blue", "Red", "", 3]}) == [
        "Red",
        "Blue",
    ]
    assert clean_choices({"choices": ["only"]}) == []
    assert clean_choices({"choices": "Red"}) == []
    assert clean_choices({}) == []
    assert clean_choices({"choices": ["a", "b"]}, is_password=True) == []
    many = [f"c{i}" for i in range(30)]
    assert len(clean_choices({"choices": many})) == 20


def test_resolve_choice_reply_maps_numbers_and_labels():
    from uagent.tools.human_ask_tool import resolve_choice_reply

    choices = ["Red", "Blue"]
    assert resolve_choice_reply("2", choices) == "Blue"
    assert resolve_choice_reply(" 1 ", choices) == "Red"
    assert resolve_choice_reply("Blue", choices) == "Blue"
    assert resolve_choice_reply("3", choices) == "3"
    assert resolve_choice_reply("green", choices) == "green"
    assert resolve_choice_reply("2", []) == "2"


def test_human_ask_choices_end_to_end(monkeypatch):
    import json
    import queue as queue_module

    from uagent.tools.context import ToolCallbacks

    monkeypatch.delenv("UAGENT_NON_INTERACTIVE", raising=False)

    state = {
        "active": False,
        "message": None,
        "choices": None,
        "queue": None,
        "lines": [],
    }
    message_seen = threading.Event()

    def set_message(value):
        state["message"] = value
        if value:
            message_seen.set()

    callbacks = ToolCallbacks(
        human_ask_lock=threading.RLock(),
        human_ask_active_ref=lambda: state["active"],
        human_ask_set_active=lambda v: state.__setitem__("active", bool(v)),
        human_ask_queue_ref=lambda: state["queue"],
        human_ask_set_queue=lambda q: state.__setitem__("queue", q),
        human_ask_lines_ref=lambda: state["lines"],
        human_ask_multiline_active_ref=lambda: False,
        human_ask_set_multiline_active=lambda v: None,
        human_ask_set_password=lambda v: None,
        human_ask_set_message=set_message,
        human_ask_set_choices=lambda v: state.__setitem__("choices", list(v)),
        is_auto_pilot_active=lambda: False,
    )
    monkeypatch.setattr(human_ask_tool, "get_callbacks", lambda: callbacks)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            human_ask_tool.run_tool,
            {"message": "pick one", "choices": ["Red", "Blue"]},
        )
        assert message_seen.wait(timeout=5)
        # The exposed question carries the numbered list for frontends.
        assert state["message"] == "pick one\n  1. Red\n  2. Blue"
        assert state["choices"] == ["Red", "Blue"]
        answer_queue = state["queue"]
        assert isinstance(answer_queue, queue_module.Queue)
        answer_queue.put("2")
        result = json.loads(future.result(timeout=5))

    assert result["user_reply"] == "Blue"
    assert result["choices"] == ["Red", "Blue"]
    assert result["cancelled"] is False
    assert state["message"] == ""
    assert state["choices"] == []


def test_resolve_choice_reply_passes_unicode_digits_through():
    from uagent.tools.human_ask_tool import resolve_choice_reply

    choices = ["Red", "Blue"]
    # isdigit() accepts these but int() rejects them; they are
    # free-text replies, not position selections.
    assert resolve_choice_reply("²", choices) == "²"
    assert resolve_choice_reply("①", choices) == "①"
