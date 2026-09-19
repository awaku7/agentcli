from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from uagent.runtime.agent_state import AgentState, AgentStateManager
from uagent.runtime.session_command_service import SessionCommandService
from uagent.runtime.session_restore import apply_persisted_state
from uagent.runtime.session_store import SessionStore
from uagent.util_common import _host_is_cancelled, _mcp_generation


def test_restored_generation_is_bumped_and_saved_on_cancel(tmp_path) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as store:
        session = store.create_session(project="demo", entry_point="test")
        store.save_agent_state(
            session.session_id,
            AgentState(
                mcp_request_generation=11,
                mcp_provider="openai",
                mcp_model="gpt-test",
            ).to_dict(),
        )
        restored = store.get_agent_state(session.session_id)
        manager = AgentStateManager(AgentState.from_dict(restored))
        core = SimpleNamespace(
            interrupt_requested=True,
            cancellation_token=SimpleNamespace(is_cancelled=lambda: False),
            responses_state={"provider": "openai", "model": "gpt-test"},
            agent_state_manager=manager,
            save_agent_state=lambda state: store.save_agent_state(
                session.session_id, state
            ),
        )

        assert _mcp_generation(core) == 11
        assert _host_is_cancelled(core) is True
        assert core.mcp_request_generation == 12

        persisted = store.get_agent_state(session.session_id)

    assert persisted is not None
    assert persisted["mcp_request_generation"] == 12
    assert persisted["mcp_provider"] == "openai"
    assert persisted["mcp_model"] == "gpt-test"


def test_fresh_core_restore_rejects_late_mcp_response_after_host_cancel(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A process-boundary restore must retain the stale-response guard."""
    import uagent.tools.handle_mcp_v2_tool as mcp_tool
    from uagent.uagent_llm import _begin_responses_runtime

    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as store:
        session = store.create_session(project="demo", entry_point="test")
        store.save_agent_state(
            session.session_id,
            AgentState(
                mcp_request_generation=8,
                mcp_provider="openai",
                mcp_model="gpt-test",
            ).to_dict(),
        )
        store.record_response_state(
            session.session_id,
            provider="openai",
            model="gpt-test",
            response_id="resp_restored",
            status="completed",
        )

        service = SessionCommandService(store)
        plan = service.build_restore_plan(
            session.session_id,
            [{"role": "user", "content": "continue"}],
        )

        # This is deliberately a fresh host object: no in-memory generation or
        # ResponsesRuntime is carried across the simulated process boundary.
        core = SimpleNamespace(
            tool_context={},
            responses_state={},
            interrupt_requested=False,
            cancellation_token=SimpleNamespace(is_cancelled=lambda: False),
            save_agent_state=lambda state: store.save_agent_state(
                session.session_id, state
            ),
        )
        apply_persisted_state(core, plan)

        runtime = _begin_responses_runtime(
            core=core,
            provider="openai",
            model="gpt-test",
            enabled=True,
        )
        assert runtime is not None
        assert runtime.previous_response_id == "resp_restored"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def list_tools(self):
                return {"tools": []}

            async def call_tool(self, _name, _arguments):
                # The host is cancelled while the restored request is in
                # flight. The callback below also advances the generation.
                core.interrupt_requested = True
                return "LATE_AFTER_RESTORE"

        monkeypatch.setattr(mcp_tool, "MCPClient", lambda **_kwargs: FakeClient())
        monkeypatch.setattr(
            mcp_tool,
            "get_callbacks",
            lambda: SimpleNamespace(
                is_cancelled=lambda: _host_is_cancelled(core),
                request_generation=lambda: _mcp_generation(core),
            ),
        )

        out = asyncio.run(mcp_tool._call_mcp_http("http://example.com", "demo", {}))
        payload = json.loads(out)

        assert payload["ok"] is False
        assert payload["error"]["code"] == "MCP_STALE"
        assert core.mcp_request_generation == 9
        persisted = store.get_agent_state(session.session_id)

    assert persisted is not None
    assert persisted["mcp_request_generation"] == 9
