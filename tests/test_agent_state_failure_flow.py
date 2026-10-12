from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.llm_flow_helpers import _execute_tool_calls
from uagent.runtime.session_store import (
    attach_opt_in_session_store,
    detach_opt_in_session_store,
)


class _Cache:
    def record_file_access(self, filename):
        pass


def test_tool_failure_is_not_persisted_as_completed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(tmp_path / "sessions.sqlite3"))
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *args: False
    )

    results = iter(
        [
            json.dumps({"ok": False, "error": "simulated failure"}),
            "[tool argument error] name='demo' err=invalid alias",
            "[tool error] unknown tool: demo",
            "Error: plugin failed",
            "[ツール引数エラー] 無効な引数",
            "[ツール実行時エラー] 実行に失敗",
            "エラー: ツール実行失敗",
            "[get_env error] required name missing",
            json.dumps({"status": "blocked", "reason": "permission denied"}),
            "source: timeout = 30; cancelled = False",
            json.dumps({"ok": True}),
        ]
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool", lambda name, args: next(results)
    )
    core = SimpleNamespace(
        log_message=lambda message: None,
        set_status=lambda *args: None,
        show_tool_output=False,
    )
    store, session_id = attach_opt_in_session_store(
        core, project_path=tmp_path, entry_point="test"
    )
    assert store is not None
    assert session_id

    try:
        for call_id, expected_failed in (
            ("json-failure", True),
            ("argument-error", True),
            ("unknown-tool", True),
            ("plugin-error", True),
            ("localized-args", True),
            ("localized-runtime", True),
            ("localized-tool", True),
            ("get-env", True),
            ("blocked", True),
            ("payload-keywords", False),
            ("retry-success", False),
        ):
            tool_calls = [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "demo", "arguments": "{}"},
                }
            ]
            _execute_tool_calls(
                tool_calls_list=tool_calls,
                messages=[],
                core=core,
                cache_mgr=_Cache(),
            )
            state = store.get_agent_state(session_id)
            assert state is not None
            if expected_failed:
                assert state["failed_steps"] == ["tool:demo"]
                assert "tool:demo" not in state["completed_steps"]
            else:
                assert state["failed_steps"] == []
                assert state["completed_steps"] == ["tool:demo"]
    finally:
        detach_opt_in_session_store(core)
