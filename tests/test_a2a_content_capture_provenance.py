from uagent.a2a.engine import _capture_trusted_a2a_user_message
from uagent.a2a.models import A2AMessage
from uagent.runtime.observability.content_runtime import bind_agent_content_capture
from uagent.runtime.observability.settings import ObservabilitySettings


def _settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset({"user_input"}),
        capture_max_field_chars=2048,
        capture_max_span_chars=8192,
    )


class _Span:
    def __init__(self) -> None:
        self.content_events = []

    def add_content_event(self, event):
        self.content_events.append(event)
        return True


def test_a2a_trusted_capture_requires_original_exact_string_content():
    structured = {"type": "file", "content": "private body"}
    A2AMessage(role="user", content=structured)

    structured_span = _Span()
    with bind_agent_content_capture(structured_span, _settings()):
        assert (
            _capture_trusted_a2a_user_message(
                {"role": "user", "content": str(structured)}
            )
            is False
        )

    assert structured_span.content_events == []

    A2AMessage(role="user", content="plain operator request")
    text_span = _Span()
    with bind_agent_content_capture(text_span, _settings()):
        assert (
            _capture_trusted_a2a_user_message(
                {"role": "user", "content": "plain operator request"}
            )
            is True
        )

    assert [event.attributes() for event in text_span.content_events] == [
        {
            "uag.content.category": "user_input",
            "uag.content.value": "plain operator request",
            "uag.content.ordinal": 1,
        }
    ]
