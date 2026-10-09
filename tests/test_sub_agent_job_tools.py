from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.runtime.identity_context import TurnContext, bind_turn_context
from uagent.runtime.sub_agent_job_access import get_cli_job_runtime_context
from uagent.runtime.sub_agent_jobs import (
    CURRENT_SUB_AGENT_JOB_MODE,
    SubAgentJobOwner,
)
from uagent.tools.context import set_active_sub_agent


def _turn(entry_point: str = "cli", session_id: str = "session-a") -> TurnContext:
    return TurnContext(
        principal_id="local",
        room_id="",
        project_id="",
        session_id=session_id,
        entry_point=entry_point,
        authenticated=True,
        authn_kind="local",
    )


def test_job_runtime_context_is_cli_session_bound_and_foreground_only(monkeypatch):
    import uagent.core as core

    manager = object()
    owner = SubAgentJobOwner(entry_point="cli", session_id="session-a")
    monkeypatch.setattr(core, "_sub_agent_job_manager", manager, raising=False)
    monkeypatch.setattr(core, "_sub_agent_job_owner", owner, raising=False)

    with bind_turn_context(_turn()):
        assert get_cli_job_runtime_context() == (manager, owner)
        with bind_turn_context(_turn("web")):
            assert get_cli_job_runtime_context() is None
        with bind_turn_context(_turn(session_id="other")):
            assert get_cli_job_runtime_context() is None

        mode_token = CURRENT_SUB_AGENT_JOB_MODE.set("background")
        try:
            assert get_cli_job_runtime_context() is None
        finally:
            CURRENT_SUB_AGENT_JOB_MODE.reset(mode_token)

        active_token = set_active_sub_agent("planner")
        try:
            assert get_cli_job_runtime_context() is None
        finally:
            from uagent.tools.context import reset_active_sub_agent

            reset_active_sub_agent(active_token)


def test_job_tool_spec_filter_hides_or_shows_only_job_tools(monkeypatch):
    import uagent.tools as tools

    names = [
        "search_web",
        "spawn_sub_agent",
        "get_sub_agent_job",
        "wait_sub_agent_job",
        "send_sub_agent_message",
        "cancel_sub_agent_job",
    ]
    specs = [{"function": {"name": name}} for name in names]
    assert [
        item["function"]["name"]
        for item in tools._filter_sub_agent_job_tools(specs, allowed=False)
    ] == ["search_web"]
    assert tools._filter_sub_agent_job_tools(specs, allowed=True) == specs


def test_direct_job_tool_dispatch_fails_closed_outside_cli(monkeypatch):
    import uagent.tools as tools

    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(tools, "_sub_agent_job_tools_visible", lambda: False)
    result = json.loads(
        tools.run_tool("spawn_sub_agent", {"agent_name": "planner", "task": "x"})
    )
    assert result == {
        "status": "blocked",
        "reason": "foreground_main_agent_only",
        "message": "Sub-Agent Job orchestration is available only to an integrated foreground Main Agent.",
    }


def test_spawn_tool_binds_owner_shared_context_and_inbox_instructions(monkeypatch):
    from uagent.tools import spawn_sub_agent_tool, sub_agent_tool

    owner = SubAgentJobOwner(entry_point="cli", session_id="session-a")
    owner_expected = owner
    captured = {}

    class FakeManager:
        settings = SimpleNamespace(task_max_bytes=65536)

        def load_shared_results(self, *, owner, keys):
            assert owner == owner_expected
            assert keys == ["prior"]
            return {"prior": "earlier result"}, []

        def spawn(self, **kwargs):
            captured["spawn_args"] = kwargs
            context = SimpleNamespace(
                remaining=30.0,
                raise_if_cancelled=lambda: None,
                drain_messages=lambda: [{"sequence": 1, "message": "Check case B"}],
            )
            captured["worker_result"] = kwargs["worker"](context)
            return {
                "status": "accepted",
                "job_id": "sa_test",
                "agent_name": "planner",
            }

    manager = FakeManager()
    monkeypatch.setattr(
        spawn_sub_agent_tool, "get_job_runtime", lambda: (manager, owner)
    )

    def fake_sync_run(args):
        captured["subagent_args"] = args
        return "analysis result"

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_sync_run)
    result = json.loads(
        spawn_sub_agent_tool.run_tool(
            {
                "agent_name": "planner",
                "task": "Analyze the issue",
                "permission_level": "none",
                "load_keys": ["prior"],
            }
        )
    )
    assert result == {
        "status": "accepted",
        "job_id": "sa_test",
        "agent_name": "planner",
    }
    args = captured["subagent_args"]
    assert "Check case B" in args["task"]
    assert "analysis result" not in args["task"]
    assert args["_shared_context"] == {"prior": "earlier result"}
    assert captured["worker_result"] == "analysis result"


def test_structured_spawn_tool_passes_snapshot_without_shared_store_or_inbox(
    monkeypatch,
):
    from uagent.runtime.handoff_projection import HandoffBounds
    from uagent.runtime.sub_agent_handoff import SubAgentDispatch
    from uagent.tools import spawn_sub_agent_tool, sub_agent_tool

    owner = SubAgentJobOwner(entry_point="cli", session_id="session-a")
    dispatch = SubAgentDispatch(
        dispatch_id="dispatch-1",
        source_session_id="child-session",
        objective="Analyze only this task",
        bounds=HandoffBounds(owner.session_id, 0),
        _context_json='{"kind":"main_to_subagent"}',
        _source_refs=(),
        _source_access_check=lambda _ref: False,
        _store=object(),
    )
    captured = {}

    class FakeManager:
        settings = SimpleNamespace(task_max_bytes=65536)
        structured_handoff_enabled = True

        def load_shared_results(self, **_kwargs):
            raise AssertionError("structured jobs must not read the shared store")

        def spawn(self, **kwargs):
            captured["spawn_args"] = kwargs
            context = SimpleNamespace(
                handoff_dispatch=dispatch,
                remaining=30.0,
                raise_if_cancelled=lambda: None,
                drain_messages=lambda: (_ for _ in ()).throw(
                    AssertionError("structured jobs cannot drain live inbox")
                ),
            )
            captured["worker_result"] = kwargs["worker"](context)
            return {"status": "accepted", "job_id": "sa_structured"}

    manager = FakeManager()
    monkeypatch.setattr(
        spawn_sub_agent_tool, "get_job_runtime", lambda: (manager, owner)
    )

    def fake_sync_run(args, *, handoff_dispatch):
        captured["subagent_args"] = args
        captured["dispatch"] = handoff_dispatch
        return "structured result"

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_sync_run)
    result = json.loads(
        spawn_sub_agent_tool.run_tool(
            {
                "agent_name": "planner",
                "task": dispatch.objective,
                "permission_level": "none",
            }
        )
    )
    assert result == {"status": "accepted", "job_id": "sa_structured"}
    assert captured["dispatch"] is dispatch
    assert captured["subagent_args"]["task"] == dispatch.objective
    assert captured["subagent_args"]["_shared_context"] == {}
    assert captured["spawn_args"]["store_key"] is None
    assert captured["worker_result"] == "structured result"


def test_get_tool_specs_context_filters_job_tools_at_delivery_time(monkeypatch):
    import uagent.core as core
    import uagent.tools as tools

    owner = SubAgentJobOwner(entry_point="cli", session_id="session-a")
    monkeypatch.setattr(core, "_sub_agent_job_manager", object(), raising=False)
    monkeypatch.setattr(core, "_sub_agent_job_owner", owner, raising=False)
    monkeypatch.setattr(
        core, "register_tool_context_names", lambda _names: None, raising=False
    )
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(tools, "_hide_analyze_image_for_chat_vision", lambda: False)
    monkeypatch.setattr(tools, "_is_embedded_mode", lambda: False)
    monkeypatch.setattr(
        tools,
        "TOOL_SPECS",
        [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "spawn_sub_agent",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ],
    )
    monkeypatch.setattr(tools, "_TOOL_SPECS_CACHE", None)
    monkeypatch.setattr(tools, "_TOOL_SPECS_DIRTY", True)
    monkeypatch.setattr(tools, "_TOOL_SPECS_CACHE_EMBEDDED", None)
    monkeypatch.setattr(tools, "_ANALYZE_IMAGE_HIDDEN", None)

    hidden = tools.get_tool_specs()
    assert [item["function"]["name"] for item in hidden] == ["search_web"]
    with bind_turn_context(_turn()):
        visible = tools.get_tool_specs()
    assert {item["function"]["name"] for item in visible} == {
        "search_web",
        "spawn_sub_agent",
    }


def test_job_tools_are_discovered_as_plugins():
    import uagent.tools as tools

    tools._ensure_loaded()
    expected = {
        "spawn_sub_agent",
        "get_sub_agent_job",
        "wait_sub_agent_job",
        "send_sub_agent_message",
        "cancel_sub_agent_job",
    }
    assert expected.issubset(tools._RUNNERS)
    assert expected.issubset({spec["function"]["name"] for spec in tools.TOOL_SPECS})
