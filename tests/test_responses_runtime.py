from __future__ import annotations

import pytest

from uagent.providers.responses_runtime import (
    ContinuationInvariantError,
    DuplicateToolOutput,
    ResponsesRuntime,
    UnknownToolOutput,
)
from uagent.runtime.round_runtime import RetryRequest


def test_restore_and_continue_requires_provider_capability() -> None:
    runtime = ResponsesRuntime("openai", model="gpt-5.4")

    assert runtime.restore_continuation(
        "resp_1", session_generation=2, provider="openai", model="gpt-5.4"
    )
    assert runtime.state == "Restored"
    runtime.begin_request(previous_response_id="resp_1")
    assert runtime.state == "Active"

    stateless = ResponsesRuntime("openrouter")
    with pytest.raises(ContinuationInvariantError):
        stateless.begin_request(previous_response_id="resp_1")
    assert stateless.previous_response_id is None


def test_provider_switch_clears_continuation() -> None:
    runtime = ResponsesRuntime("openai", model="gpt-5.4")
    assert runtime.restore_continuation("resp_1", session_generation=1)

    runtime.switch_provider("azure", model="gpt-5.4")

    assert runtime.provider == "azure"
    assert runtime.previous_response_id is None
    assert runtime.state == "Fresh"


def test_tool_outputs_are_matched_once_by_response_and_generation() -> None:
    runtime = ResponsesRuntime("openai", session_generation=3)
    runtime.begin_request()
    runtime.record_response(
        "resp_1",
        tool_calls=[{"id": "call-1", "type": "function"}],
    )
    assert runtime.state == "AwaitingToolOutput"

    runtime.accept_tool_output("resp_1", "call-1", {"ok": True})
    assert runtime.state == "Continuing"

    with pytest.raises(DuplicateToolOutput):
        runtime.accept_tool_output("resp_1", "call-1", {"ok": True})
    assert runtime.state == "Failed"
    assert runtime.previous_response_id is None


def test_continuation_cannot_bypass_pending_tool_outputs() -> None:
    runtime = ResponsesRuntime("openai")
    runtime.begin_request()
    runtime.record_response("resp_1", tool_calls=[{"id": "call-1"}])

    with pytest.raises(ContinuationInvariantError):
        runtime.begin_request(previous_response_id="resp_1")

    assert runtime.state == "AwaitingToolOutput"


def test_unknown_or_wrong_generation_tool_output_cannot_continue() -> None:
    runtime = ResponsesRuntime("openai", session_generation=4)
    runtime.begin_request()
    runtime.record_response("resp_1", tool_calls=[{"id": "call-1"}])

    with pytest.raises(UnknownToolOutput):
        runtime.accept_tool_output("resp_1", "call-unknown", {}, session_generation=4)
    assert runtime.state == "Failed"
    assert runtime.accept_retry(
        RetryRequest(reason="feature_fallback", detail="new turn"),
        authorized=True,
    )

    runtime.begin_request()
    runtime.record_response("resp_2", tool_calls=[{"id": "call-2"}])
    with pytest.raises(UnknownToolOutput):
        runtime.accept_tool_output("resp_2", "call-2", {}, session_generation=99)
    assert runtime.state == "Failed"


def test_failed_tool_output_clears_continuation() -> None:
    runtime = ResponsesRuntime("openai")
    runtime.begin_request()
    runtime.record_response("resp_1", tool_calls=[{"id": "call-1"}])

    with pytest.raises(ContinuationInvariantError):
        runtime.accept_tool_output("resp_1", "call-1", {}, failed=True)

    assert runtime.state == "Failed"
    assert runtime.previous_response_id is None


def test_interrupt_cancel_and_timeout_clear_response_ids() -> None:
    for method_name, expected_state in (
        ("interrupt", "Interrupted"),
        ("cancel", "Cancelled"),
        ("timeout", "TimedOut"),
    ):
        runtime = ResponsesRuntime("openai")
        runtime.begin_request()
        runtime.record_response("resp_1")

        getattr(runtime, method_name)()

        assert runtime.state == expected_state
        assert runtime.previous_response_id is None
        assert runtime.active_response_id is None
        assert runtime.pending_tool_calls == ()


def test_stale_retry_is_authorized_by_attempt_budget() -> None:
    runtime = ResponsesRuntime("openai")
    runtime.restore_continuation("resp_old", session_generation=1)
    request = runtime.request_stale_retry()

    assert request == RetryRequest(
        reason="stale_continuation", detail="stale continuation"
    )
    assert runtime.state == "Stale"
    assert runtime.accept_retry(request, authorized=True)
    assert runtime.state == "Fresh"

    denied = runtime.request_stale_retry("second stale")
    assert runtime.accept_retry(denied, authorized=False) is False
    assert runtime.state == "Failed"


def test_snapshot_contains_safe_continuation_metadata() -> None:
    runtime = ResponsesRuntime("openai", model="gpt-5.4", session_generation=7)
    runtime.begin_request()
    runtime.record_response("resp_1", tool_calls=[{"id": "call-1"}])

    snapshot = runtime.snapshot()

    assert snapshot["provider"] == "openai"
    assert snapshot["session_generation"] == 7
    assert snapshot["pending_tool_calls"] == [
        {
            "response_id": "resp_1",
            "tool_call_id": "call-1",
            "session_generation": 7,
        }
    ]
    assert "output" not in snapshot


def test_restore_requires_trusted_input_fingerprint_when_expected() -> None:
    unavailable = ResponsesRuntime("openai", model="gpt-5.4")

    assert not unavailable.restore_continuation(
        "resp_1",
        session_generation=1,
        expected_input_fingerprint="opaque-digest",
        input_fingerprint_status="unavailable",
    )
    assert unavailable.previous_response_id is None

    valid = ResponsesRuntime("openai", model="gpt-5.4")
    assert valid.restore_continuation(
        "resp_1",
        session_generation=1,
        expected_input_fingerprint="opaque-digest",
        input_fingerprint_status="valid",
    )
