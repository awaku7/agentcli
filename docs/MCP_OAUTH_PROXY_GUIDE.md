# MCP OAuth / Proxy User Guide

This guide explains how to use remote MCP servers (Streamable HTTP) with OAuth and corporate proxies.

## Protocol mode

When configuring an MCP client, use `stateless` only with a stateless server.
For a session-required Streamable HTTP server, use `auto` (recommended) or
`legacy`; `stateless` may be rejected with HTTP 400. If omitted, the mode
defaults to `auto` and can fall back to the legacy SDK transport.

## Scope

OAuth is intended for remote HTTP MCP servers. stdio MCP servers normally use OS permissions, environment variables, or server-specific API keys instead.

Supported flow:

```text
MCP metadata → authorization server metadata → CIMD/client_id validation
→ browser authorization → localhost callback → PKCE code exchange
→ encrypted Token Store → Bearer requests and refresh on 401
```

## Token Store

By default, tokens are stored per user, not in the pip installation directory.

Windows:

```text
C:\Users\<user>\.uag\mcps\oauth_tokens.json
```

Linux/macOS:

```text
~/.uag/mcps/oauth_tokens.json
```

Change the base directory with `UAGENT_STATE_DIR`:

```powershell
$env:UAGENT_STATE_DIR = "D:\uag-state"
```

```bash
export UAGENT_STATE_DIR="$HOME/.config/uagent"
```

Records are separated by the `issuer` and `resource` pair. The file contains encrypted token payloads and must not be committed to Git or placed on a shared drive.

## Proxy configuration

Using environment variables:

```powershell
$env:HTTPS_PROXY = "http://proxy.example:8080"
$env:HTTP_PROXY = "http://proxy.example:8080"
$env:NO_PROXY = "127.0.0.1,localhost"
```

```bash
export HTTPS_PROXY="http://proxy.example:8080"
export HTTP_PROXY="http://proxy.example:8080"
export NO_PROXY="127.0.0.1,localhost"
```

`NO_PROXY` must include `127.0.0.1` and `localhost` so that the OAuth callback is not sent through the proxy.

Explicit configuration:

```python
from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.http_client import MCPHTTPConfig

client = MCPClient(
    url="https://mcp.example.com/mcp",
    http_config=MCPHTTPConfig(
        proxy_url="http://proxy.example:8080",
        trust_env=True,
        timeout=30,
    ),
)
```

For SOCKS proxies, install the optional dependency:

```bash
pip install "httpx[socks]"
```

## Corporate CA certificates

For TLS inspection by a corporate proxy, configure the corporate CA:

```python
MCPHTTPConfig(
    proxy_url="http://proxy.example:8080",
    ca_cert="C:/certs/company-ca.pem",
    trust_env=False,
)
```

You can also use `SSL_CERT_FILE`. Do not disable TLS verification with `verify=False` in production; OAuth tokens and refresh tokens are sensitive credentials.

## Reverse proxy deployments

Metadata must use the canonical URL visible to the client, not an internal hostname.

```text
Correct: https://mcp.example.com/mcp
Incorrect: http://mcp-internal:8000/mcp
```

Do not expose internal hostnames or addresses in `resource`, `issuer`, authorization/token endpoints, or the CIMD `client_id`. Configure `X-Forwarded-Proto` and `X-Forwarded-Host` consistently at the reverse proxy.

## Common errors

- **issuer mismatch**: the configured issuer and discovered issuer differ; check the canonical URL and forwarded scheme/host.
- **CIMD client_id mismatch**: the document's `client_id` does not match its URL.
- **TLS certificate verify failed**: configure the corporate CA with `ca_cert` or `SSL_CERT_FILE`.
- **OAuth callback timeout**: check browser access to localhost and `NO_PROXY`.
- **MCP_OAUTH_REFRESH_TOKEN_MISSING**: re-authorize the MCP server.
- **conflicting auth configuration**: an injected `httpx.AsyncClient` already has a different auth handler; do not overwrite it implicitly.

## Security notes

- Never log access tokens, refresh tokens, or proxy passwords.
- Do not commit the token store.
- Do not expose the OAuth callback outside localhost.
- Do not use public OAuth/MCP endpoints as fixed CI dependencies.
- Verify real corporate proxy, CA, and authorization-server behavior in a controlled environment.

## Local integration tests

The repository includes local MCP/OAuth/proxy fixtures that do not contact external services:

```bash
python -m pytest -q tests/integration/test_mcp_oauth_proxy_integration.py
python -m pytest -q tests/integration/test_mcp_oauth_security_integration.py
```

These tests do not replace validation against a real corporate proxy or authorization server.
