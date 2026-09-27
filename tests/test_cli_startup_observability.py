from __future__ import annotations

from contextlib import contextmanager

from uagent.cli_startup import _call_cli_startup_turn, _log_startup_file_message
from uagent.runtime.observability.content_runtime import capture_logged_message


def test_cli_startup_turn_enters_lifecycle_before_resolved_context(
    monkeypatch, tmp_path
) -> None:
    events = []

    @contextmanager
    def fake_lifecycle():
        events.append("lifecycle-enter")
        try:
            yield None
        finally:
            events.append("lifecycle-exit")

    def fake_call(fn, *args, **kwargs):
        events.append(
            (
                "turn-context",
                kwargs.pop("entry_point"),
                kwargs.pop("project_path"),
                kwargs.pop("session_id"),
            )
        )
        return fn(*args, **kwargs)

    monkeypatch.setattr(
        "uagent.runtime.execution.lifecycle_execution",
        fake_lifecycle,
    )
    monkeypatch.setattr(
        "uagent.runtime.turn_context_runtime.call_with_resolved_turn_context",
        fake_call,
    )

    result = _call_cli_startup_turn(
        lambda value: events.append(("fn", value)) or value,
        "ok",
        project_path=str(tmp_path),
        session_id="session-1",
    )

    assert result == "ok"
    assert events == [
        "lifecycle-enter",
        ("turn-context", "cli", str(tmp_path), "session-1"),
        ("fn", "ok"),
        "lifecycle-exit",
    ]


def test_startup_file_logging_marks_only_the_log_envelope() -> None:
    logged = []

    class Core:
        @staticmethod
        def log_message(message):
            logged.append(message)

    provider_message = {
        "role": "user",
        "content": "Startup file provided: C:/private/notes.txt\n\nsecret body",
    }
    original = dict(provider_message)

    _log_startup_file_message(Core(), provider_message)

    assert provider_message == original
    assert logged[0] is not provider_message
    assert logged[0]["attachments"] is True
    assert capture_logged_message(logged[0]) is False
