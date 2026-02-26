# tools/file_exists.py
from .i18n_helper import make_tool_translator
from .arg_util import get_path

_ = make_tool_translator(__file__)

from typing import Any, Dict
import os
import time

BUSY_LABEL = True
STATUS_LABEL = "tool:file_exists"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "file_exists",
        "description": _(
            "tool.description",
            default="Checks if a file or directory exists at the specified path and returns type, size, and modification time if it does.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool is used for the following purpose: check if a file or directory exists at the specified path and return type, size, and modification time if it does.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path of the file or directory to check for existence (supports ~).",
                    ),
                }
            },
            "required": ["path"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    expanded = get_path(args, "path", "")
    if not expanded:
        return _("err.path_empty", default="[file_exists error] path is empty")

    try:
        if not os.path.exists(expanded):
            return f"[file_exists]\npath={expanded}\nexists=False"

        is_dir = os.path.isdir(expanded)
        st = os.stat(expanded)
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        size_str = "n/a (directory)" if is_dir else f"{st.st_size} bytes"

        return (
            "[file_exists]\n"
            f"path={expanded}\n"
            "exists=True\n"
            f"is_dir={is_dir}\n"
            f"size={size_str}\n"
            f"mtime={mtime}"
        )
    except Exception as e:
        return f"[file_exists error] {type(e).__name__}: {e}"
