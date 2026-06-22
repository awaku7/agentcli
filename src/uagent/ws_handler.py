from __future__ import annotations

"""
WebSocket message handler for VSCode extension integration.
Dispatches incoming messages to the appropriate handler.
"""

import json
import os
from pathlib import Path
from typing import Any

from uagent.ws_config import WsConfigManager
from uagent.ws_session import WsSessionManager


class WsHandler:
    """Handles incoming WebSocket messages and routes them to methods."""

    def __init__(self):
        self.session_mgr = WsSessionManager()
        self.config_mgr = WsConfigManager()

    async def dispatch(self, msg: dict) -> dict:
        """Route a message to the appropriate handler method."""
        method = msg.get("method", "")
        params = msg.get("params", {})
        req_id = msg.get("id")

        handlers = {
            "ping": self.handle_ping,
            "tools/list": self.handle_tools_list,
            "tools/get": self.handle_tools_get,
            "tool/execute": self.handle_tool_execute,
            "config/get": self.handle_config_get,
            "config/set": self.handle_config_set,
            "session/list": self.handle_session_list,
            "session/load": self.handle_session_load,
            "session/new": self.handle_session_new,
            "session/delete": self.handle_session_delete,
            "files/read": self.handle_files_read,
            "workdir/get": self.handle_workdir_get,
            "workdir/set": self.handle_workdir_set,
            "system/specs": self.handle_system_specs,
        }

        handler = handlers.get(method)
        if not handler:
            return {
                "id": req_id,
                "ok": False,
                "error": {
                    "code": "METHOD_NOT_FOUND",
                    "message": f"Unknown method: {method}",
                },
            }

        try:
            result = await handler(params)
            return {"id": req_id, "ok": True, "result": result}
        except FileNotFoundError as e:
            return {
                "id": req_id,
                "ok": False,
                "error": {"code": "FILE_NOT_FOUND", "message": str(e)},
            }
        except PermissionError as e:
            return {
                "id": req_id,
                "ok": False,
                "error": {"code": "PERMISSION_DENIED", "message": str(e)},
            }
        except ValueError as e:
            return {
                "id": req_id,
                "ok": False,
                "error": {"code": "INVALID_PARAMS", "message": str(e)},
            }
        except Exception as e:
            return {
                "id": req_id,
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                },
            }

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def handle_ping(self, params: dict) -> dict:
        """Health check."""
        import time

        return {"pong": True, "timestamp": time.time()}

    async def handle_tools_list(self, params: dict) -> dict:
        """Return a simplified list of all available tools."""
        from uagent.tools import get_tool_catalog

        raw_tools = get_tool_catalog(query="")
        tools = []
        for t in raw_tools:
            tools.append(
                {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "genre": t.get("genre", "unknown"),
                    "parallel_safe": t.get("loaded", False),
                    "parameters": t.get("parameters", []),
                }
            )
        return {"tools": tools}

    async def handle_tools_get(self, params: dict) -> dict:
        """Get detailed spec for a single tool."""
        name = params.get("name", "")
        if not name:
            raise ValueError("'name' is required")
        result = await self.handle_tools_list({})
        for t in result["tools"]:
            if t["name"] == name:
                return {"spec": t}
        raise ValueError(f"Tool '{name}' not found")

    async def handle_tool_execute(self, params: dict) -> dict:
        """Execute a tool by name with given arguments."""
        name = params.get("name", "")
        args = params.get("args", {})
        if not name:
            raise ValueError("'name' is required")

        from uagent.tools import run_tool

        raw_result = run_tool(name, args)
        try:
            parsed = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            parsed = {"raw": str(raw_result)}
        return {"result": parsed}

    async def handle_config_get(self, params: dict) -> dict:
        """Get config value(s)."""
        key = params.get("key")
        if key:
            return {"config": {key: self.config_mgr.get(key)}}
        return {"config": self.config_mgr.get_all()}

    async def handle_config_set(self, params: dict) -> dict:
        """Set a config value (session-scoped, does not modify env)."""
        key = params.get("key")
        value = params.get("value")
        if not key:
            raise ValueError("'key' is required")
        self.config_mgr.set(key, value)
        return {"ok": True}

    async def handle_session_list(self, params: dict) -> dict:
        """List all saved sessions."""
        sessions = self.session_mgr.list_sessions()
        return {"sessions": sessions}

    async def handle_session_load(self, params: dict) -> dict:
        """Load a session by index."""
        index = int(params.get("index", 0))
        session = self.session_mgr.load(index)
        if session is None:
            raise ValueError(f"Session index {index} not found")
        return {"session": session}

    async def handle_session_new(self, params: dict) -> dict:
        """Create a new session."""
        session_id = self.session_mgr.create()
        return {"id": session_id}

    async def handle_session_delete(self, params: dict) -> dict:
        """Delete a session by ID."""
        session_id = params.get("id", "")
        if not session_id:
            raise ValueError("'id' is required")
        deleted = self.session_mgr.delete(session_id)
        return {"deleted": deleted}

    async def handle_files_read(self, params: dict) -> dict:
        """Read a file within the workdir."""
        path = params.get("path", "")
        if not path:
            raise ValueError("'path' is required")

        from uagent.tools.safe_file_ops_extras import ensure_within_workdir

        safe_path = ensure_within_workdir(path)
        if not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File not found: {safe_path}")

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        ext = Path(safe_path).suffix.lower()
        lang_map = {
            ".py": "python", ".ts": "typescript", ".js": "javascript",
            ".jsx": "javascriptreact", ".tsx": "typescriptreact",
            ".html": "html", ".css": "css", ".json": "json",
            ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
            ".rs": "rust", ".go": "go", ".java": "java",
            ".cs": "csharp", ".cpp": "cpp", ".c": "c",
            ".h": "c", ".hpp": "cpp", ".rb": "ruby",
            ".php": "php", ".swift": "swift", ".kt": "kotlin",
            ".toml": "toml", ".xml": "xml", ".sql": "sql",
            ".sh": "bash", ".bat": "batch", ".ps1": "powershell",
            ".dockerfile": "dockerfile", ".txt": "text",
        }
        language = lang_map.get(ext, "text")
        return {"content": content, "language": language, "size": len(content)}

    async def handle_workdir_get(self, params: dict) -> dict:
        """Get the current working directory."""
        from uagent.tools.context import get_callbacks

        cb = get_callbacks()
        return {"path": str(cb.get_workdir())}

    async def handle_workdir_set(self, params: dict) -> dict:
        """Set the working directory (must be within workdir)."""
        path = params.get("path", "")
        if not path:
            raise ValueError("'path' is required")

        from uagent.tools.safe_file_ops_extras import ensure_within_workdir
        from uagent.tools.context import get_callbacks

        safe_path = ensure_within_workdir(path)
        cb = get_callbacks()
        cb.set_workdir(safe_path)
        return {"ok": True, "path": safe_path}

    async def handle_system_specs(self, params: dict) -> dict:
        """Return basic system information."""
        import platform

        return {
            "platform": platform.system(),
            "release": platform.release(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }
