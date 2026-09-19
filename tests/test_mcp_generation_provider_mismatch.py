from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.agent_state import AgentState, AgentStateManager
from uagent.runtime.session_store import SessionStore
from uagent.util_common import _mcp_generation


def test_provider_switch_invalidates_restored_generation(tmp_path) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as store:
        session = store.create_session(project="demo", entry_point="test")
        store.save_agent_state(
            session.session_id,
            AgentState(
                mcp_request_generation=4,
                mcp_provider="openai",
                mcp_model="gpt-test",
            ).to_dict(),
        )
        manager = AgentStateManager(
            AgentState.from_dict(store.get_agent_state(session.session_id))
        )
        core = SimpleNamespace(
            responses_state={"provider": "anthropic", "model": "claude-test"},
            agent_state_manager=manager,
            save_agent_state=lambda state: store.save_agent_state(
                session.session_id, state
            ),
        )

        assert _mcp_generation(core) == 5
        persisted = store.get_agent_state(session.session_id)

    assert persisted is not None
    assert persisted["mcp_request_generation"] == 5
    assert persisted["mcp_provider"] == "anthropic"
    assert persisted["mcp_model"] == "claude-test"
