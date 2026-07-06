"""ucp_mcp_server_tool

Start/stop a UCP MCP Server that exposes UCP capabilities as MCP tools.

The server wraps a UCP Business's REST API and exposes it through
the Model Context Protocol (MCP), allowing MCP clients to interact
with UCP-enabled merchants.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

BUSY_LABEL = True
STATUS_LABEL = "tool:ucp_mcp_server"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_mcp_server",
        "description": _(
            "tool.description",
            default=(
                "Start or stop a UCP MCP Server that wraps a UCP merchant's "
                "REST API as MCP tools. Use mode='start' to launch the server, "
                "mode='stop' to shut it down, mode='status' to check."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["start", "stop", "status"],
                    "description": _(
                        "param.mode.description",
                        default="'start' to launch, 'stop' to shut down, 'status' to check.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Business URL to proxy (required for mode='start').",
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": 8100,
                    "description": _(
                        "param.port.description",
                        default="Port for the MCP server (default 8100).",
                    ),
                },
                "transport": {
                    "type": "string",
                    "enum": ["stdio", "sse"],
                    "default": "sse",
                    "description": _(
                        "param.transport.description",
                        default="MCP transport: 'sse' (HTTP) or 'stdio' (stdin/stdout).",
                    ),
                },
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    },
}

_PROCESS: subprocess.Popen | None = None
_PROCESS_LOCK = threading.Lock()


def _get_server_script_path() -> str:
    """Return the path to the UCP MCP server script (~/.uag/mcps/ucp_mcp_server_main.py)."""
    return os.path.normpath(
        os.path.join(os.path.expanduser("~"), ".uag", "mcps", "ucp_mcp_server_main.py")
    )


def _ensure_mcp_server_script() -> str:
    """Create/update the MCP server script in ~/.uag/mcps/."""
    path = _get_server_script_path()
    # Always regenerate from template to stay in sync

    script = r'''"""UCP MCP Server — wraps UCP REST API as MCP tools.

Usage:
  python ucp_mcp_server_main.py --business-url https://example.shop --port 8100

Or via stdio (for MCP host integration):
  python ucp_mcp_server_main.py --business-url https://example.shop --transport stdio
"""
import argparse
import json
import sys
import os
import urllib.request
import urllib.error
from typing import Any

# Add parent to path for ucp_shared
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ucp_shared import discover_business, resolve_endpoint, resolve_mcp_endpoint, ucp_request


def _discover_and_get_profile(business_url: str) -> dict[str, Any]:
    """Discover business profile."""
    return discover_business(business_url)


def _build_mcp_tools(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Build MCP tool definitions from business capabilities."""
    caps = profile.get("ucp", {}).get("capabilities", {})
    tools = []

    cap_to_tool = {
        "dev.ucp.shopping.catalog_search": {
            "name": "ucp_catalog_search",
            "description": "Search product catalog",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "currency": {"type": "string", "description": "Currency code"},
                },
                "required": ["query"],
            },
        },
        "dev.ucp.shopping.catalog_lookup": {
            "name": "ucp_catalog_lookup",
            "description": "Lookup product details by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_ids": {"type": "array", "items": {"type": "string"}, "description": "Item IDs"},
                },
                "required": ["item_ids"],
            },
        },
        "dev.ucp.shopping.cart": {
            "name": "ucp_cart_create",
            "description": "Create a shopping cart",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "line_items": {"type": "array", "items": {"type": "object"}, "description": "Cart items"},
                    "currency": {"type": "string"},
                },
                "required": ["line_items"],
            },
        },
        "dev.ucp.shopping.checkout": {
            "name": "ucp_checkout_create",
            "description": "Create a checkout session",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cart_id": {"type": "string"},
                    "currency": {"type": "string"},
                },
                "required": ["cart_id"],
            },
        },
        "dev.ucp.shopping.order": {
            "name": "ucp_order_list",
            "description": "List orders",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    }

    for cap_name, tool_def in cap_to_tool.items():
        if cap_name in caps:
            tools.append(tool_def)

    # Add a generic tool
    tools.append({
        "name": "ucp_get_profile",
        "description": "Get the UCP business profile",
        "inputSchema": {"type": "object", "properties": {}},
    })

    return tools


# MCP protocol handlers
async def handle_mcp_request(request: dict[str, Any], business_url: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Handle an MCP request."""
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ucp-mcp-server", "version": "0.5.0"},
        }}

    if method == "tools/list":
        tools = _build_mcp_tools(profile)
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    if method == "tools/call":
        tool_name = request.get("params", {}).get("name", "")
        tool_args = request.get("params", {}).get("arguments", {})

        endpoint = resolve_endpoint(profile)

        try:
            if tool_name == "ucp_catalog_search":
                result = ucp_request(business_url, "search", body={"query": tool_args.get("query", "")}, profile=profile)
            elif tool_name == "ucp_catalog_lookup":
                result = ucp_request(business_url, "lookup-catalog", body={"item_ids": tool_args.get("item_ids", [])}, profile=profile)
            elif tool_name == "ucp_cart_create":
                result = ucp_request(business_url, "carts", method="POST", body={"line_items": tool_args.get("line_items", [])}, profile=profile)
            elif tool_name == "ucp_checkout_create":
                result = ucp_request(business_url, "checkout-sessions", method="POST", body={"cart_id": tool_args.get("cart_id", "")}, profile=profile)
            elif tool_name == "ucp_order_list":
                result = ucp_request(business_url, "list-orders", method="POST", profile=profile)
            elif tool_name == "ucp_get_profile":
                result = profile
            else:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}

            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def run_stdio(business_url: str):
    """Run MCP server over stdio."""
    import asyncio
    profile = _discover_and_get_profile(business_url)

    async def _handle_stdin():
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            try:
                request = json.loads(line)
                response = await handle_mcp_request(request, business_url, profile)
                sys.stdout.write(json.dumps(response) + "\\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                pass

    asyncio.run(_handle_stdin())


def run_sse(business_url: str, port: int):
    """Run MCP server over SSE (HTTP)."""
    import asyncio
    from http.server import HTTPServer, BaseHTTPRequestHandler

    profile = _discover_and_get_profile(business_url)
    pending_responses: dict[str, Any] = {}

    class MCPHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                request = json.loads(body)
                response = asyncio.run(handle_mcp_request(request, business_url, profile))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"UCP MCP Server running. Use POST with JSON-RPC.")

        def log_message(self, format, *args):
            pass  # Suppress logs

    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"UCP MCP Server running on http://0.0.0.0:{port}")
    print(f"Business: {business_url}")
    print(f"Capabilities: {list(profile.get('ucp', {}).get('capabilities', {}).keys())}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UCP MCP Server")
    parser.add_argument("--business-url", required=True, help="UCP Business URL")
    parser.add_argument("--port", type=int, default=8100, help="HTTP port (SSE mode)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse", help="MCP transport")
    args = parser.parse_args()

    if args.transport == "stdio":
        run_stdio(args.business_url)
    else:
        run_sse(args.business_url, args.port)
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    return path


def run_tool(args: dict[str, Any]) -> str:
    global _PROCESS

    mode = str(args.get("mode") or "status").strip()
    business_url = str(args.get("business_url") or "").strip()
    port = int(args.get("port", 8100))
    transport = str(args.get("transport") or "sse").strip()

    if mode == "status":
        with _PROCESS_LOCK:
            running = _PROCESS is not None and _PROCESS.poll() is None
        if running:
            return json.dumps({
                "ok": True,
                "mode": mode,
                "status": "running",
                "port": port,
                "transport": transport,
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "ok": True,
                "mode": mode,
                "status": "stopped",
            }, ensure_ascii=False, indent=2)

    if mode == "start":
        with _PROCESS_LOCK:
            if _PROCESS is not None and _PROCESS.poll() is None:
                return json.dumps({
                    "ok": False,
                    "error": {"code": "already_running", "message": "Server is already running. Stop it first."},
                }, ensure_ascii=False)

            if not business_url:
                return json.dumps({
                    "ok": False,
                    "error": {"code": "invalid_argument", "message": "business_url is required."},
                }, ensure_ascii=False)

            script_path = _ensure_mcp_server_script()
            cmd = [
                sys.executable, script_path,
                "--business-url", business_url,
                "--port", str(port),
                "--transport", transport,
            ]

            _PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(script_path),
            )
            time.sleep(2)

            if _PROCESS.poll() is not None:
                stderr = _PROCESS.stderr.read(500).decode("utf-8") if _PROCESS.stderr else ""
                _PROCESS = None
                return json.dumps({
                    "ok": False,
                    "error": {"code": "start_failed", "message": f"Server failed to start: {stderr}"},
                }, ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "mode": mode,
            "status": "running",
            "business_url": business_url,
            "mcp_endpoint": f"http://localhost:{port}",
            "transport": transport,
            "usage_tip": "Add this endpoint to your MCP config or use ucp_discover to see MCP capabilities.",
        }, ensure_ascii=False, indent=2)

    if mode == "stop":
        with _PROCESS_LOCK:
            if _PROCESS is None or _PROCESS.poll() is not None:
                _PROCESS = None
                return json.dumps({
                    "ok": True,
                    "mode": mode,
                    "status": "already_stopped",
                }, ensure_ascii=False)

            _PROCESS.terminate()
            try:
                _PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _PROCESS.kill()
                _PROCESS.wait()
            _PROCESS = None

        return json.dumps({
            "ok": True,
            "mode": mode,
            "status": "stopped",
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        "ok": False,
        "error": {"code": "invalid_mode", "message": f"Unknown mode: {mode}"},
    }, ensure_ascii=False)
