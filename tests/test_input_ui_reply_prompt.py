"""Tests for withdrawing a stale human_ask [REPLY] prompt.

A plain human_ask reply prompt owns stdin only while its ask is
pending. The ask can also be answered from another channel: the Nostr
remote and bitchat bridges put the reply into the same queue the tool
waits on, and the tool then sets human_ask_active=False. The blocked
prompt_toolkit prompt must notice and return, so stdin_loop can drop
the stale [REPLY] prompt instead of leaving it on screen (and later
swallowing a line into a queue nobody reads).
"""

from __future__ import annotations

import threading
from contextlib import nullcontext

import pytest

from uagent import core
from uagent.cli_impl import input_ui


class _FakeApp:
    def __init__(self) -> None:
        self.is_running = True
        self.exited = threading.Event()
        self.result = None

    def exit(self, result=None) -> None:
        self.result = result
        self.is_running = False
        self.exited.set()


class _FakeSession:
    """A PromptSession stand-in whose prompt() blocks until exited."""

    def __init__(self) -> None:
        self.app = _FakeApp()

    def prompt(self, prompt, **kwargs):
        self.app.exited.wait(timeout=10)
        return self.app.result


@pytest.fixture()
def fake_session(monkeypatch):
    monkeypatch.delenv("UAGENT_NON_INTERACTIVE", raising=False)
    input_ui._CLI_SHUTDOWN.clear()
    # The stand-in does not interact with a terminal; avoid patch_stdout's
    # prompt-toolkit event-loop setup so the state watcher is the only thing
    # under test.
    import prompt_toolkit.patch_stdout

    monkeypatch.setattr(
        prompt_toolkit.patch_stdout, "patch_stdout", lambda: nullcontext()
    )
    session = _FakeSession()
    monkeypatch.setattr(input_ui, "_get_prompt_session", lambda reply=False: session)
    monkeypatch.setattr(input_ui, "_reset_prompt_sessions", lambda: None)
    monkeypatch.setattr(core, "human_ask_job_id", None, raising=False)
    yield session
    with core.human_ask_lock:
        core.human_ask_active = False
    input_ui._CLI_SHUTDOWN.clear()


def _run_prompt_async(**kwargs):
    outcome: dict = {}

    def run() -> None:
        outcome["line"] = input_ui._prompt_toolkit_input("[REPLY] > ", **kwargs)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def test_reply_prompt_withdrawn_when_ask_answered_elsewhere(fake_session) -> None:
    with core.human_ask_lock:
        core.human_ask_active = True
    thread, outcome = _run_prompt_async(reply=True)
    thread.join(timeout=0.5)
    assert thread.is_alive()

    # The bridge delivered a remote answer: the tool woke and released
    # stdin ownership.
    with core.human_ask_lock:
        core.human_ask_active = False

    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert outcome["line"] is None


def test_reply_prompt_stays_while_ask_pending(fake_session) -> None:
    with core.human_ask_lock:
        core.human_ask_active = True
    thread, _outcome = _run_prompt_async(reply=True)
    thread.join(timeout=0.6)
    # Nothing answered yet: the prompt must still be waiting for input.
    assert thread.is_alive()

    with core.human_ask_lock:
        core.human_ask_active = False
    thread.join(timeout=2.0)
    assert not thread.is_alive()
