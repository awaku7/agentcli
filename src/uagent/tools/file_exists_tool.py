# tools/file_exists.py
from typing import Any, Dict
import os
import time

BUSY_LABEL = True
STATUS_LABEL = "tool:file_exists"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "file_exists",
        "description": "指定したパスにファイルまたはディレクトリが存在するかどうかを確認し、あれば種別・サイズ・更新日時を返します。",
        "system_prompt": """このツールは次の目的で使われます: 指定したパスにファイルまたはディレクトリが存在するかどうかを確認し、あれば種別・サイズ・更新日時を返します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "存在確認したいファイルまたはディレクトリのパス（~ も使用可）。",
                }
            },
            "required": ["path"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    path = (args.get("path") or "").strip()
    if not path:
        return "[file_exists error] path が空です"

    expanded = os.path.expanduser(path)
    # print(expanded)
    try:
        if not os.path.exists(expanded):
            return f"[file_exists]\npath={path} (expanded={expanded})\nexists=False"

        is_dir = os.path.isdir(expanded)
        st = os.stat(expanded)
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        size_str = "n/a (directory)" if is_dir else f"{st.st_size} bytes"

        return (
            "[file_exists]\n"
            f"path={path} (expanded={expanded})\n"
            "exists=True\n"
            f"is_dir={is_dir}\n"
            f"size={size_str}\n"
            f"mtime={mtime}"
        )
    except Exception as e:
        return f"[file_exists error] {type(e).__name__}: {e}"
