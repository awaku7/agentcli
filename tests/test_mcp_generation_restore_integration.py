from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.agent_state import AgentState, AgentStateManager
from uagent.runtime.session_store import SessionStore
from uagent.util_common import _host_is_cancelled, _mcp_generation


def test_restored_generation_is_bumped_and_saved_on_cancel(tmp_path) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as store:
        session = store.create_session(project="demo", entry_point="test")
        store.save_agent_state(
            session.session_id,
            AgentState(mcp_request_generation=11).to_dict(),
        )
        restored = store.get_agent_state(session.session_id)
        manager = AgentStateManager(AgentState.from_dict(restored))
        core = SimpleNamespace(
            interrupt_requested=True,
            cancellation_token=SimpleNamespace(is_cancelled=lambda: False),
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
