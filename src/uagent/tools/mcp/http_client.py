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


async def _inject_trusted_trace_context(request: Any) -> None:
    """Inject only UAG-owned W3C trace context into one MCP HTTP request."""
    try:
        for key in ("traceparent", "tracestate"):
            if key in request.headers:
                del request.headers[key]

        from ...runtime.observability.bootstrap import get_observability_backend

        carrier: dict[str, str] = {}
        get_observability_backend().inject_context(carrier)
        for key in ("traceparent", "tracestate"):
            value = carrier.get(key)
            if value:
                request.headers[key] = value
    except Exception:
        # Propagation is best-effort and must never fail MCP/OAuth traffic.
        return


def create_mcp_http_client(
    config: MCPHTTPConfig | None = None,
    *,
    headers: dict[str, str] | None = None,
    auth: Any = None,
    trusted_trace_propagation: bool = False,
) -> httpx.AsyncClient:
    """Create an AsyncClient for MCP or OAuth traffic.

    ``trusted_trace_propagation`` is deliberately separate from ``MCPHTTPConfig``
    so proxy/TLS settings reused by OAuth clients cannot accidentally enable MCP
    trace propagation. Callers must opt in at the UAG-owned MCP transport boundary.
    """
    selected = config or MCPHTTPConfig()
    selected.validate()
    verify: bool | str = selected.ca_cert or selected.verify
    client_kwargs: dict[str, Any] = {
        "headers": headers,
        "auth": auth,
        "proxy": selected.proxy_url,
        "verify": verify,
        "trust_env": selected.trust_env,
        "timeout": selected.timeout,
    }
    if trusted_trace_propagation:
        client_kwargs["event_hooks"] = {"request": [_inject_trusted_trace_context]}
    return httpx.AsyncClient(**client_kwargs)


__all__ = ["MCPHTTPConfig", "create_mcp_http_client"]
