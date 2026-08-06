from __future__ import annotations

import json


def test_mcp_resources_validates_action_and_uri() -> None:
    from uagent.tools.mcp_resources_tool import run_tool

    assert "action" in run_tool({"action": "invalid"})
    assert "uri" in run_tool({"action": "read"})


def test_mcp_resources_reads_with_shared_client(monkeypatch) -> None:
    import uagent.tools.mcp_resources_tool as tool

    captured: dict[str, object] = {}

    async def fake_request(connection, action, uri):
        captured.update(connection=connection, action=action, uri=uri)
        return {"contents": [{"uri": uri, "text": "hello"}]}

    monkeypatch.setattr(tool, "_request", fake_request)
    output = tool.run_tool(
        {
            "url": "https://example.test/mcp",
            "action": "read",
            "uri": "file:///README.md",
            "protocol_mode": "stateless",
        }
    )

    assert json.loads(output)["contents"][0]["text"] == "hello"
    assert captured["action"] == "read"
    assert captured["uri"] == "file:///README.md"
    assert captured["connection"]["protocol_mode"] == "stateless"
