from __future__ import annotations

from uagent.runtime import spinner
from uagent.tools import sub_agent_tool


def test_judge_event_clears_spinner_before_print(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(spinner, "stop_quietly", lambda: events.append("stop"))
    monkeypatch.setattr(
        "builtins.print", lambda message, **kwargs: events.append(message)
    )

    sub_agent_tool._print_sub_agent_judge_event("[SUBAGENT:judge] judgment=COMPLETE")

    assert events == ["stop", "[SUBAGENT:judge] judgment=COMPLETE"]
