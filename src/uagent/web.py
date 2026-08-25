"""Web UI for uagent (FastAPI).

The implementation was split out into the ``web_impl`` package (see
``web_impl/`` for details).  This module preserves the ``uagent.web`` import
surface (``app``, ``web_manager``, route handlers, ``init_web``, ``main``)
and the ``python -m uagent.web`` entry point.
"""

from __future__ import annotations

from .web_impl.app import (
    BASE_DIR,
    STATIC_DIR,
    TEMPLATE_DIR,
    app,
    templates,
)
from .web_impl.helpers import (
    ANSI_ESCAPE,
    _STATE_TOKEN_RE,
    _enrich_message_attachments,
    _lang_from_accept_language,
    _load_input_history,
    _save_input_history,
    _strip_state_markers,
)
from .web_impl.rooms import (
    WebManager,
    WebRoom,
    _broadcast_modes_all,
    _handle_mode_command,
    _thread_ctx,
    web_manager,
)
from .web_impl.io import (
    WebStderr,
    WebStdout,
    _web_console_log_enabled,
    _web_debug_enabled,
    _web_server_log,
    web_human_ask,
    web_set_status,
)
from .web_impl.history import (
    _bootstrap_room_on_connect,
    _ensure_room_history_initialized,
)
from .web_impl.agent_worker import run_agent_worker
from .web_impl.routes_pages import (
    get_local_file,
    get_room,
    get_root,
    upload_files,
)
from .web_impl.routes_api import (
    _genre_enabled,
    _log_first_user_message,
    add_memory,
    api_command,
    clear_profile,
    delete_memory,
    get_log_preview,
    get_log_preview_by_path,
    get_logs,
    get_memories,
    get_profile,
    get_tool_genres,
    get_tools_enabled,
    profile_from_logs,
    set_tool_genre,
    set_tools_enabled,
    update_memory,
    update_profile,
)
from .web_impl.routes_ws import websocket_endpoint
from .web_impl.init import init_web, main

__all__ = [
    "ANSI_ESCAPE",
    "BASE_DIR",
    "STATIC_DIR",
    "TEMPLATE_DIR",
    "WebManager",
    "WebRoom",
    "WebStderr",
    "WebStdout",
    "_STATE_TOKEN_RE",
    "_bootstrap_room_on_connect",
    "_broadcast_modes_all",
    "_enrich_message_attachments",
    "_ensure_room_history_initialized",
    "_genre_enabled",
    "_handle_mode_command",
    "_lang_from_accept_language",
    "_load_input_history",
    "_log_first_user_message",
    "_save_input_history",
    "_strip_state_markers",
    "_thread_ctx",
    "_web_console_log_enabled",
    "_web_debug_enabled",
    "_web_server_log",
    "add_memory",
    "api_command",
    "app",
    "clear_profile",
    "delete_memory",
    "get_local_file",
    "get_log_preview",
    "get_log_preview_by_path",
    "get_logs",
    "get_memories",
    "get_profile",
    "get_room",
    "get_root",
    "get_tool_genres",
    "get_tools_enabled",
    "init_web",
    "main",
    "profile_from_logs",
    "run_agent_worker",
    "set_tool_genre",
    "set_tools_enabled",
    "templates",
    "update_memory",
    "update_profile",
    "upload_files",
    "web_human_ask",
    "web_manager",
    "web_set_status",
    "websocket_endpoint",
]


if __name__ == "__main__":
    main()
