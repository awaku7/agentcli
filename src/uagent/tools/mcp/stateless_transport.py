"""Minimal stateless MCP Streamable HTTP transport.

This adapter is intentionally limited to JSON-RPC request/response calls. It
exists for MCP 2026-07-28 endpoints when the installed SDK does not provide
stateless header routing. It has no localization and no hidden session state.
"""

from __future__ import annotations

import itertools
from typing import Any

from .errors import MCPProtocolError, MCPTransportError
from .stateless_http import build_protocol_headers


class StatelessHTTPClient:
    """Small JSON-RPC client for stateless MCP HTTP endpoints."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        protocol_version: str = "2026-07-28",
        http_client: Any = None,
    ) -> None:
        self.url = url if url.endswith("/mcp") else url.rstrip("/") + "/mcp"
        self.headers = headers or {}
        self.protocol_version = protocol_version
        self.http_client = http_client
        self._owns_client = http_client is None
        self._ids = itertools.count(1)

    async def __aenter__(self) -> "StatelessHTTPClient":
        if self.http_client is None:
            import httpx

            self.http_client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._owns_client and self.http_client is not None:
            await self.http_client.aclose()

    async def request(
        self,
        method: str,
        name: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = next(self._ids)
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            body["params"] = params

        request_headers = dict(self.headers)
        request_headers.update(
            build_protocol_headers(
                method=method,
                name=name,
                protocol_version=self.protocol_version,
            )
        )
        request_headers.setdefault("Accept", "application/json")
        request_headers.setdefault("Content-Type", "application/json")

        try:
            response = await self.http_client.post(
                self.url, json=body, headers=request_headers
            )
        except Exception as exc:
            raise MCPTransportError(
                "MCP_HTTP_REQUEST_FAILED", method, {"error": str(exc)}
            ) from exc

        if response.status_code >= 400:
            raise MCPTransportError(
                "MCP_HTTP_STATUS_ERROR",
                method,
                {"status_code": response.status_code},
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise MCPProtocolError(
                "MCP_INVALID_JSON_RESPONSE", method, {"error": str(exc)}
            ) from exc
        if not isinstance(payload, dict):
            raise MCPProtocolError(
                "MCP_INVALID_RESPONSE_OBJECT", method, {"type": type(payload).__name__}
            )
        if payload.get("error") is not None:
            raise MCPProtocolError(
                "MCP_JSONRPC_ERROR", method, {"error": payload["error"]}
            )
        return payload

    async def discover(self) -> dict[str, Any]:
        return await self.request(
            "server/discover",
            params={
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": self.protocol_version,
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "uag",
                        "version": "1.0",
                    },
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        )

    async def list_tools(self) -> dict[str, Any]:
        return await self.request("tools/list")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.request(
            "tools/call", name=name, params={"name": name, "arguments": arguments}
        )

    async def list_resources(self) -> dict[str, Any]:
        return await self.request("resources/list")

    async def read_resource(self, uri: str) -> dict[str, Any]:
        return await self.request("resources/read", params={"uri": uri})

    async def list_prompts(self) -> dict[str, Any]:
        return await self.request("prompts/list")

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments
        return await self.request("prompts/get", name=name, params=params)
