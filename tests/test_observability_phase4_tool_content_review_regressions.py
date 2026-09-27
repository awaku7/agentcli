from __future__ import annotations

from uagent import tools
from uagent.runtime.observability import boundary_instrumentation
from uagent.runtime.observability import tool_content_capture
from uagent.runtime.observability.content_capture import ContentCapturePolicy
from uagent.runtime.observability.tool_content_capture import (
    ToolContentCaptureBuffer,
    make_tool_candidate,
)


def _policy(*categories: str) -> ContentCapturePolicy:
    return ContentCapturePolicy(
        enabled=True,
        categories=frozenset(categories),
        max_field_chars=4096,
        max_span_chars=8192,
    )


def test_tool_content_boundary_is_restored_after_runner_replacement(
    monkeypatch,
) -> None:
    def replacement(name, runner, args, *, tool_call_id):
        return runner(args)

    monkeypatch.setattr(boundary_instrumentation, "_INSTALLED", True)
    monkeypatch.setattr(tools, "_call_tool_runner", replacement)

    boundary_instrumentation.install_runtime_boundary_instrumentation()

    restored = tools._call_tool_runner
    assert restored is not replacement
    assert getattr(restored, "_uag_observability_content_wrapped", False) is True


def test_disabled_tool_argument_category_skips_shape_inspection(
    monkeypatch,
) -> None:
    buffer = ToolContentCaptureBuffer(_policy("tool_result"))
    candidate = make_tool_candidate(
        tool_name="calculator",
        category="tool_arguments",
        value={"expression": "1+2"},
        ordinal=1,
    )
    assert candidate is not None
    assert buffer.admit(candidate) is True

    def unexpected_shape_check(_candidate):
        raise AssertionError("disabled category must not inspect argument shape")

    monkeypatch.setattr(
        tool_content_capture,
        "_matches_reviewed_shape",
        unexpected_shape_check,
    )

    assert buffer.prepared_events() == ()


def test_oversized_tool_argument_mapping_is_rejected() -> None:
    buffer = ToolContentCaptureBuffer(_policy("tool_arguments"))
    value = {"expression": "1+2"}
    value.update({f"extra_{index}": "x" for index in range(64)})
    candidate = make_tool_candidate(
        tool_name="calculator",
        category="tool_arguments",
        value=value,
        ordinal=1,
    )
    assert candidate is not None
    assert buffer.admit(candidate) is True
    assert buffer.prepared_events() == ()
