"""Common helpers shared across uagent (moved from util_tools.py)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import tools
from .env_utils import env_get
from .i18n import _
from .tools.context import ToolCallbacks

# Default translation function used when core.tr is not provided.
# Kept as a separate name for backward-compatibility.
tr = _
tr_ = _


def strip_surrogates(text: str) -> str:
    """Normalize UTF-16 surrogates for prompt_toolkit/UTF-8 output.

    A valid high+low surrogate pair is folded into the actual Unicode scalar
    value so prompt_toolkit can render it as an emoji. A lone surrogate has
    no valid display character and is replaced with U+FFFD.
    """
    if not isinstance(text, str) or not text:
        return text
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text
    try:
        return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    except Exception:
        return "".join("�" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in text)


@dataclass
class CommandResult:
    continue_running: bool = True
    run_llm: bool = False
    prompt: str | None = None

    def __bool__(self) -> bool:
        return self.continue_running


def init_tools_callbacks(core: Any) -> None:
    """tools 側へ、ホスト側の依存（core の関数・状態）を注入する。"""

    cb = ToolCallbacks(
        set_status=getattr(core, "set_status", None),
        debug=getattr(core, "debug", None),
        log=getattr(core, "log", None),
        error=getattr(core, "error", None),
        exception=getattr(core, "exception", None),
        rewrite_current_log_from_messages=getattr(
            core, "rewrite_current_log_from_messages", None
        ),
        log_message=getattr(core, "log_message", None),
        prompt_history_append=getattr(core, "prompt_history_append", None),
        get_env=getattr(core, "get_env", None),
        get_env_url=getattr(core, "get_env_url", None),
        truncate_output=(
            (
                lambda label, text, limit=200000: core.truncate_output(
                    label, text, limit=limit
                )
            )
            if hasattr(core, "truncate_output")
            else None
        ),
        human_ask_lock=getattr(core, "human_ask_lock", None),
        human_ask_active_ref=(lambda: getattr(core, "human_ask_active", False)),
        human_ask_set_active=(
            (lambda v: setattr(core, "human_ask_active", bool(v)))
            if hasattr(core, "human_ask_active")
            else None
        ),
        human_ask_queue_ref=(lambda: getattr(core, "human_ask_queue", None)),
        human_ask_set_queue=(
            (lambda q: setattr(core, "human_ask_queue", q))
            if hasattr(core, "human_ask_queue")
            else None
        ),
        human_ask_lines_ref=(lambda: getattr(core, "human_ask_lines", [])),
        human_ask_multiline_active_ref=(
            lambda: getattr(core, "human_ask_multiline_active", False)
        ),
        human_ask_set_multiline_active=(
            (lambda v: setattr(core, "human_ask_multiline_active", bool(v)))
            if hasattr(core, "human_ask_multiline_active")
            else None
        ),
        human_ask_set_password=(
            (lambda v: setattr(core, "human_ask_is_password", bool(v)))
            if hasattr(core, "human_ask_is_password")
            else None
        ),
        is_auto_pilot_active=(
            (lambda: getattr(core, "auto_pilot_active", False))
            if hasattr(core, "auto_pilot_active")
            else None
        ),
        event_queue=getattr(core, "event_queue", None),
        session_id=getattr(core, "session_id", None),
        session_store=getattr(core, "session_store", None),
        cmd_encoding=getattr(core, "CMD_ENCODING", "utf-8"),
        cmd_exec_timeout_ms=getattr(core, "CMD_EXEC_TIMEOUT_MS", 60_000),
        python_exec_timeout_ms=getattr(core, "PYTHON_EXEC_TIMEOUT_MS", 60_000),
        url_fetch_timeout_ms=getattr(core, "URL_FETCH_TIMEOUT_MS", 60_000),
        url_fetch_max_bytes=getattr(core, "URL_FETCH_MAX_BYTES", 1_000_000),
        read_file_max_bytes=getattr(core, "READ_FILE_MAX_BYTES", 1_000_000),
        is_gui=False,
    )

    tools.init_callbacks(cb)


def parse_startup_args() -> tuple[dict[str, Any], list[str]]:
    # ``uag realtime`` is a startup mode, rather than a normal initial file.
    # Remove it before argparse so existing positional-file behavior is unchanged.
    realtime = False
    argv = list(sys.argv[1:])
    if argv and argv[0].lower() == "realtime":
        realtime = True
        argv.pop(0)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--workdir",
        "-C",
        dest="workdir",
        help=_(
            "Specify working directory. If not set, uses UAGENT_WORKDIR env var or the current directory."
        ),
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=_(
            "Non-interactive mode. Do not start the stdin loop; exit after processing the startup file (if any)."
        ),
    )
    parser.add_argument(
        "--tool-genre-mask",
        type=int,
        default=None,
        help=_(
            "Tool genre bitmask (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,256=file,512=index,1024=dev,2048=web,4096=utility,8191=all). Skips the interactive genre prompt when specified."
        ),
    )
    parser.add_argument(
        "--use-tool",
        dest="use_tool",
        action="store_true",
        default=None,
        help=_("Enable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--no-use-tool",
        dest="use_tool",
        action="store_false",
        default=None,
        help=_("Disable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--computer-use",
        dest="computer_use",
        action="store_true",
        default=None,
        help=_("Enable Computer Use (overrides UAGENT_COMPUTER_USE env var)."),
    )
    parser.add_argument(
        "--no-computer-use",
        dest="computer_use",
        action="store_false",
        default=None,
        help=_("Disable Computer Use (overrides UAGENT_COMPUTER_USE env var)."),
    )
    parser.add_argument(
        "--inject-message",
        "-M",
        dest="inject_message",
        default=None,
        help=_(
            "Inject a message into the LLM at startup and exit after completion. Implies --non-interactive."
        ),
    )
    parser.add_argument(
        "--inject-message-auto",
        dest="inject_message_auto",
        default=None,
        help=_(
            "Start auto-pilot with an injected goal. Include --max-rounds N or --infinite in the value."
        ),
    )
    parser.add_argument(
        "--enable-tool",
        dest="enable_tools",
        action="append",
        default=None,
        help=_(
            "Enable a specific tool by name at startup. "
            "Can be specified multiple times or as a comma-separated list."
        ),
    )
    parser.add_argument(
        "--embedded",
        dest="embedded",
        action="store_true",
        default=False,
        help=_(
            "Embedded mode: disables the session store (UAGENT_SESSION_STORE=0) "
            "and hides tool management tools (tool_catalog, tool_load, unload_tool)."
        ),
    )
    parser.add_argument(
        "--plugin-dir",
        dest="plugin_dirs",
        action="append",
        default=None,
        help=_("Load a plugin from a directory (can be specified multiple times)."),
    )
    args, unknown = parser.parse_known_args(argv)
    if args.inject_message_auto is not None:
        args.non_interactive = True
    if args.enable_tools:
        # Support comma-separated values in addition to repeated flags:
        # --enable-tool a,b --enable-tool c  ->  [a, b, c] (order preserved)
        flat: list[str] = []
        for item in args.enable_tools:
            for part in str(item).split(","):
                part = part.strip()
                if part:
                    flat.append(part)
        args.enable_tools = flat
    parsed = vars(args)
    parsed["realtime"] = realtime
    return parsed, unknown


def iter_backup_files(root_dir: str) -> list[str]:
    """Find backup files under root_dir.

    Backup pattern:
    - *.org
    - *.org<digits>

    Returns list of file paths.
    """
    root = Path(root_dir)
    results: list[str] = []
    if not root.exists():
        return results

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".org"):
            results.append(str(p))
            continue
        m = re.match(r"^.+\.org\d+$", name)
        if m:
            results.append(str(p))

    return results


def load_agents_md() -> str:
    """\u8d77\u52d5\u30c7\u30a3\u30ec\u30af\u30c8\u30ea\u306b AGENTS.md \u304c\u3042\u308c\u3070\u5185\u5bb9\u3092\u8fd4\u3059\u3002"""
    agents_path = os.path.join(os.getcwd(), "AGENTS.md")
    if not os.path.isfile(agents_path):
        return ""

    if getattr(load_agents_md, "_loaded", False):
        return ""

    try:
        from tools.read_file_tool import run_tool as read_file

        content = read_file({"filename": agents_path})
        obj = json.loads(content)
        if obj.get("ok"):
            setattr(load_agents_md, "_loaded", True)
            return str(obj.get("content", ""))
        return ""
    except Exception:
        return ""


def append_result_to_outfile(text: str) -> None:
    """UAGENT_OUTFILE \u304c\u6307\u5b9a\u3055\u308c\u3066\u3044\u308c\u3070\u3001\u30a2\u30b7\u30b9\u30bf\u30f3\u30c8\u6700\u7d42\u51fa\u529b\u3092\u8ffd\u8a18\u3059\u308b\u3002"""
    out_path = env_get("UAGENT_OUTFILE")
    if not out_path:
        return

    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
    except Exception:
        return
