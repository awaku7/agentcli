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


def test_read_file_contents_do_not_control_agent_step_status(
    monkeypatch, tmp_path
) -> None:
    from uagent.tools import read_file_tool

    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setenv(
        "UAGENT_SESSION_STORE_PATH", str(tmp_path / "read-sessions.sqlite3")
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *a: False
    )
    monkeypatch.setattr(read_file_tool, "sync_file", None)
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool",
        lambda name, args: read_file_tool.run_tool(args),
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

    source = tmp_path / "example.json"
    try:
        for index, content in enumerate(
            (
                '{"status":"blocked","error":"example"}',
                '{"ok":false,"error":"example"}',
                "Error: text in a document is not a failed tool call",
                "[python_exec timeout] source code being inspected",
            )
        ):
            source.write_text(content, encoding="utf-8")
            result_messages = []
            _execute_tool_calls(
                tool_calls_list=[
                    {
                        "id": f"read-{index}",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"filename": str(source)}),
                        },
                    }
                ],
                messages=result_messages,
                core=core,
                cache_mgr=_Cache(),
            )
            assert result_messages[0]["content"] == content
            state = store.get_agent_state(session_id)
            assert state is not None
            assert state["completed_steps"] == ["tool:read_file"]
            assert state["failed_steps"] == []

        source.unlink()
        _execute_tool_calls(
            tool_calls_list=[
                {
                    "id": "read-missing",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": json.dumps({"filename": str(source)}),
                    },
                }
            ],
            messages=[],
            core=core,
            cache_mgr=_Cache(),
        )
        state = store.get_agent_state(session_id)
        assert state is not None
        assert state["completed_steps"] == []
        assert state["failed_steps"] == ["tool:read_file"]
    finally:
        detach_opt_in_session_store(core)


def test_fetched_payload_is_not_treated_as_tool_status(monkeypatch, tmp_path) -> None:
    from uagent.tools import fetch_url_tool

    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setenv(
        "UAGENT_SESSION_STORE_PATH", str(tmp_path / "fetch-sessions.sqlite3")
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *a: False
    )

    class Response:
        headers = {"Content-Type": "application/json"}

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, max_bytes):
            return self.body[:max_bytes].encode("utf-8")

    responses = iter(
        [
            '{"status":"blocked","error":"example"}',
            "Error: This is an ordinary webpage",
        ]
    )
    monkeypatch.setattr(
        fetch_url_tool, "urlopen", lambda request: Response(next(responses))
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool",
        lambda name, args: fetch_url_tool.run_tool(args),
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
        for index, extract in enumerate(("json", "head")):
            _execute_tool_calls(
                tool_calls_list=[
                    {
                        "id": f"fetch-{index}",
                        "type": "function",
                        "function": {
                            "name": "fetch_url",
                            "arguments": json.dumps(
                                {"url": "https://example.test", "extract": extract}
                            ),
                        },
                    }
                ],
                messages=[],
                core=core,
                cache_mgr=_Cache(),
            )
            state = store.get_agent_state(session_id)
            assert state is not None
            assert state["completed_steps"] == ["tool:fetch_url"]
            assert state["failed_steps"] == []
    finally:
        detach_opt_in_session_store(core)


def test_localized_location_error_is_marked_failed(monkeypatch, tmp_path) -> None:
    from uagent.tools import current_location_tool

    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setenv(
        "UAGENT_SESSION_STORE_PATH", str(tmp_path / "location-sessions.sqlite3")
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *a: False
    )
    monkeypatch.setattr(
        current_location_tool,
        "_",
        lambda key, default=None: (
            "Erreur : Échec de la requête: {err}" if key == "err.generic" else default
        ),
    )

    def raise_location_error():
        raise RuntimeError("location backend unavailable")

    monkeypatch.setattr(current_location_tool, "_get_location", raise_location_error)
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool",
        lambda name, args: current_location_tool.run_tool(args),
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
        _execute_tool_calls(
            tool_calls_list=[
                {
                    "id": "location-error",
                    "type": "function",
                    "function": {
                        "name": "get_current_location",
                        "arguments": "{}",
                    },
                }
            ],
            messages=[],
            core=core,
            cache_mgr=_Cache(),
        )
        state = store.get_agent_state(session_id)
        assert state is not None
        assert state["completed_steps"] == []
        assert state["failed_steps"] == ["tool:get_current_location"]
    finally:
        detach_opt_in_session_store(core)
