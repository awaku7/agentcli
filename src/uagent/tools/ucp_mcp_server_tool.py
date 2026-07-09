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
    """Return the path to the UCP MCP server script (mcps/ucp_mcp_server_main.py)."""
    # Tools dir: src/uagent/tools/ → project root → mcps/
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "mcps",
            "ucp_mcp_server_main.py",
        )
    )


def _get_server_script_path_str() -> str:
    """Return the path to the UCP MCP server script."""
    return _get_server_script_path()


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
            return json.dumps(
                {
                    "ok": True,
                    "mode": mode,
                    "status": "running",
                    "port": port,
                    "transport": transport,
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "ok": True,
                    "mode": mode,
                    "status": "stopped",
                },
                ensure_ascii=False,
                indent=2,
            )

    if mode == "start":
        with _PROCESS_LOCK:
            if _PROCESS is not None and _PROCESS.poll() is None:
                return json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "code": "already_running",
                            "message": "Server is already running. Stop it first.",
                        },
                    },
                    ensure_ascii=False,
                )

            if not business_url:
                return json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "code": "invalid_argument",
                            "message": "business_url is required.",
                        },
                    },
                    ensure_ascii=False,
                )

            script_path = _get_server_script_path()
            cmd = [
                sys.executable,
                script_path,
                "--business-url",
                business_url,
                "--port",
                str(port),
                "--transport",
                transport,
            ]

            _PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(script_path),
            )
            time.sleep(2)

            if _PROCESS.poll() is not None:
                stderr = (
                    _PROCESS.stderr.read(500).decode("utf-8") if _PROCESS.stderr else ""
                )
                _PROCESS = None
                return json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "code": "start_failed",
                            "message": f"Server failed to start: {stderr}",
                        },
                    },
                    ensure_ascii=False,
                )

        return json.dumps(
            {
                "ok": True,
                "mode": mode,
                "status": "running",
                "business_url": business_url,
                "mcp_endpoint": f"http://localhost:{port}",
                "transport": transport,
                "usage_tip": "Add this endpoint to your MCP config or use ucp_discover to see MCP capabilities.",
            },
            ensure_ascii=False,
            indent=2,
        )

    if mode == "stop":
        with _PROCESS_LOCK:
            if _PROCESS is None or _PROCESS.poll() is not None:
                _PROCESS = None
                return json.dumps(
                    {
                        "ok": True,
                        "mode": mode,
                        "status": "already_stopped",
                    },
                    ensure_ascii=False,
                )

            _PROCESS.terminate()
            try:
                _PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _PROCESS.kill()
                _PROCESS.wait()
            _PROCESS = None

        return json.dumps(
            {
                "ok": True,
                "mode": mode,
                "status": "stopped",
            },
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        {
            "ok": False,
            "error": {"code": "invalid_mode", "message": f"Unknown mode: {mode}"},
        },
        ensure_ascii=False,
    )
