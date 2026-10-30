"""OTel SDK export regression for standard GenAI content attributes."""

from __future__ import annotations

import json

import pytest

from uagent.runtime.observability.content_capture import (
    ContentCapturePolicy,
    make_text_candidate,
    prepare_content_event,
)
from uagent.runtime.observability.otel_backend import OpenTelemetrySpan
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.tool_content_capture import (
    ToolContentCaptureBuffer,
    make_tool_candidate,
)


def _sdk_span(*, limit: int, use_global: bool = False):
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.sdk.trace import SpanLimits, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    if use_global:
        limits = SpanLimits(max_attribute_length=limit)
    else:
        limits = SpanLimits(max_span_attribute_length=limit)
    provider = TracerProvider(span_limits=limits)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@pytest.mark.parametrize("use_global", [False, True])
def test_genai_agent_json_is_not_truncated_by_sdk(use_global):
    provider, exporter = _sdk_span(limit=80, use_global=use_global)
    settings = ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset({"user_input"}),
    )
    policy = ContentCapturePolicy.from_settings(settings)
    tracer = provider.get_tracer(__name__)

    with tracer.start_as_current_span("invoke_agent") as raw:
        span = OpenTelemetrySpan(raw, operation="invoke_agent", capture_content=True)
        oversized = prepare_content_event(
            make_text_candidate(category="user_input", value="z" * 120, ordinal=1),
            policy,
        )
        assert oversized is not None
        assert span.add_content_event(oversized) is False
        assert "gen_ai.input.messages" not in raw.attributes

        admitted = prepare_content_event(
            make_text_candidate(category="user_input", value="ok", ordinal=2),
            policy,
        )
        assert admitted is not None
        assert span.add_content_event(admitted) is True

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert json.loads(spans[0].attributes["gen_ai.input.messages"]) == [
        {"role": "user", "parts": [{"type": "text", "content": "ok"}]}
    ]
    assert all(event.name != "uag.content" for event in spans[0].events)
    provider.shutdown()


def test_genai_tool_json_is_not_truncated_by_sdk():
    provider, exporter = _sdk_span(limit=90)
    settings = ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset({"tool_arguments", "tool_result"}),
    )
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
            value="z" * 120,
            ordinal=2,
        )
    )

    with provider.get_tracer(__name__).start_as_current_span("execute_tool") as raw:
        span = OpenTelemetrySpan(raw, operation="execute_tool", capture_content=True)
        assert buffer.emit_to(span) == 1

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert json.loads(spans[0].attributes["gen_ai.tool.call.arguments"]) == {
        "expression": "1+2"
    }
    assert "gen_ai.tool.call.result" not in spans[0].attributes
    assert all(event.name != "uag.content" for event in spans[0].events)
    provider.shutdown()
