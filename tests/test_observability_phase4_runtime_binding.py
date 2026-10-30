import json
from contextlib import contextmanager

from uagent.runtime.execution import lifecycle_execution
from uagent.runtime.observability.content_capture import (
    ContentCapturePolicy,
    make_text_candidate,
    prepare_content_event,
)
from uagent.runtime.observability.content_runtime import (
    bind_agent_content_capture,
    capture_logged_message,
    capture_trusted_user_message,
)
from uagent.runtime.observability.otel_backend import OpenTelemetrySpan
from uagent.runtime.observability.settings import ObservabilitySettings


def _settings(*categories: str) -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset(categories),
        capture_max_field_chars=2048,
        capture_max_span_chars=8192,
    )


def _disabled_settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=False,
        capture_categories=frozenset(),
        capture_max_field_chars=2048,
        capture_max_span_chars=8192,
    )


class _RawSpan:
    def __init__(self) -> None:
        self.events = []
        self.attributes = {}
        self.statuses = []

    def add_event(self, name, attributes=None):
        self.events.append((name, dict(attributes or {})))

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_status(self, status):
        self.statuses.append(status)


class _DedicatedSpan:
    def __init__(self) -> None:
        self.content_events = []
        self.attributes = {}
        self.statuses = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        return None

    def add_content_event(self, event):
        self.content_events.append(event)
        return True

    def record_exception(self, exc):
        return None

    def set_status(self, status, description=None):
        self.statuses.append((status, description))


class _Backend:
    enabled = True

    def __init__(self, span: _DedicatedSpan) -> None:
        self.span = span

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        yield self.span

    @contextmanager
    def attach_remote_context(self, carrier):
        yield False


def test_otel_span_uses_standard_genai_messages_without_legacy_events():
    settings = _settings("user_input")
    policy = ContentCapturePolicy.from_settings(settings)
    event = prepare_content_event(
        make_text_candidate(category="user_input", value="hello", ordinal=1),
        policy,
    )
    assert event is not None

    raw = _RawSpan()
    span = OpenTelemetrySpan(raw, capture_content=True, operation="invoke_agent")
    assert span.add_content_event(event) is True
    assert raw.events == []
    assert json.loads(raw.attributes["gen_ai.input.messages"]) == [
        {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
    ]

    # No duplicated ordinals, fabricated events or wrong semantic owners.
    assert span.add_content_event(event) is False
    assert span.add_content_event(object()) is False
    assert not any(key.startswith("uag.content") for key in raw.attributes)

    disabled_raw = _RawSpan()
    disabled = OpenTelemetrySpan(
        disabled_raw, capture_content=False, operation="invoke_agent"
    )
    assert disabled.add_content_event(event) is False
    assert disabled_raw.events == []
    assert disabled_raw.attributes == {}


def test_genai_output_is_single_latest_reply_not_multiple_model_choices():
    policy = ContentCapturePolicy.from_settings(_settings("assistant_output"))
    raw = _RawSpan()
    span = OpenTelemetrySpan(raw, capture_content=True, operation="invoke_agent")
    for ordinal, value in enumerate(("intermediate", "final"), 1):
        event = prepare_content_event(
            make_text_candidate(
                category="assistant_output", value=value, ordinal=ordinal
            ),
            policy,
        )
        assert event is not None
        assert span.add_content_event(event) is True
    assert json.loads(raw.attributes["gen_ai.output.messages"]) == [
        {"role": "assistant", "parts": [{"type": "text", "content": "final"}]}
    ]
    assert raw.events == []


def test_genai_tool_arguments_and_result_have_object_schema():
    from uagent.runtime.observability.tool_content_capture import (
        ToolContentCaptureBuffer,
        make_tool_candidate,
    )

    settings = _settings("tool_arguments", "tool_result")
    policy = ContentCapturePolicy.from_settings(settings)
    buffer = ToolContentCaptureBuffer(policy)
    assert buffer.admit(
        make_tool_candidate(
            tool_name="calculator",
            category="tool_arguments",
            value={"expression": "1+2"},
            ordinal=1,
        )
    )
    assert buffer.admit(
        make_tool_candidate(
            tool_name="calculator",
            category="tool_result",
            value="[calculator] Result: 3",
            ordinal=2,
        )
    )
    raw = _RawSpan()
    span = OpenTelemetrySpan(raw, capture_content=True, operation="execute_tool")
    assert buffer.emit_to(span) == 2
    assert json.loads(raw.attributes["gen_ai.tool.call.arguments"]) == {
        "expression": "1+2"
    }
    assert json.loads(raw.attributes["gen_ai.tool.call.result"]) == {
        "content": "[calculator] Result: 3"
    }
    assert raw.events == []

    # Tool data cannot land on an agent span and vice versa.
    other = OpenTelemetrySpan(_RawSpan(), capture_content=True, operation="chat")
    for event in buffer.prepared_events():
        assert other.add_content_event(event) is False


def test_lifecycle_binding_consumes_pending_user_and_emits_assistant(monkeypatch):
    span = _DedicatedSpan()
    backend = _Backend(span)
    settings = _settings("user_input", "assistant_output")

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: settings,
    )

    user_message = {"role": "user", "content": "hello"}
    assert capture_logged_message(user_message) is True

    with lifecycle_execution():
        assert capture_logged_message(user_message) is False
        assert capture_logged_message({"role": "assistant", "content": "world"}) is True
        assert span.content_events == []

    assert [event.attributes() for event in span.content_events] == [
        {
            "uag.content.category": "user_input",
            "uag.content.value": "hello",
            "uag.content.ordinal": 1,
        },
        {
            "uag.content.category": "assistant_output",
            "uag.content.value": "world",
            "uag.content.ordinal": 2,
        },
    ]


def test_pending_user_is_consumed_once(monkeypatch):
    first_span = _DedicatedSpan()
    second_span = _DedicatedSpan()
    spans = iter((first_span, second_span))
    backend = _Backend(first_span)
    settings = _settings("user_input")

    @contextmanager
    def start_span(operation, *, attributes=None, root=False):
        yield next(spans)

    backend.start_span = start_span

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: settings,
    )

    assert capture_logged_message({"role": "user", "content": "hello"}) is True

    with lifecycle_execution():
        pass
    with lifecycle_execution():
        pass

    assert [
        event.attributes()["uag.content.value"] for event in first_span.content_events
    ] == ["hello"]
    assert second_span.content_events == []


def test_disabled_nested_capture_scope_masks_enabled_parent():
    outer_span = _DedicatedSpan()
    inner_span = _DedicatedSpan()
    outer_user = {"role": "user", "content": "outer"}

    assert capture_logged_message(outer_user) is True
    with bind_agent_content_capture(
        outer_span,
        _settings("user_input", "assistant_output"),
    ):
        assert capture_logged_message(outer_user) is False
        with bind_agent_content_capture(inner_span, _disabled_settings()):
            assert (
                capture_logged_message({"role": "assistant", "content": "inner"})
                is False
            )
        assert (
            capture_logged_message({"role": "assistant", "content": "outer reply"})
            is True
        )

    assert inner_span.content_events == []
    assert [
        event.attributes()["uag.content.value"] for event in outer_span.content_events
    ] == [
        "outer",
        "outer reply",
    ]


def test_attachment_envelopes_are_never_capture_eligible():
    span = _DedicatedSpan()
    user_with_attachment = {
        "role": "user",
        "content": "[Attached File] report.txt\n[File Path] C:/private/report.txt",
        "attachments": [{"name": "report.txt"}],
    }
    assistant_with_attachment = {
        "role": "assistant",
        "content": "attachment reply",
        "attachments": [{"name": "result.txt"}],
    }

    assert capture_logged_message(user_with_attachment) is False
    with bind_agent_content_capture(
        span,
        _settings("user_input", "assistant_output"),
    ):
        assert capture_logged_message(user_with_attachment) is False
        assert capture_logged_message(assistant_with_attachment) is False

    assert span.content_events == []


def test_trusted_a2a_user_boundary_preserves_real_input_only():
    span = _DedicatedSpan()
    trusted_user = {"role": "user", "content": "a2a operator request"}
    synthetic_user = {"role": "user", "content": "tool-generated next action"}

    with bind_agent_content_capture(
        span,
        _settings("user_input", "assistant_output"),
    ):
        assert capture_trusted_user_message(trusted_user) is True
        assert capture_logged_message(trusted_user) is False
        assert capture_logged_message(synthetic_user) is False
        assert (
            capture_logged_message({"role": "assistant", "content": "a2a reply"})
            is True
        )

    assert [event.attributes() for event in span.content_events] == [
        {
            "uag.content.category": "user_input",
            "uag.content.value": "a2a operator request",
            "uag.content.ordinal": 1,
        },
        {
            "uag.content.category": "assistant_output",
            "uag.content.value": "a2a reply",
            "uag.content.ordinal": 2,
        },
    ]


def test_lifecycle_binding_fails_closed_for_structured_or_internal_messages(
    monkeypatch,
):
    span = _DedicatedSpan()
    backend = _Backend(span)
    settings = _settings("user_input", "assistant_output")

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: settings,
    )

    assert (
        capture_logged_message(
            {"role": "user", "content": [{"type": "text", "text": "hello"}]}
        )
        is False
    )

    with lifecycle_execution():
        assert (
            capture_logged_message(
                {"role": "assistant", "content": "hidden", "_uagent_internal": True}
            )
            is False
        )
        assert (
            capture_logged_message(
                {"role": "assistant", "content": "hidden", "_uagent_ui_only": True}
            )
            is False
        )
        assert capture_logged_message({"role": "system", "content": "hidden"}) is False
        assert capture_logged_message({"role": "tool", "content": "hidden"}) is False

    assert span.content_events == []
