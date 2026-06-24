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
        self._websocket: Any = None
        self._startup_cache = None  # Cache for (provider, client, depname, messages)

    async def _send_chunk(self, data: str) -> None:
        """Send a streaming text chunk to the current WebSocket, if available."""
        import logging
        logger = logging.getLogger("uag.ws_handler")
        if self._websocket is not None:
            try:
                msg = {"type": "chunk", "data": data}
                payload = json.dumps(msg, ensure_ascii=False)
                await self._websocket.send(payload)
                logger.info("_send_chunk sent OK (len=%d)", len(payload))
            except (Exception, SystemExit) as e:
                logger.error("_send_chunk failed: %s", e)
        else:
            logger.info("_send_chunk: no websocket")

    async def _send_progress(self, data: str) -> None:
        """Send a progress notification via the current WebSocket, if available."""
        import logging
        logger = logging.getLogger("uag.ws_handler")
        if self._websocket is not None:
            try:
                msg = {"type": "progress", "data": data}
                await self._websocket.send(json.dumps(msg, ensure_ascii=False))
                logger.info("_send_progress sent: %s", data)
            except Exception as e:
                logger.error("_send_progress failed: %s", e)

    async def dispatch(self, msg: dict, websocket=None) -> dict:
        """Route a message to the appropriate handler method."""
        self._websocket = websocket
        method = msg.get("method", "")
        params = msg.get("params", {})
        req_id = msg.get("id")

        handlers = {
            "chat": self.handle_chat,
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
        except (Exception, SystemExit) as e:
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

    async def handle_chat(self, params: dict) -> dict:
        """Send a message to the LLM and return the reply."""
        message = params.get("message", "")
        if not message:
            raise ValueError("'message' is required")
        # Notify progress before potentially slow startup / LLM call
        await self._send_progress("準備中...")
        import asyncio
        await asyncio.sleep(0)  # flush send buffer so client sees progress

        # Cache startup state so conversation history is preserved across calls.
        try:
            from uagent.cli_startup import run_cli_startup
            from uagent.providers import util_providers as _providers
            from uagent import uagent_llm as llm_util
            from uagent import core as _core

            if self._startup_cache is None:
                startup = await asyncio.to_thread(
                    run_cli_startup,
                    core=_core,
                    cli_workdir=os.getcwd(),
                    env_workdir="",
                    initial_file_arg="",
                    non_interactive=True,
                    tool_genre_mask=0,
                )
                if not startup.provider or not startup.client:
                    return {"reply": "[uag] Startup failed. Check UAGENT_PROVIDER and API key."}
                self._startup_cache = {
                    "provider": startup.provider,
                    "client": startup.client,
                    "depname": startup.depname,
                    "messages": startup.messages,
                }

            cache = self._startup_cache
            await self._send_progress("LLMに問い合わせ中...")

            # Append user message
            user_msg = {"role": "user", "content": message}
            cache["messages"].append(user_msg)

            import asyncio
            await asyncio.to_thread(
                llm_util.run_llm_rounds,
                cache["provider"],
                cache["client"],
                cache["depname"],
                cache["messages"],
                core=_core,
                make_client_fn=_providers.make_client,
                append_result_to_outfile_fn=lambda *a, **kw: None,
                try_open_images_from_text_fn=lambda *a, **kw: None,
            )

            await self._send_progress("応答を処理中...")

            # Extract the last assistant message as reply
            reply = ""
            for m in reversed(cache["messages"]):
                if isinstance(m, dict) and m.get("role") == "assistant":
                    content = m.get("content", "")
                    if content:
                        reply = content
                        break

            self.session_mgr.save_message("user", message)
            self.session_mgr.save_message("assistant", reply or "(empty response)")

            # Stream the final reply as chunks so VSCode can display it
            if reply:
                await self._send_chunk(reply)

            return {"reply": reply or "[uag] No response generated."}

        except (Exception, SystemExit) as e:
            import traceback
            return {"reply": f"[uag] LLM error: {e}\n{traceback.format_exc()[:500]}"}


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
