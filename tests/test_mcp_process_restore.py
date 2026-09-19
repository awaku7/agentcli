from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from uagent.runtime.agent_state import AgentState
from uagent.runtime.session_store import SessionStore

_PROCESS_RESTORE_SCRIPT = textwrap.dedent("""
    import json
    import sys
    from types import SimpleNamespace

    from uagent.runtime.session_command_service import SessionCommandService
    from uagent.runtime.session_restore import apply_persisted_state
    from uagent.runtime.session_store import SessionStore
    from uagent.uagent_llm import _begin_responses_runtime

    db_path, session_id = sys.argv[1:3]
    with SessionStore(db_path) as store:
        plan = SessionCommandService(store).build_restore_plan(
            session_id,
            [{"role": "user", "content": "continue"}],
        )
        core = SimpleNamespace(tool_context={}, responses_state={})
        apply_persisted_state(core, plan)
        restored = _begin_responses_runtime(
            core=core,
            provider="openai",
            model="gpt-test",
            enabled=True,
        )
        restored_response_id = (
            restored.previous_response_id if restored is not None else None
        )
        switched = _begin_responses_runtime(
            core=core,
            provider="anthropic",
            model="claude-test",
            enabled=True,
        )
        print(
            json.dumps(
                {
                    "generation": core.mcp_request_generation,
                    "response_id": restored_response_id,
                    "switched_response_id": (
                        switched.previous_response_id if switched is not None else None
                    ),
                    "legacy_previous_response_id": core.responses_state.get(
                        "previous_response_id"
                    ),
                }
            )
        )
    """)


def test_real_process_restore_reloads_generation_and_drops_mismatched_continuation(
    tmp_path,
) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as store:
        session = store.create_session(project="demo", entry_point="test")
        store.save_agent_state(
            session.session_id,
            AgentState(
                mcp_request_generation=13,
                mcp_provider="openai",
                mcp_model="gpt-test",
            ).to_dict(),
        )
        store.record_response_state(
            session.session_id,
            provider="openai",
            model="gpt-test",
            response_id="resp_process_restore",
            status="completed",
        )

    env = os.environ.copy()
    project_root = Path(__file__).resolve().parents[1]
    source_root = str(project_root / "src")
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        source_root
        if not current_pythonpath
        else source_root + os.pathsep + current_pythonpath
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _PROCESS_RESTORE_SCRIPT,
            str(db_path),
            session.session_id,
        ],
        cwd=str(project_root),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "generation": 13,
        "response_id": "resp_process_restore",
        "switched_response_id": None,
        "legacy_previous_response_id": None,
    }
