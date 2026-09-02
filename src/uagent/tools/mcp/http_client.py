"""Shared Proxy/TLS configuration for MCP and OAuth HTTP clients."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ...lazy_import import lazy_module

httpx = lazy_module("httpx")


@dataclass(frozen=True)
class MCPHTTPConfig:
    """Explicit HTTP settings shared by MCP and OAuth requests."""

    proxy_url: str | None = None
    ca_cert: str | Path | None = None
    verify: bool = True
    trust_env: bool = True
    timeout: float = 30.0

    def validate(self) -> None:
        if self.proxy_url:
            parsed = urlparse(self.proxy_url)
            if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
                raise ValueError("proxy_url must use http, https, socks5, or socks5h")
            if not parsed.netloc:
                raise ValueError("proxy_url must be an absolute URL")
        if self.ca_cert is not None and not Path(self.ca_cert).is_file():
            raise FileNotFoundError(f"CA certificate not found: {self.ca_cert}")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")


def create_mcp_http_client(
    config: MCPHTTPConfig | None = None,
    *,
    headers: dict[str, str] | None = None,
    auth: Any = None,
) -> httpx.AsyncClient:
    """Create an AsyncClient for MCP or OAuth traffic."""
    selected = config or MCPHTTPConfig()
    selected.validate()
    verify: bool | str = selected.ca_cert or selected.verify
    return httpx.AsyncClient(
        headers=headers,
        auth=auth,
        proxy=selected.proxy_url,
        verify=verify,
        trust_env=selected.trust_env,
        timeout=selected.timeout,
    )


__all__ = ["MCPHTTPConfig", "create_mcp_http_client"]
