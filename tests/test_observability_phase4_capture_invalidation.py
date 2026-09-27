from uagent import core
from uagent.runtime.observability.content_runtime import (
    bind_agent_content_capture,
    capture_logged_message,
    discard_agent_content_capture,
)
from uagent.runtime.observability.settings import ObservabilitySettings


def _settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset({"assistant_output"}),
        capture_max_field_chars=2048,
        capture_max_span_chars=8192,
    )


class _Span:
    def __init__(self) -> None:
        self.content_events = []

    def add_content_event(self, event):
        self.content_events.append(event)
        return True


def test_explicit_discard_suppresses_buffered_and_later_content() -> None:
    span = _Span()
    before = {"role": "assistant", "content": "before"}
    after = {"role": "assistant", "content": "after"}

    with bind_agent_content_capture(span, _settings()):
        assert capture_logged_message(before) is True
        assert discard_agent_content_capture() is True
        assert capture_logged_message(after) is False

    assert span.content_events == []


def test_web_memory_projection_invalidation_discards_buffered_content(
    monkeypatch,
) -> None:
    span = _Span()
    message = {"role": "assistant", "content": "memory-derived"}
    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.setattr(core, "_memory_projection_invalidated", False, raising=False)

    with bind_agent_content_capture(span, _settings()):
        assert capture_logged_message(message) is True
        core._memory_projection_invalidated = True

    assert span.content_events == []


def test_non_web_memory_flag_does_not_discard_agent_content(monkeypatch) -> None:
    span = _Span()
    message = {"role": "assistant", "content": "cli reply"}
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "_memory_projection_invalidated", True, raising=False)

    with bind_agent_content_capture(span, _settings()):
        assert capture_logged_message(message) is True

    values = [event.attributes()["uag.content.value"] for event in span.content_events]
    assert values == ["cli reply"]
