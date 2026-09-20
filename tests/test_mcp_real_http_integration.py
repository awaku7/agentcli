from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.session_pool import MCPHTTPSessionPool


class _MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        method = request["method"]
        server = self.server
        assert isinstance(server, _MCPTestServer)
        server.requests.append(
            {
                "method": method,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "params": request.get("params"),
            }
        )

        if method == "server/discover":
            result: dict[str, Any] = {"supportedVersions": ["2026-07-28"]}
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                        },
                    }
                ]
            }
        elif method == "tools/call":
            arguments = (request.get("params") or {}).get("arguments", {})
            result = {
                "content": [{"type": "text", "text": str(arguments.get("text", ""))}]
            }
        else:
            self.send_error(404, "unknown MCP method")
            return

        payload = json.dumps(
            {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()

    def log_message(self, format: str, *args: Any) -> None:
        return None


class _MCPTestServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _MCPHandler)
        self.requests: list[dict[str, Any]] = []

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/mcp"


def _run_server() -> tuple[_MCPTestServer, threading.Thread]:
    server = _MCPTestServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_server(server: _MCPTestServer, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_mcp_client_auto_flow_uses_real_http_server() -> None:
    server, thread = _run_server()

    async def scenario() -> None:
        async with MCPClient(url=server.endpoint, protocol_mode="auto") as client:
            assert client.protocol_info is not None
            assert client.protocol_info.mode.value == "stateless"
            assert client.protocol_info.detection_reason == "stateless_probe"

            tools = await client.list_tools()
            result = await client.call_tool("echo", {"text": "hello"})

        assert tools["result"]["tools"][0]["name"] == "echo"
        assert result["result"]["content"][0]["text"] == "hello"

    try:
        asyncio.run(scenario())
        assert [request["method"] for request in server.requests] == [
            "server/discover",
            "tools/list",
            "tools/call",
        ]
        assert all(
            "application/json" in request["headers"]["accept"]
            and "text/event-stream" in request["headers"]["accept"]
            for request in server.requests
        )
    finally:
        _stop_server(server, thread)


def test_mcp_session_pool_reuses_real_http_session() -> None:
    server, thread = _run_server()
    pool = MCPHTTPSessionPool()

    try:
        tools = pool.list_tools(
            url=server.endpoint,
            headers={},
            protocol_mode="auto",
        )
        _, first = pool.call_tool(
            url=server.endpoint,
            name="echo",
            arguments={"text": "first"},
            headers={},
            protocol_mode="auto",
        )
        _, second = pool.call_tool(
            url=server.endpoint,
            name="echo",
            arguments={"text": "second"},
            headers={},
            protocol_mode="auto",
        )

        assert tools["result"]["tools"][0]["name"] == "echo"
        assert first["result"]["content"][0]["text"] == "first"
        assert second["result"]["content"][0]["text"] == "second"
        assert [request["method"] for request in server.requests] == [
            "server/discover",
            "tools/list",
            "tools/call",
            "tools/call",
        ]
    finally:
        pool.close()
        _stop_server(server, thread)
