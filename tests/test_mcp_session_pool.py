import asyncio
import time

import pytest

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


class _SlowMCPClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def list_tools(self):
        return {"tools": []}

    async def call_tool(self, name, arguments):
        await asyncio.sleep(2)
        return {"name": name, "arguments": arguments}


def test_http_session_pool_cancels_inflight_call(monkeypatch):
    monkeypatch.setattr(session_pool, "MCPClient", _SlowMCPClient)
    pool = session_pool.MCPHTTPSessionPool()
    started = time.monotonic()
    try:
        pool.list_tools(
            url="http://slow.example.test/mcp",
            headers={},
            protocol_mode="auto",
        )
        with pytest.raises(session_pool.MCPSessionCancelled):
            pool.call_tool(
                url="http://slow.example.test/mcp",
                name="slow",
                arguments={},
                headers={},
                protocol_mode="auto",
                is_cancelled=lambda: time.monotonic() - started > 0.1,
            )
        assert time.monotonic() - started < 1.5
    finally:
        pool.close()


def test_http_session_pool_rejects_stale_generation(monkeypatch):
    monkeypatch.setattr(session_pool, "MCPClient", _SlowMCPClient)
    pool = session_pool.MCPHTTPSessionPool()
    generation_calls = 0

    def generation():
        nonlocal generation_calls
        generation_calls += 1
        return 0 if generation_calls < 3 else 1

    try:
        pool.list_tools(
            url="http://stale.example.test/mcp",
            headers={},
            protocol_mode="auto",
        )
        with pytest.raises(session_pool.MCPSessionStale):
            pool.call_tool(
                url="http://stale.example.test/mcp",
                name="slow",
                arguments={},
                headers={},
                protocol_mode="auto",
                request_generation=generation,
            )
    finally:
        pool.close()
