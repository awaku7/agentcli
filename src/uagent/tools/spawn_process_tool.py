from __future__ import annotations

# tools/spawn_process.py
import os
import subprocess
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "function": {
        "description": _(
            "tool.description",
            default=(
                "Asynchronously start an external GUI or browser process. Avoid repeated spawns for the same request."
            ),
        ),
        "name": "spawn_process",
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "spawn_process",
                "spawn process",
                "launch process",
                "start app",
                "gui process",
                "browser process",
            ],
        ),
        "x_search_terms_en": [
            "spawn_process",
            "spawn process",
            "launch process",
            "start app",
            "gui process",
            "browser process",
        ],
        "parameters": {
            "properties": {
                "command": {
                    "description": _(
                        "param.command.description",
                        default="Command line to execute.",
                    ),
                    "type": "string",
                }
            },
            "required": ["command"],
            "type": "object",
        },
    },
    "type": "function",
    "tool_genre": "basic",
}


def _validate_command(raw: str) -> str | None:
    """Rough validation for the command string.

    Returns:
      - error message (str) if invalid
      - None if valid
    """
    if not raw:
        return _("err.command_empty", default="[spawn_process error] command is empty")

    if os.name == "nt":
        lower = raw.strip().lower()
        # 'start' or 'start ""' alone has no target
        if lower == "start" or lower == 'start ""':
            return _(
                "err.windows_start_missing_target",
                default="[spawn_process error] Windows 'start' command has no URL or executable path.\\nExample: start \"\" https://www.google.com",
            )

    return None


def run_tool(args: dict[str, Any]) -> str:
    raw = (args.get("command") or "").strip()
    print(raw)
    err = _validate_command(raw)
    if err is not None:
        return err

    # Execute
    try:
        if os.name == "nt":
            # pass through to cmd.exe /c
            cmdline = f"cmd.exe /c {raw}"
            subprocess.Popen(
                cmdline,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            cmdline = raw
            subprocess.Popen(
                cmdline,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        return (
            "[spawn_process] Tried to start a process with the following command:\n"
            f"{cmdline}"
        )
    except Exception as e:
        # return command line for debugging
        return (
            "[spawn_process error] Exception occurred while executing the command.\n"
            f"command={raw!r}\n"
            f"error={type(e).__name__}: {e}"
        )
