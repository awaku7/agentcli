from __future__ import annotations

import json

from uagent import tools
from uagent.tools import sub_agent_tool


def test_read_only_sub_agent_dispatches_only_allowlisted_read_tools(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    calls = []
    monkeypatch.setattr(
        tools,
        "run_tool",
        lambda name, args: calls.append((name, args)) or "file contents",
    )

    results = runner._execute_tool_calls(
        'read_file(filename="notes.txt") create_file(filename="x", content="no")',
        "read_only",
        "general",
    )

    assert calls == [("read_file", {"filename": "notes.txt"})]
    assert any("[tool:read_file success]" in result for result in results)
    blocked = next(
        result for result in results if "[tool:create_file blocked]" in result
    )
    assert json.loads(blocked.split("\n", 1)[1])["status"] == "blocked"


def test_propose_only_create_file_is_recorded_but_never_executed(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    calls = []
    monkeypatch.setattr(
        tools,
        "run_tool",
        lambda name, args: calls.append((name, args)) or "unexpected execution",
    )

    result, status = runner._run_permissioned_tool(
        "create_file",
        {"filename": "draft.txt", "content": "proposal", "overwrite": False},
        "propose_only",
        "general",
    )

    proposal = json.loads(result)
    assert status == "proposed"
    assert proposal["status"] == "proposed"
    assert proposal["executed"] is False
    assert proposal["arguments"]["filename"] == "draft.txt"
    assert calls == []


def test_propose_only_rejects_overwrite_and_other_mutations():
    runner = sub_agent_tool.SubAgentRunner()

    overwrite_result, overwrite_status = runner._run_permissioned_tool(
        "create_file",
        {"filename": "existing.txt", "content": "replacement", "overwrite": True},
        "propose_only",
        "general",
    )
    delete_result, delete_status = runner._run_permissioned_tool(
        "delete_file",
        {"filename": "existing.txt"},
        "propose_only",
        "general",
    )

    assert overwrite_status == "blocked"
    assert json.loads(overwrite_result)["status"] == "blocked"
    assert delete_status == "blocked"
    assert json.loads(delete_result)["status"] == "blocked"


def test_native_tool_schemas_are_filtered_by_permission_and_role(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        tools,
        "get_tool_specs",
        lambda: [
            {"function": {"name": name}}
            for name in (
                "read_file",
                "create_file",
                "delete_file",
                "search_web",
                "get_env",
            )
        ],
    )
    role = sub_agent_tool.AgentSpec(
        name="test", description="", system_prompt="", allowed_tools=["read_file"]
    )

    read_only = runner._native_tool_specs(role, "read_only")
    propose_only = runner._native_tool_specs(role, "propose_only")
    unrestricted_role = sub_agent_tool.AgentSpec(
        name="test", description="", system_prompt=""
    )
    proposal_specs = runner._native_tool_specs(unrestricted_role, "propose_only")

    assert [spec["function"]["name"] for spec in read_only] == ["read_file"]
    assert [spec["function"]["name"] for spec in propose_only] == ["read_file"]
    assert {spec["function"]["name"] for spec in proposal_specs} == {
        "read_file",
        "create_file",
    }


def test_invalid_permission_level_fails_closed():
    runner = sub_agent_tool.SubAgentRunner()

    assert runner._normalize_permission_level("anything") == "none"
    assert (
        runner._tool_permission_decision(
            "read_file", {"filename": "notes.txt"}, "anything"
        )[0]
        == "deny"
    )


def test_native_tool_calls_cannot_bypass_read_only_gate(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    dispatched = []
    monkeypatch.setattr(
        tools,
        "run_tool",
        lambda name, args: dispatched.append((name, args)) or "unexpected execution",
    )
    calls = iter(
        [
            (
                "",
                [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "delete_file",
                            "arguments": json.dumps({"filename": "important.txt"}),
                        },
                    }
                ],
                {},
            ),
            ("finished", [], {}),
        ]
    )

    tool_specs_seen = []

    def fake_native_call(*args, **kwargs):
        tool_specs = args[4]
        tool_specs_seen.append(tool_specs)
        assert "delete_file" not in {item["function"]["name"] for item in tool_specs}
        if len(tool_specs_seen) == 2:
            assert tool_specs == []
        return next(calls)

    monkeypatch.setattr(runner, "_call_openai_with_tools", fake_native_call)
    result = runner._run_llm_multi_turn(
        cb=None,
        provider="openai",
        client=object(),
        model_name="test-model",
        system_prompt="system",
        user_prompt="task",
        timeout=1,
        max_retries=0,
        response_mode="text",
        permission_level="read_only",
        max_turns=2,
        agent_spec=sub_agent_tool.AgentSpec(
            name="test", description="", system_prompt=""
        ),
        agent_name="test",
    )

    assert result[0] == "finished"
    assert result[3][0]["status"] == "blocked"
    assert dispatched == []


def test_final_native_tool_request_is_blocked_without_execution(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        tools,
        "get_tool_specs",
        lambda: [{"function": {"name": "read_file"}}],
    )
    calls = iter(
        [
            (
                "",
                [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"filename": "notes.txt"}),
                        },
                    }
                ],
                {},
            ),
            (
                "",
                [
                    {
                        "id": "call-2",
                        "function": {
                            "name": "file_exists",
                            "arguments": json.dumps({"path": "final.txt"}),
                        },
                    }
                ],
                {},
            ),
        ]
    )
    tool_specs_seen = []

    def fake_native_call(*args, **kwargs):
        tool_specs_seen.append(args[4])
        return next(calls)

    executed = []
    monkeypatch.setattr(runner, "_call_openai_with_tools", fake_native_call)
    monkeypatch.setattr(
        runner,
        "_run_permissioned_tool",
        lambda name, args, *_rest: executed.append((name, args))
        or ("read result", "success"),
    )

    result = runner._run_llm_multi_turn(
        cb=None,
        provider="openai",
        client=object(),
        model_name="test-model",
        system_prompt="system",
        user_prompt="task",
        timeout=1,
        max_retries=0,
        response_mode="text",
        permission_level="read_only",
        max_turns=2,
        agent_spec=sub_agent_tool.AgentSpec(
            name="test", description="", system_prompt=""
        ),
        agent_name="test",
    )

    assert tool_specs_seen[0] == [{"function": {"name": "read_file"}}]
    assert tool_specs_seen[1] == []
    assert executed == [("read_file", {"filename": "notes.txt"})]
    assert "tool-turn budget exhausted" in result[0]
    assert result[3][-1]["status"] == "budget_exhausted"


def test_final_compatibility_tool_request_is_blocked_without_execution(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    responses = iter(
        [
            ('read_file(filename="notes.txt")', 0, {}),
            ('read_file(filename="final.txt")', 0, {}),
        ]
    )
    monkeypatch.setattr(
        runner, "_call_with_retry", lambda *args, **kwargs: next(responses)
    )
    executed = []
    monkeypatch.setattr(
        runner,
        "_run_permissioned_tool",
        lambda name, args, *_rest: executed.append((name, args))
        or ("read result", "success"),
    )

    result = runner._run_llm_multi_turn(
        cb=None,
        provider="gemini",
        client=object(),
        model_name="test-model",
        system_prompt="system",
        user_prompt="task",
        timeout=1,
        max_retries=0,
        response_mode="text",
        permission_level="read_only",
        max_turns=2,
        agent_spec=sub_agent_tool.AgentSpec(
            name="test",
            description="",
            system_prompt="",
            allowed_tools=["read_file"],
        ),
        agent_name="test",
    )

    assert executed == [("read_file", {"filename": "notes.txt"})]
    assert result[3][-1]["tool"] == "read_file"
    assert result[3][-1]["status"] == "budget_exhausted"


def test_final_responses_turn_does_not_inject_hosted_web_search(monkeypatch):
    from types import SimpleNamespace

    from uagent.providers import responses_common

    monkeypatch.setenv("UAGENT_OPENAI_WEB_SEARCH", "1")
    request = {}

    def create(**kwargs):
        request.update(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1, completion_tokens=1, total_tokens=2)
        )

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(
        responses_common,
        "parse_responses_response",
        lambda _response: ("final answer", "", [], None, []),
    )

    result = sub_agent_tool.SubAgentRunner()._call_responses_with_tools(
        client,
        model_name="gpt-6-luna",
        system_prompt="final only",
        messages=[{"role": "user", "content": "finish"}],
        tool_specs=[],
        timeout=10,
        provider="openai",
    )

    assert result[0] == "final answer"
    assert request["tools"] == []


def test_final_chat_completion_turn_omits_empty_tool_fields():
    from types import SimpleNamespace

    request = {}
    message = SimpleNamespace(content="final answer", tool_calls=None)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )

    def create(**kwargs):
        request.update(kwargs)
        return response

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create),
        )
    )
    result = sub_agent_tool.SubAgentRunner()._call_openai_with_tools(
        client,
        model_name="sarashina-chat",
        system_prompt="final only",
        messages=[{"role": "user", "content": "finish"}],
        tool_specs=[],
        timeout=10,
        provider="sarashina",
    )

    assert result[0] == "final answer"
    assert "tools" not in request
    assert "tool_choice" not in request
