"""Import-time startup behavior for the uagent CLI (split from cli.py).

This module preserves the exact module-level code that used to run when
``uagent.cli`` was imported: i18n initialization, tool confirmation defaults,
startup argument parsing, and the ``UAGENT_*`` environment overrides.
"""

from __future__ import annotations

import importlib
import os

from ..env_utils import env_get
from ..i18n import detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from .. import tools

tools.configure_default_confirmation()

try:
    from ..tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


# OpenAI / Azure OpenAI / Google Gemini (google-genai)
# These are imported lazily inside the functions that actually need them to speed up CLI startup.
OpenAI = None
genai = None
gemini_types = None
gemini_errors = None

from ..util_tools import parse_startup_args as _parse_startup_args

# Import scheck_core
core = importlib.import_module(".core", package="uagent")

_startup_args, _startup_unknown = _parse_startup_args()
_cli_workdir = _startup_args.get("workdir")
_env_workdir = env_get("UAGENT_WORKDIR")

UAGENT_NON_INTERACTIVE = bool(_startup_args.get("non_interactive"))
UAGENT_INJECT_MESSAGE = _startup_args.get("inject_message")
UAGENT_INJECT_MESSAGE_AUTO = _startup_args.get("inject_message_auto")
if UAGENT_INJECT_MESSAGE is not None:
    UAGENT_NON_INTERACTIVE = True
if UAGENT_INJECT_MESSAGE is not None or UAGENT_INJECT_MESSAGE_AUTO is not None:
    os.environ["UAGENT_INJECT_MODE"] = "1"
# Non-interactive runs must never wait for a person or load project
# instruction files intended for an interactive session.
if UAGENT_NON_INTERACTIVE:
    os.environ["UAGENT_NON_INTERACTIVE"] = "1"
UAGENT_TOOL_GENRE_MASK = _startup_args.get("tool_genre_mask")
UAGENT_ENABLE_TOOLS = _startup_args.get("enable_tools")
UAGENT_REALTIME = bool(_startup_args.get("realtime"))
UAGENT_EMBEDDED = bool(_startup_args.get("embedded"))

# Embedded mode: no persistent session store, and tool management tools
# (tool_catalog / tool_load / unload_tool) are hidden from the LLM.
if UAGENT_EMBEDDED:
    os.environ["UAGENT_SESSION_STORE"] = "0"
    os.environ["UAGENT_EMBEDDED"] = "1"

# Initialize the shared Computer Use policy override before startup config is used.
_computer_use_arg = _startup_args.get("computer_use")
if _computer_use_arg is not None:
    os.environ["UAGENT_COMPUTER_USE"] = "1" if _computer_use_arg else "0"

# Initialize runtime tools_enabled flag.
# Priority: --use-tool / --no-use-tool CLI arg > UAGENT_USE_TOOL env var > default ON.
_use_tool_arg = _startup_args.get("use_tool")
if _use_tool_arg is not None:
    core.tools_enabled = bool(_use_tool_arg)
else:
    _use_tool_env = (env_get("UAGENT_USE_TOOL") or "").strip().lower()
    core.tools_enabled = _use_tool_env not in ("0", "false", "no", "off")

# NOTE(Mode A): workdir initialization (mkdir/chdir + startup info) is performed inside main()
# under startup stdout/stderr capture, so importing this module does not change CWD.

# Use the first element of unknown as the initial file argument if present (equivalent to the traditional sys.argv[1])
INITIAL_FILE_ARG = _startup_unknown[0] if _startup_unknown else None
