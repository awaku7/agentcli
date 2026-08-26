"""Interactive command-line UI for uagent.

The implementation was split out into the ``cli_impl`` package (see
``cli_impl/`` for details).  This module preserves the ``uagent.cli`` import
surface, the module-level startup side effects (delegated to
``cli_impl.startup``), and the ``python -m uagent.cli`` entry point.
"""

from __future__ import annotations

import uagent.runtime.runtime_init  # noqa: F401

from .cli_impl.startup import (
    INITIAL_FILE_ARG,
    OpenAI,
    UAGENT_EMBEDDED,
    UAGENT_ENABLE_TOOLS,
    UAGENT_INJECT_MESSAGE,
    UAGENT_NON_INTERACTIVE,
    UAGENT_REALTIME,
    UAGENT_TOOL_GENRE_MASK,
    _cli_workdir,
    _env_workdir,
    core,
    ensure_mcp_config_template,
    genai,
    gemini_errors,
    gemini_types,
)
from .cli_impl.state import (
    _CLI_SHUTDOWN,
    _PROMPT_HISTORY,
    _PROMPT_REPLY_SESSION,
    _PROMPT_SESSION,
)
from .cli_impl.history import (
    _append_prompt_history_entry,
    _bootstrap_prompt_history,
    _persist_prompt_history_entry,
)
from .cli_impl.input_ui import (
    _can_use_textarea,
    _clear_abandoned_prompt,
    _flush_stdin_input_buffer,
    _getpass_fallback,
    _make_prompt_key_bindings,
    _multiline_editor,
    _prompt_toolkit_input,
)
from .cli_impl.main import main
from .cli_impl.prompt_session import _get_prompt_session, _reset_prompt_sessions
from .cli_impl.stdin_loop import stdin_loop

__all__ = [
    "INITIAL_FILE_ARG",
    "OpenAI",
    "UAGENT_EMBEDDED",
    "UAGENT_ENABLE_TOOLS",
    "UAGENT_INJECT_MESSAGE",
    "UAGENT_NON_INTERACTIVE",
    "UAGENT_REALTIME",
    "UAGENT_TOOL_GENRE_MASK",
    "_CLI_SHUTDOWN",
    "_PROMPT_HISTORY",
    "_PROMPT_REPLY_SESSION",
    "_PROMPT_SESSION",
    "_append_prompt_history_entry",
    "_bootstrap_prompt_history",
    "_can_use_textarea",
    "_clear_abandoned_prompt",
    "_cli_workdir",
    "_env_workdir",
    "_flush_stdin_input_buffer",
    "_get_prompt_session",
    "_getpass_fallback",
    "_make_prompt_key_bindings",
    "_multiline_editor",
    "_persist_prompt_history_entry",
    "_prompt_toolkit_input",
    "_reset_prompt_sessions",
    "core",
    "ensure_mcp_config_template",
    "genai",
    "gemini_errors",
    "gemini_types",
    "main",
    "stdin_loop",
]


if __name__ == "__main__":
    main()
