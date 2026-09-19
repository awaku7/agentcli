from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.session_command_service import SessionRestorePlan
from uagent.runtime.session_restore import apply_persisted_state, bind_session


def test_bind_session_updates_core_and_callback_context() -> None:
    core = SimpleNamespace()
    callbacks = SimpleNamespace()
    store = object()

    bind_session(core, "session-1", store, callbacks_factory=lambda: callbacks)

    assert core.session_id == "session-1"
    assert core._session_store_active_id == "session-1"
    assert callbacks.session_id == "session-1"
    assert callbacks.session_store is store


def test_apply_persisted_state_updates_tool_and_responses_state() -> None:
    core = SimpleNamespace(
        tool_context={"old": True},
        responses_state={"last_response_status": "failed"},
    )
    plan = SessionRestorePlan(
        session_id="session-1",
        messages=[],
        tool_context={"browser": {"url": "https://example.test"}},
        response_state={
            "provider": "openai",
            "model": "gpt-5.4",
            "response_id": "resp-1",
            "status": "completed",
        },
        agent_state={
            "mcp_request_generation": 4,
            "mcp_provider": "openai",
            "mcp_model": "gpt-5.4",
        },
    )

    apply_persisted_state(core, plan)

    assert core.tool_context == {"browser": {"url": "https://example.test"}}
    assert core.responses_state == {
        "last_response_status": "completed",
        "provider": "openai",
        "model": "gpt-5.4",
        "previous_response_id": "resp-1",
    }
    assert core.agent_state_manager.state.mcp_request_generation == 4
    assert core.mcp_request_generation == 4
