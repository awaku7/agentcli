from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Barrier
from queue import Queue

import pytest

from uagent import core
from uagent.cli_impl import stdin_loop
from uagent.cli_impl.state import (
    release_typeahead_slot,
    reserve_typeahead_slot,
    reset_typeahead_slot,
)
from uagent.cli_impl.stdin_loop import _typeahead_rejection_notice
from uagent.i18n import reset_contextvar_locale, set_contextvar_locale


def test_only_one_typeahead_message_can_be_pending() -> None:
    reset_typeahead_slot()
    try:
        assert reserve_typeahead_slot() is True
        assert reserve_typeahead_slot() is False

        release_typeahead_slot()
        assert reserve_typeahead_slot() is True
    finally:
        reset_typeahead_slot()


def test_typeahead_accepts_only_ordinary_single_line_user_messages() -> None:
    assert (
        _typeahead_rejection_notice(
            "follow-up question", multiline_active=False, mesh_only=False
        )
        is None
    )
    assert (
        _typeahead_rejection_notice("", multiline_active=False, mesh_only=False) == ""
    )
    for unsafe in (":exit", "f", "first\nsecond", "first\rsecond"):
        assert (
            _typeahead_rejection_notice(unsafe, multiline_active=False, mesh_only=False)
            is not None
        )
    assert (
        _typeahead_rejection_notice("follow-up", multiline_active=True, mesh_only=False)
        is not None
    )
    assert (
        _typeahead_rejection_notice("follow-up", multiline_active=False, mesh_only=True)
        is not None
    )


def test_typeahead_rejection_notice_is_localized() -> None:
    token = set_contextvar_locale("ja")
    try:
        notice = _typeahead_rejection_notice(
            ":exit", multiline_active=False, mesh_only=False
        )
    finally:
        reset_contextvar_locale(token)

    assert notice is not None
    assert "先行入力できるのは1行" in notice


def test_busy_prompt_queues_one_message_for_the_foreground_loop(monkeypatch) -> None:
    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    class _Session:
        app = object()

        @staticmethod
        def prompt(_prompt, **_kwargs):
            # The prompt was already open when the response started.
            core.status_busy = True
            stdin_loop._CLI_SHUTDOWN.set()
            return "follow-up question"

    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "get_prompt", lambda: "User> ")
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(stdin_loop.sys, "stdin", _TTY())
    monkeypatch.setattr(stdin_loop, "_get_prompt_session", lambda: _Session())
    monkeypatch.setattr(stdin_loop, "_exit_prompt_application", lambda _app: None)
    monkeypatch.setattr(stdin_loop, "_make_prompt_key_bindings", lambda: None)
    monkeypatch.setattr(stdin_loop, "is_chat_mode", lambda: "off")
    monkeypatch.setattr(stdin_loop, "_append_prompt_history_entry", lambda _text: None)
    monkeypatch.setattr(stdin_loop, "forward_to_mesh", lambda _text: None)
    monkeypatch.setattr(stdin_loop, "_spinner_paused", lambda: nullcontext())

    import prompt_toolkit.patch_stdout

    monkeypatch.setattr(
        prompt_toolkit.patch_stdout, "patch_stdout", lambda: nullcontext()
    )
    stdin_loop._CLI_SHUTDOWN.clear()
    reset_typeahead_slot()
    try:
        stdin_loop.stdin_loop()
        event = events.get_nowait()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()
        reset_typeahead_slot()

    assert event == {
        "kind": "user",
        "text": "follow-up question",
        "cli_typeahead": True,
    }


def test_prompt_is_not_redrawn_while_status_is_busy(monkeypatch) -> None:
    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    prompt_busy_states: list[bool] = []

    class _Session:
        app = object()

        @staticmethod
        def prompt(_prompt, **_kwargs):
            prompt_busy_states.append(bool(core.status_busy))
            stdin_loop._CLI_SHUTDOWN.set()
            return None

    monkeypatch.setattr(core, "status_busy", True)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(stdin_loop.sys, "stdin", _TTY())
    monkeypatch.setattr(stdin_loop, "_get_prompt_session", lambda: _Session())
    monkeypatch.setattr(stdin_loop, "_exit_prompt_application", lambda _app: None)
    monkeypatch.setattr(stdin_loop, "_make_prompt_key_bindings", lambda: None)
    monkeypatch.setattr(stdin_loop, "is_chat_mode", lambda: "off")

    def finish_busy_wait(seconds: float) -> None:
        if seconds == 0.05:
            core.status_busy = False

    monkeypatch.setattr(stdin_loop.time, "sleep", finish_busy_wait)

    import prompt_toolkit.patch_stdout

    monkeypatch.setattr(
        prompt_toolkit.patch_stdout, "patch_stdout", lambda: nullcontext()
    )
    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert prompt_busy_states == [False]


@pytest.mark.parametrize("command", (":load 0", ":cont"))
def test_load_and_continue_stop_spinner_before_command_output(
    monkeypatch, command: str
) -> None:
    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    class _Session:
        app = object()

        @staticmethod
        def prompt(_prompt, **_kwargs):
            stdin_loop._CLI_SHUTDOWN.set()
            return command

    events: Queue = Queue()
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "get_prompt", lambda: "User> ")
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(
        core,
        "set_status",
        lambda busy, label="": calls.append(("status", (busy, label))),
    )
    monkeypatch.setattr(stdin_loop.sys, "stdin", _TTY())
    monkeypatch.setattr(stdin_loop, "_get_prompt_session", lambda: _Session())
    monkeypatch.setattr(stdin_loop, "_exit_prompt_application", lambda _app: None)
    monkeypatch.setattr(stdin_loop, "_make_prompt_key_bindings", lambda: None)
    monkeypatch.setattr(stdin_loop, "is_chat_mode", lambda: "off")
    monkeypatch.setattr(stdin_loop, "_append_prompt_history_entry", lambda _text: None)
    monkeypatch.setattr(stdin_loop, "forward_to_mesh", lambda _text: None)
    monkeypatch.setattr(stdin_loop, "_spinner_paused", lambda: nullcontext())
    monkeypatch.setattr(
        stdin_loop,
        "_stop_spinner_quietly",
        lambda: calls.append(("stop_spinner", None)),
    )

    import prompt_toolkit.patch_stdout

    monkeypatch.setattr(
        prompt_toolkit.patch_stdout, "patch_stdout", lambda: nullcontext()
    )
    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
        event = events.get_nowait()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert event == {"kind": "command", "text": command}
    assert calls == [
        ("status", (True, "command_pending")),
        ("stop_spinner", None),
    ]


def test_concurrent_typeahead_reservations_are_serialized() -> None:
    reset_typeahead_slot()
    barrier = Barrier(8)

    def reserve_after_barrier() -> bool:
        barrier.wait(timeout=2)
        return reserve_typeahead_slot()

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _index: reserve_after_barrier(), range(8)))

        assert results.count(True) == 1
        assert results.count(False) == 7
    finally:
        reset_typeahead_slot()
