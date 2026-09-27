from __future__ import annotations

from uagent.runtime.observability.content_runtime import (
    bind_agent_content_capture,
    capture_logged_message,
)
from uagent.runtime.observability.settings import ObservabilitySettings


class _Span:
    def __init__(self) -> None:
        self.content_events = []

    def add_content_event(self, event):
        self.content_events.append(event)
        return True


def _settings(*categories: str) -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset(categories),
        capture_max_field_chars=2048,
        capture_max_span_chars=8192,
    )


def test_in_span_synthetic_user_is_not_captured_as_operator_input() -> None:
    span = _Span()
    real_user = {"role": "user", "content": "real prompt"}
    synthetic_user = {"role": "user", "content": "tool-derived next action"}

    assert capture_logged_message(real_user) is True
    with bind_agent_content_capture(
        span,
        _settings("user_input", "assistant_output"),
    ):
        assert capture_logged_message(synthetic_user) is False
        assert capture_logged_message({"role": "assistant", "content": "reply"}) is True

    assert [event.attributes()["uag.content.value"] for event in span.content_events] == [
        "real prompt",
        "reply",
    ]


def test_rejected_next_user_submission_clears_blocked_pending_prompt() -> None:
    span = _Span()
    blocked = {"role": "user", "content": "blocked prompt"}
    later_attachment = {
        "role": "user",
        "content": "[Attached File] secret.txt",
        "attachments": [{"name": "secret.txt"}],
    }

    assert capture_logged_message(blocked) is True
    assert capture_logged_message(later_attachment) is False

    with bind_agent_content_capture(span, _settings("user_input")):
        pass

    assert span.content_events == []


def test_structured_next_user_submission_clears_older_pending_prompt() -> None:
    span = _Span()
    blocked = {"role": "user", "content": "blocked prompt"}
    later_multimodal = {
        "role": "user",
        "content": [{"type": "text", "text": "new prompt"}],
    }

    assert capture_logged_message(blocked) is True
    assert capture_logged_message(later_multimodal) is False

    with bind_agent_content_capture(span, _settings("user_input")):
        pass

    assert span.content_events == []
