# tools/spawn_process.py
import os
import subprocess
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: Dict[str, Any] = {
    "function": {
        "description": _(
            "tool.description",
            default=(
                "Asynchronously start an external GUI or browser process. Avoid repeated spawns for the same request."
            ),
        ),
        "name": "spawn_process",
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
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool performs the operation described by the tool name 'spawn_process'. Use it when that action is needed."
            ),
        ),
    },
    "type": "function",
}


def _validate_command(raw: str) -> str | None:
    """Rough validation for the command string.

    Returns:
      - error message (str) if invalid
      - None if valid
    """
    if not raw:
        return "[spawn_process error] command is empty"

    if os.name == "nt":
        lower = raw.strip().lower()
        # 'start' or 'start ""' alone has no target
        if lower == "start" or lower == 'start ""':
            return (
                "[spawn_process error] Windows 'start' command has no URL or executable path.\n"
                "Example: start \"\" https://www.google.com"
            )

    return None


def run_tool(args: Dict[str, Any]) -> str:
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
