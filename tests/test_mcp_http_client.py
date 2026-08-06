from __future__ import annotations

from pathlib import Path

import pytest

from uagent.tools.mcp.http_client import MCPHTTPConfig, create_mcp_http_client
from uagent.tools.mcp.stateless_transport import StatelessHTTPClient


def test_http_config_rejects_invalid_proxy() -> None:
    with pytest.raises(ValueError):
        MCPHTTPConfig(proxy_url="ftp://proxy.example:8080").validate()


def test_http_config_rejects_missing_ca(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        MCPHTTPConfig(ca_cert=tmp_path / "missing.pem").validate()


def test_create_http_client_applies_explicit_settings() -> None:
    client = create_mcp_http_client(
        MCPHTTPConfig(
            proxy_url="http://proxy.example:8080",
            trust_env=False,
            timeout=12,
        )
    )
    try:
        assert client.timeout.read == 12
        assert client._trust_env is False
    finally:
        import asyncio

        asyncio.run(client.aclose())


def test_stateless_transport_retains_http_config() -> None:
    config = MCPHTTPConfig(proxy_url="http://proxy.example:8080")
    transport = StatelessHTTPClient("https://mcp.example/mcp", http_config=config)
    assert transport.http_config is config
