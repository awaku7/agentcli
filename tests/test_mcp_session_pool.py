from uagent.tools.mcp import session_pool


class _FakeMCPClient:
    created = 0
    entered = 0
    listed = 0
    calls = 0

    def __init__(self, **kwargs):
        type(self).created += 1

    async def __aenter__(self):
        type(self).entered += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def list_tools(self):
        type(self).listed += 1
        return {
            "tools": [
                {"name": "echo", "inputSchema": {"type": "object", "properties": {}}}
            ]
        }

    async def call_tool(self, name, arguments):
        type(self).calls += 1
        return {"name": name, "arguments": arguments}


def test_http_session_pool_reuses_connection_and_tools(monkeypatch):
    monkeypatch.setattr(session_pool, "MCPClient", _FakeMCPClient)
    pool = session_pool.MCPHTTPSessionPool()
    try:
        headers = {"Authorization": "Bearer test"}
        first_tools = pool.list_tools(
            url="http://example.test/mcp",
            headers=headers,
            protocol_mode="auto",
        )
        first_tools_again = pool.list_tools(
            url="http://example.test/mcp",
            headers=headers,
            protocol_mode="auto",
        )
        pool.call_tool(
            url="http://example.test/mcp",
            name="echo",
            arguments={},
            headers=headers,
            protocol_mode="auto",
        )
        pool.call_tool(
            url="http://example.test/mcp",
            name="echo",
            arguments={"again": True},
            headers=headers,
            protocol_mode="auto",
        )

        assert first_tools == first_tools_again
        assert _FakeMCPClient.created == 1
        assert _FakeMCPClient.entered == 1
        assert _FakeMCPClient.listed == 1
        assert _FakeMCPClient.calls == 2
    finally:
        pool.close()
