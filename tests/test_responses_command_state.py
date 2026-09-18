from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.responses_command_state import ResponsesCommandState


def test_state_prefers_explicit_active_and_previous_response_ids() -> None:
    core = SimpleNamespace(
        responses_state={
            "provider": "OpenAI",
            "active_response_id": "active-1",
            "previous_response_id": "previous-1",
        }
    )

    state = ResponsesCommandState.from_core(core)

    assert state.provider == "openai"
    assert state.resolve_id() == "active-1"
    assert state.resolve_id("explicit-1") == "explicit-1"
    assert state.is_current("active-1") is True
    assert state.is_current("previous-1") is False


def test_state_falls_back_to_core_provider_and_previous_id() -> None:
    core = SimpleNamespace(
        provider="azure",
        responses_state={"previous_response_id": "previous-1"},
    )

    state = ResponsesCommandState.from_core(core)

    assert state.provider == "azure"
    assert state.resolve_id() == "previous-1"
    assert state.is_current("previous-1") is True


def test_state_is_empty_for_invalid_host_state() -> None:
    state = ResponsesCommandState.from_core(
        SimpleNamespace(responses_state=None, provider=None)
    )

    assert state.provider == ""
    assert state.resolve_id() == ""
    assert state.is_current("response-1") is False
