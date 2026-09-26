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


def test_otel_span_emits_only_trusted_prepared_content_event():
    settings = _settings("user_input")
    policy = ContentCapturePolicy.from_settings(settings)
    event = prepare_content_event(
        make_text_candidate(category="user_input", value="hello", ordinal=1),
        policy,
    )
    assert event is not None

    raw = _RawSpan()
    span = OpenTelemetrySpan(raw, capture_content=True)
    assert span.add_content_event(event) is True
    assert raw.events == [
        (
            "uag.content",
            {
                "uag.content.category": "user_input",
                "uag.content.value": "hello",
                "uag.content.ordinal": 1,
            },
        )
    ]

    assert span.add_content_event(object()) is False
    assert len(raw.events) == 1

    disabled_raw = _RawSpan()
    disabled = OpenTelemetrySpan(disabled_raw, capture_content=False)
    assert disabled.add_content_event(event) is False
    assert disabled_raw.events == []


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
        assert (
            capture_logged_message({"role": "assistant", "content": "world"}) is True
        )
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


def test_disabled_nested_capture_scope_masks_enabled_parent():
    outer_span = _DedicatedSpan()
    inner_span = _DedicatedSpan()

    with bind_agent_content_capture(
        outer_span,
        _settings("user_input", "assistant_output"),
    ):
        assert capture_logged_message({"role": "user", "content": "outer"}) is True
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
    assert [event.attributes()["uag.content.value"] for event in outer_span.content_events] == [
        "outer",
        "outer reply",
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
