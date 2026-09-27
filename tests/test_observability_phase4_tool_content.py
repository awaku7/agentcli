from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from uagent.runtime.execution import mark_tool_waiting
from uagent.runtime.observability import runtime as observability_runtime
from uagent.runtime.observability import tool_content_capture
from uagent.runtime.observability.boundary_instrumentation import (
    _wrap_tool_content_runner,
)
from uagent.runtime.observability.content_capture import ContentCapturePolicy
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.tool_content_capture import (
    ToolContentCaptureBuffer,
    is_reviewed_tool_runner,
    make_tool_candidate,
)


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.events: list[tuple[str, dict[str, object]]] = []
        self.content_events: list[dict[str, object]] = []
        self.status: list[tuple[str, str | None]] = []

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes=None) -> None:
        self.events.append((name, dict(attributes or {})))

    def add_content_event(self, event: object) -> bool:
        attributes = event.attributes()
        if not attributes:
            return False
        self.content_events.append(attributes)
        return True

    def set_status(self, status: str, description: str | None = None) -> None:
        self.status.append((status, description))


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.spans: list[dict[str, object]] = []

    @contextmanager
    def start_span(self, operation: str, *, attributes=None, root=False):
        span = _Span()
        self.spans.append(
            {
                "operation": operation,
                "attributes": dict(attributes or {}),
                "root": root,
                "span": span,
            }
        )
        yield span


def _tool_settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset({"tool_arguments", "tool_result"}),
    )


def test_reviewed_calculator_adapter_emits_arguments_then_result() -> None:
    policy = ContentCapturePolicy.from_settings(_tool_settings())
    buffer = ToolContentCaptureBuffer(policy)

    arguments = make_tool_candidate(
        tool_name="calculator",
        category="tool_arguments",
        value={"expression": "1+2"},
        ordinal=1,
    )
    result = make_tool_candidate(
        tool_name="calculator",
        category="tool_result",
        value="[calculator]\nExpression: 1+2\nResult: 3",
        ordinal=2,
    )

    assert arguments is not None
    assert result is not None
    assert buffer.admit(arguments) is True
    assert buffer.admit(result) is True

    events = buffer.prepared_events()
    assert [event.category for event in events] == ["tool_arguments", "tool_result"]
    assert [event.ordinal for event in events] == [1, 2]
    assert events[0].value == '{"expression":"1+2"}'
    assert events[1].value == "[calculator]\nExpression: 1+2\nResult: 3"


def test_tool_adapter_requires_reviewed_builtin_runner() -> None:
    from uagent.tools.calculator_tool import run_tool as calculator_runner

    assert is_reviewed_tool_runner("calculator", calculator_runner) is True
    assert is_reviewed_tool_runner("calculator", lambda _args: "foreign") is False
    assert is_reviewed_tool_runner("read_file", calculator_runner) is False


def test_tool_adapter_rejects_unknown_or_mismatched_shape_after_admission() -> None:
    policy = ContentCapturePolicy.from_settings(_tool_settings())
    buffer = ToolContentCaptureBuffer(policy)

    candidate = make_tool_candidate(
        tool_name="calculator",
        category="tool_arguments",
        value={"unexpected": "1+2"},
        ordinal=1,
    )
    assert candidate is not None
    assert buffer.admit(candidate) is True
    assert buffer.prepared_events() == ()

    typed_buffer = ToolContentCaptureBuffer(policy)
    wrong_type = make_tool_candidate(
        tool_name="calculator",
        category="tool_arguments",
        value={"expression": 3},
        ordinal=1,
    )
    assert wrong_type is not None
    assert typed_buffer.admit(wrong_type) is True
    assert typed_buffer.prepared_events() == ()

    assert (
        make_tool_candidate(
            tool_name="read_file",
            category="tool_arguments",
            value={"filename": "private.txt"},
            ordinal=2,
        )
        is None
    )


def test_tool_adapter_rejects_schema_revision_mismatch(monkeypatch) -> None:
    changed_module = SimpleNamespace(
        TOOL_SPEC={
            "type": "function",
            "function": {
                "name": "calculator",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "enum": ["1+2"],
                        }
                    },
                    "required": ["expression"],
                },
            },
        }
    )
    monkeypatch.setattr(
        tool_content_capture,
        "import_module",
        lambda _module_name: changed_module,
    )

    policy = ContentCapturePolicy.from_settings(_tool_settings())
    buffer = ToolContentCaptureBuffer(policy)
    candidate = make_tool_candidate(
        tool_name="calculator",
        category="tool_arguments",
        value={"expression": "1+2"},
        ordinal=1,
    )

    assert candidate is not None
    assert buffer.admit(candidate) is True
    assert buffer.prepared_events() == ()


def test_tool_content_is_emitted_on_matching_execute_tool_span(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        observability_runtime,
        "get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        _tool_settings,
    )
    observability_runtime._reset_runtime_observability_for_tests()

    observability_runtime.before_structured_event(
        "tool.dispatch",
        {"tool": "calculator", "side_effect": "read"},
    )
    mark_tool_waiting()

    assert observability_runtime.capture_trusted_tool_arguments(
        "calculator", {"expression": "2+3"}
    )
    assert not observability_runtime.capture_trusted_tool_result(
        "get_current_time", "wrong owner"
    )
    assert observability_runtime.capture_trusted_tool_result(
        "calculator", "[calculator]\nExpression: 2+3\nResult: 5"
    )

    observability_runtime.before_structured_event(
        "tool.completed",
        {"tool": "calculator"},
    )
    observability_runtime.after_structured_event("tool.completed")

    assert len(backend.spans) == 1
    record = backend.spans[0]
    assert record["operation"] == "execute_tool"
    span = record["span"]
    assert isinstance(span, _Span)
    assert [event["uag.content.category"] for event in span.content_events] == [
        "tool_arguments",
        "tool_result",
    ]
    assert [event["uag.content.ordinal"] for event in span.content_events] == [1, 2]


def test_tool_runner_wrapper_captures_inside_runner_without_changing_result(
    monkeypatch,
) -> None:
    captured: list[tuple[str, str, object]] = []
    monkeypatch.setattr(
        observability_runtime,
        "capture_trusted_tool_arguments",
        lambda name, value: captured.append(("args", name, value)) or True,
    )
    monkeypatch.setattr(
        observability_runtime,
        "capture_trusted_tool_result",
        lambda name, value: captured.append(("result", name, value)) or True,
    )

    wrapped = _wrap_tool_content_runner(
        "calculator",
        lambda args: str(eval(args["expression"], {"__builtins__": {}}, {})),
    )
    result = wrapped({"expression": "4+5"})

    assert result == "9"
    assert captured == [
        ("args", "calculator", {"expression": "4+5"}),
        ("result", "calculator", "9"),
    ]


def test_tool_runner_wrapper_preserves_fail_open_capture_and_runner_errors(
    monkeypatch,
) -> None:
    def broken_capture(*_args, **_kwargs):
        raise RuntimeError("capture unavailable")

    monkeypatch.setattr(
        observability_runtime,
        "capture_trusted_tool_arguments",
        broken_capture,
    )
    monkeypatch.setattr(
        observability_runtime,
        "capture_trusted_tool_result",
        broken_capture,
    )

    wrapped = _wrap_tool_content_runner("get_current_time", lambda _args: "ok")
    assert wrapped({}) == "ok"

    def failing_runner(_args):
        raise ValueError("tool failed")

    wrapped_failure = _wrap_tool_content_runner("calculator", failing_runner)
    with pytest.raises(ValueError, match="tool failed"):
        wrapped_failure({"expression": "1/0"})
