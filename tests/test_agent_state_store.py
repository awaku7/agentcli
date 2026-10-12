from __future__ import annotations

from uagent.runtime.agent_state import AgentState, AgentStateManager
from uagent.runtime.session_store import SessionStore


def test_agent_state_is_saved_and_restored(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        state = AgentState(
            goal="ship feature",
            current_step="test",
            files=("src/app.py",),
            next_action="run pytest",
            mcp_request_generation=6,
        )
        store.save_agent_state(session.session_id, state.to_dict())

        restored = store.get_agent_state(session.session_id)

    assert restored is not None
    assert AgentState.from_dict(restored).goal == "ship feature"
    assert restored["files"] == ["src/app.py"]
    assert restored["next_action"] == "run pytest"
    assert restored["mcp_request_generation"] == 6


def test_failed_step_survives_session_store_reload(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        failed = AgentStateManager()
        failed.mark_step_failed("tool:fetch_url")
        store.save_agent_state(session.session_id, failed.state.to_dict())
        restored = store.get_agent_state(session.session_id)

    assert restored is not None
    assert AgentState.from_dict(restored).failed_steps == ("tool:fetch_url",)
    assert AgentState.from_dict(restored).completed_steps == ()
