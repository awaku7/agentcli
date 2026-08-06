"""Shared MCP client wrapper.

This module deliberately has no localization. Public tools translate the
structured errors and protocol information returned here.
"""

from __future__ import annotations

import os
from contextlib import AsyncExitStack
from typing import Any

from .errors import (
    MCPProtocolError,
    MCPTransportError,
    MCPUnsupportedError,
)
from .protocol import (
    MCPProtocolInfo,
    detect_protocol_mode,
    select_protocol_version,
)
from .stateless_transport import StatelessHTTPClient

try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.client.streamable_http import streamable_http_client
except ImportError:  # pragma: no cover - exercised only in minimal installs
    from .._pip_auto import install_with_status

    if not install_with_status("mcp"):
        raise
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.client.streamable_http import streamable_http_client


def _is_legacy_probe_rejection(exc: Exception) -> bool:
    """Return whether an auto probe was rejected as a legacy endpoint."""
    if isinstance(exc, MCPTransportError):
        if exc.code != "MCP_HTTP_STATUS_ERROR":
            return False
        status = exc.details.get("status_code")
        return status in {400, 404, 405}
    if isinstance(exc, MCPProtocolError):
        if exc.code != "MCP_JSONRPC_ERROR":
            return False
        error = exc.details.get("error")
        if not isinstance(error, dict):
            return False
        return error.get("code") == -32601
    return False


class MCPClient:
    """Shared client for the currently supported MCP transports."""

    def __init__(
        self,
        *,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        protocol_mode: str = "auto",
        http_client: Any = None,
    ) -> None:
        self.url = url
        self.headers = headers or {}
        self.command = command or ""
        self.args = args or []
        self.env = env or {}
        self.requested_mode = protocol_mode
        self.session: Any = None
        self.initialize_result: Any = None
        self.protocol_info: MCPProtocolInfo | None = None
        self._stack = AsyncExitStack()
        self._http_client: Any = http_client
        self._owns_http_client = http_client is None
        self._stateless_client: StatelessHTTPClient | None = None

    async def __aenter__(self) -> "MCPClient":
        try:
            if self.requested_mode == "auto" and self.url and not self.command:
                # Probe read-only tools/list first. Legacy servers commonly
                # reject this pre-initialize request, in which case the SDK
                # initialize path below remains the compatibility fallback.
                probe = StatelessHTTPClient(
                    self.url,
                    headers=self.headers,
                    http_client=self._http_client,
                )
                try:
                    await probe.__aenter__()
                    discovery = await probe.discover()
                    result = (
                        discovery.get("result", {})
                        if isinstance(discovery, dict)
                        else {}
                    )
                    supported = result.get("supportedVersions", [])
                    probe.protocol_version = select_protocol_version(supported)
                except Exception as exc:
                    await probe.__aexit__(None, None, None)
                    if not _is_legacy_probe_rejection(exc):
                        raise
                else:
                    self._stateless_client = probe
                    self.url = probe.url
                    self.protocol_info = detect_protocol_mode(
                        requested_mode="auto",
                        protocol_version=probe.protocol_version,
                        stateless_probe_succeeded=True,
                    )
                    return self

            if self.requested_mode == "stateless":
                if not self.url or self.command:
                    raise MCPUnsupportedError(
                        "MCP_STATELESS_HTTP_REQUIRED",
                        "connect",
                        {"transport": "stdio" if self.command else "unknown"},
                    )
                self._stateless_client = StatelessHTTPClient(
                    self.url,
                    headers=self.headers,
                    http_client=self._http_client,
                )
                await self._stateless_client.__aenter__()
                self.url = self._stateless_client.url
                self.protocol_info = detect_protocol_mode(
                    requested_mode="stateless",
                    protocol_version=self._stateless_client.protocol_version,
                )
                return self

            if self.command and not self.url:
                params = StdioServerParameters(
                    command=self.command,
                    args=self.args,
                    env={**os.environ, **self.env},
                )
                read, write = await self._stack.enter_async_context(
                    stdio_client(params)
                )
            elif self.url:
                endpoint = (
                    self.url
                    if self.url.endswith("/mcp")
                    else self.url.rstrip("/") + "/mcp"
                )
                if self.headers and self._http_client is None:
                    import httpx

                    self._http_client = httpx.AsyncClient(headers=self.headers)
                    self._owns_http_client = True
                read, write, get_session_id = await self._stack.enter_async_context(
                    streamable_http_client(endpoint, http_client=self._http_client)
                )
                self.url = endpoint
                self._session_id = get_session_id()
            else:
                raise MCPTransportError(
                    "MCP_ENDPOINT_MISSING", "connect", {"transport": "unknown"}
                )

            self.session = await self._stack.enter_async_context(
                ClientSession(read, write)
            )
            if self.requested_mode == "stateless":
                raise MCPUnsupportedError(
                    "MCP_STATELESS_SDK_UNSUPPORTED",
                    "connect",
                    {"requested_mode": "stateless"},
                )
            self.initialize_result = await self.session.initialize()
            self.protocol_info = detect_protocol_mode(
                requested_mode=self.requested_mode,
                protocol_version=self._protocol_version(),
                session_id=getattr(self, "_session_id", None),
                initialize_required=True,
            )
            return self
        except MCPTransportError:
            await self._stack.aclose()
            raise
        except MCPUnsupportedError:
            await self._stack.aclose()
            raise
        except Exception as exc:
            await self._stack.aclose()
            raise MCPTransportError(
                "MCP_CONNECT_FAILED", "connect", {"error": str(exc)}
            ) from exc

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._stateless_client is not None:
            await self._stateless_client.__aexit__(exc_type, exc, tb)
            self._stateless_client = None
        await self._stack.aclose()
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _protocol_version(self) -> str | None:
        result = self.initialize_result
        if isinstance(result, dict):
            value = result.get("protocolVersion") or result.get("protocol_version")
            return str(value) if value else None
        value = getattr(result, "protocolVersion", None) or getattr(
            result, "protocol_version", None
        )
        return str(value) if value else None

    async def list_tools(self) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.list_tools()
        if self.session is None:
            raise MCPTransportError("MCP_NOT_CONNECTED", "tools/list")
        try:
            return await self.session.list_tools()
        except Exception as exc:
            raise MCPTransportError(
                "MCP_LIST_TOOLS_FAILED", "tools/list", {"error": str(exc)}
            ) from exc

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.call_tool(name, arguments)
        if self.session is None:
            raise MCPTransportError("MCP_NOT_CONNECTED", "tools/call")
        try:
            return await self.session.call_tool(name, arguments)
        except Exception as exc:
            raise MCPTransportError(
                "MCP_CALL_TOOL_FAILED",
                "tools/call",
                {"tool_name": name, "error": str(exc)},
            ) from exc

    async def discover(self) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.discover()
        raise MCPUnsupportedError(
            "MCP_DISCOVER_UNSUPPORTED", "server/discover", {"mode": "legacy"}
        )

    async def list_resources(self) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.list_resources()
        if self.session is None:
            raise MCPTransportError("MCP_NOT_CONNECTED", "resources/list")
        try:
            return await self.session.list_resources()
        except Exception as exc:
            raise MCPTransportError(
                "MCP_LIST_RESOURCES_FAILED", "resources/list", {"error": str(exc)}
            ) from exc

    async def read_resource(self, uri: str) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.read_resource(uri)
        if self.session is None:
            raise MCPTransportError("MCP_NOT_CONNECTED", "resources/read")
        try:
            return await self.session.read_resource(uri)
        except Exception as exc:
            raise MCPTransportError(
                "MCP_READ_RESOURCE_FAILED", "resources/read", {"uri": uri, "error": str(exc)}
            ) from exc

    async def list_prompts(self) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.list_prompts()
        if self.session is None:
            raise MCPTransportError("MCP_NOT_CONNECTED", "prompts/list")
        try:
            return await self.session.list_prompts()
        except Exception as exc:
            raise MCPTransportError(
                "MCP_LIST_PROMPTS_FAILED", "prompts/list", {"error": str(exc)}
            ) from exc

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> Any:
        if self._stateless_client is not None:
            return await self._stateless_client.get_prompt(name, arguments)
        if self.session is None:
            raise MCPTransportError("MCP_NOT_CONNECTED", "prompts/get")
        try:
            return await self.session.get_prompt(name, arguments=arguments)
        except Exception as exc:
            raise MCPTransportError(
                "MCP_GET_PROMPT_FAILED", "prompts/get", {"name": name, "error": str(exc)}
            ) from exc
