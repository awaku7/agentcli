from __future__ import annotations

from uagent.runtime.tool_result_manager import ContextResultManager


def test_small_result_is_direct_for_llm_and_preserves_ui_value() -> None:
    manager = ContextResultManager(inline_limit_chars=20, large_limit_chars=30)

    record, projections = manager.process(
        {"ok": True}, tool_name="example", session_id="session-1"
    )

    assert record.result_class == "small"
    assert record.session_id == "session-1"
    assert projections.llm_context == '{"ok": true}'
    assert projections.ui_remote == {"ok": True}
    assert projections.persistent_history == {"ok": True}


def test_summary_is_derived_from_structured_result() -> None:
    manager = ContextResultManager()

    record, _ = manager.process(
        {"status": "success", "items": [1, 2]}, tool_name="example"
    )

    assert record.summary == "success"


def test_large_result_gets_bounded_llm_projection() -> None:
    manager = ContextResultManager(inline_limit_chars=10, large_limit_chars=20)

    record, projections = manager.process(
        "0123456789abcdefghij", tool_name="example", artifact_ref="artifact://a1"
    )

    assert record.result_class == "large"
    assert "result_id: " + record.result_id in projections.llm_context
    assert "artifact_ref: artifact://a1" in projections.llm_context
    assert "preview:" in projections.llm_context
    assert projections.ui_remote == "0123456789abcdefghij"


def test_huge_result_is_classified_without_storage_side_effect() -> None:
    manager = ContextResultManager(inline_limit_chars=2, large_limit_chars=4)

    record, projections = manager.process(
        "0123456789", tool_name="example", summary="ten chars"
    )

    assert record.result_class == "huge"
    assert record.size_bytes == 10
    assert "summary: ten chars" in projections.llm_context
    assert projections.persistent_history == "0123456789"


def test_binary_history_projection_is_sanitized_but_ui_projection_is_not() -> None:
    manager = ContextResultManager()
    value = {"image_b64": "secret", "caption": "preview"}

    _, projections = manager.process(value, tool_name="image_tool")

    assert projections.ui_remote == value
    assert projections.persistent_history["image_b64"] != "secret"
    assert projections.persistent_history["caption"] == "preview"


def test_retrieved_context_is_bounded_and_references_results() -> None:
    manager = ContextResultManager()

    context = manager.format_retrieved_context(
        [
            {
                "result_id": "result-1",
                "tool_name": "read_file",
                "result_class": "large",
                "summary": "configuration source",
                "artifact_ref": "artifact://cfg",
            }
        ],
        max_chars=200,
    )

    assert "result-1" in context
    assert "configuration source" in context
    assert "artifact_preview" not in context
    preview_context = manager.format_retrieved_context(
        [{"artifact_preview": "text from artifact"}], max_chars=200
    )
    assert "text from artifact" in preview_context
    assert len(context) <= 200
    assert (
        len(manager.format_retrieved_context([{"summary": "x" * 500}], max_chars=50))
        <= 50
    )


def test_structured_large_results_keep_head_tail_rows() -> None:
    manager = ContextResultManager(
        inline_limit_chars=100,
        large_limit_chars=200,
        max_preview_rows=3,
    )

    record, projections = manager.process(
        [{"row": index} for index in range(10)], tool_name="table"
    )

    assert record.result_class == "large"
    assert '"row": 0' in projections.llm_context
    assert '"row": 9' in projections.llm_context
    assert "rows omitted" in projections.llm_context
    assert len(projections.llm_context) > 0


def test_structured_mapping_preview_respects_single_key_limit() -> None:
    manager = ContextResultManager(
        inline_limit_chars=150,
        large_limit_chars=400,
        max_preview_rows=1,
    )

    _, projections = manager.process(
        {
            "first": "a" * 80,
            "middle": "b" * 80,
            "last": "c" * 80,
        },
        tool_name="mapping",
    )

    assert '"first":' in projections.llm_context
    assert '"middle":' not in projections.llm_context
    assert '"last":' not in projections.llm_context
    assert '"... omitted keys ...": 2' in projections.llm_context


def test_context_manager_applies_policy_row_limit(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_ROWS", "2")
    from uagent.runtime.context_manager import ContextManager

    manager = ContextManager.from_environment()
    _, projections = manager.process_result(
        [{"row": index} for index in range(2000)], tool_name="table"
    )

    assert '"row": 0' in projections.llm_context
    assert '"row": 1999' in projections.llm_context
    assert "rows omitted" in projections.llm_context


def test_invalid_limits_are_rejected() -> None:
    try:
        ContextResultManager(inline_limit_chars=10, large_limit_chars=5)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid limits should raise ValueError")
