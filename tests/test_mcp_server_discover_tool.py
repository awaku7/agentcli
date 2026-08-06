from __future__ import annotations

import json


def test_mcp_server_discover_uses_stateless_by_default(monkeypatch) -> None:
    import uagent.tools.mcp_server_discover_tool as tool

    captured: dict[str, object] = {}

    async def fake_request(connection):
        captured.update(connection)
        return {"result": {"supportedVersions": ["2026-07-28"]}}

    monkeypatch.setattr(tool, "_request", fake_request)
    output = tool.run_tool({"url": "https://example.test/mcp"})

    assert json.loads(output)["result"]["supportedVersions"] == ["2026-07-28"]
    assert captured["protocol_mode"] == "stateless"


def test_mcp_server_discover_requires_endpoint() -> None:
    from uagent.tools.mcp_server_discover_tool import run_tool

    assert "MCP" in run_tool({})
