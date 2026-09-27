from __future__ import annotations

from contextlib import contextmanager

from uagent.cli_startup import _call_cli_startup_turn


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
