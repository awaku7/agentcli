from uagent.runtime.execution import reset_tool_runner_active, set_tool_runner_active
from uagent.runtime.observability.content_runtime import (
    bind_agent_content_capture,
    capture_logged_message,
)
from uagent.runtime.observability.settings import ObservabilitySettings


class _DedicatedSpan:
    def __init__(self) -> None:
        self.content_events = []

    def add_content_event(self, event):
        self.content_events.append(event)
        return True


def _settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset({"assistant_output"}),
        capture_max_field_chars=2048,
        capture_max_span_chars=8192,
    )


def test_tool_runner_assistant_log_is_not_agent_output():
    span = _DedicatedSpan()

    with bind_agent_content_capture(span, _settings()):
        token = set_tool_runner_active(True)
        try:
            assert (
                capture_logged_message(
                    {"role": "assistant", "content": "tool-owned raw result"}
                )
                is False
            )
        finally:
            reset_tool_runner_active(token)

        assert (
            capture_logged_message({"role": "assistant", "content": "model reply"})
            is True
        )

    assert [event.attributes()["uag.content.value"] for event in span.content_events] == [
        "model reply"
    ]
