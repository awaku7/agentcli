from __future__ import annotations

from uagent.runtime.agent_state import AgentState
from uagent.runtime.session_store import SessionStore


def test_agent_state_is_saved_and_restored(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        state = AgentState(
            goal="ship feature",
            current_step="test",
            files=("src/app.py",),
            next_action="run pytest",
        )
        store.save_agent_state(session.session_id, state.to_dict())

        restored = store.get_agent_state(session.session_id)

    assert restored is not None
    assert AgentState.from_dict(restored).goal == "ship feature"
    assert restored["files"] == ["src/app.py"]
    assert restored["next_action"] == "run pytest"
