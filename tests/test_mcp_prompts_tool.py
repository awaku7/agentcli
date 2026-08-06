from __future__ import annotations

import json


def test_mcp_prompts_validates_action_and_name() -> None:
    from uagent.tools.mcp_prompts_tool import run_tool

    assert "action" in run_tool({"action": "invalid"})
    assert "name" in run_tool({"action": "get"})
    assert "arguments" in run_tool({"action": "get", "name": "summarize", "arguments": "bad"})


def test_mcp_prompts_gets_with_shared_client(monkeypatch) -> None:
    import uagent.tools.mcp_prompts_tool as tool

    captured: dict[str, object] = {}

    async def fake_request(connection, action, name, arguments):
        captured.update(
            connection=connection,
            action=action,
            name=name,
            arguments=arguments,
        )
        return {"messages": [{"role": "user", "content": "hello"}]}

    monkeypatch.setattr(tool, "_request", fake_request)
    output = tool.run_tool(
        {
            "url": "https://example.test/mcp",
            "action": "get",
            "name": "summarize",
            "arguments": {"style": "short"},
            "protocol_mode": "stateless",
        }
    )

    assert json.loads(output)["messages"][0]["content"] == "hello"
    assert captured["action"] == "get"
    assert captured["name"] == "summarize"
    assert captured["arguments"] == {"style": "short"}
    assert captured["connection"]["protocol_mode"] == "stateless"
