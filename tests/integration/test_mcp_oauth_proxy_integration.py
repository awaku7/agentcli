from __future__ import annotations

import asyncio
import json
import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from uagent.tools.mcp.http_client import MCPHTTPConfig, create_mcp_http_client
from uagent.tools.mcp.oauth_provider import OAuthTokenProvider
from uagent.tools.mcp.stateless_transport import StatelessHTTPClient
from uagent.tools.mcp.token_store import StoredToken, TokenStore


class _TargetHandler(BaseHTTPRequestHandler):
    refresh_calls = 0
    mcp_auth_headers: list[str] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/oauth/token":
            type(self).refresh_calls += 1
            payload = {"access_token": "new", "token_type": "Bearer", "expires_in": 60}
        elif self.path == "/mcp":
            type(self).mcp_auth_headers.append(self.headers.get("Authorization", ""))
            payload = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        else:
            self.send_error(404)
            return
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args: object) -> None:
        return


class _ProxyHandler(BaseHTTPRequestHandler):
    requests = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).requests += 1
        target = urlsplit(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        connection = HTTPConnection(target.hostname, target.port)
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "proxy-connection"}
        }
        connection.request("POST", target.path or "/", body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in {"connection", "transfer-encoding"}:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)
        connection.close()

    def log_message(self, *_args: object) -> None:
        return


def _server(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_mcp_oauth_refresh_and_request_through_local_proxy(tmp_path) -> None:
    async def scenario() -> None:
        target, _ = _server(_TargetHandler)
        proxy, _ = _server(_ProxyHandler)
        try:
            target_url = f"http://127.0.0.1:{target.server_port}"
            config = MCPHTTPConfig(
                proxy_url=f"http://127.0.0.1:{proxy.server_port}",
                trust_env=False,
                timeout=5,
            )
            store = TokenStore(
                tmp_path / "tokens.json",
                encrypt=lambda value: value[::-1],
                decrypt=lambda value: value[::-1],
            )
            store.save(
                "http://127.0.0.1:auth",
                f"{target_url}/mcp",
                StoredToken("old", "Bearer", refresh_token="refresh"),
            )
            async with create_mcp_http_client(config) as oauth_client:
                provider = OAuthTokenProvider(
                    issuer="http://127.0.0.1:auth",
                    resource=f"{target_url}/mcp",
                    client_id="local-test",
                    token_endpoint=f"{target_url}/oauth/token",
                    token_store=store,
                    http_client=oauth_client,
                )
                assert await provider.authorization_header(True) == "Bearer new"
                async with StatelessHTTPClient(
                    f"{target_url}/mcp",
                    http_config=config,
                    authorization_provider=provider.authorization_header,
                ) as mcp:
                    await mcp.list_tools()
            assert _TargetHandler.refresh_calls == 1
            assert _TargetHandler.mcp_auth_headers == ["Bearer new"]
            assert _ProxyHandler.requests == 2
        finally:
            target.shutdown()
            proxy.shutdown()

    asyncio.run(scenario())
