# tools/python_exec.py
from typing import Any, Dict
import os
import subprocess
import tempfile

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:python_exec"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "python_exec",
        "description": (
            "Python コードを実行します。計算、データ処理、スクリプトの実行など、Python が適したタスクにはこのツールを最優先で使用してください。"
        ),
        "system_prompt": """Python コードを実行します。
- Python の標準ライブラリや計算が必要な場合、または .py ファイルを実行する場合は、cmd_exec ではなく必ずこのツールを使用してください。
- 実行前に簡単に何を実行するかを表示すること。
""",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "実行する Python コード。一行でも複数行でもよい。",
                }
            },
            "required": ["code"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    code = args.get("code", "")
    if not isinstance(code, str):
        code = str(code)

    # 一時ファイルにコードを書いて実行（-c は一部環境で壊れることがあるため）
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(code)
            tmp_path = tf.name

        proc = subprocess.run(
            ["python", tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=cb.cmd_encoding,
            errors="replace",
            timeout=cb.python_exec_timeout_ms / 1000.0,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"[python_exec timeout] {cb.python_exec_timeout_ms / 1000:.0f}秒以内に終了しませんでした"
    except Exception as e:
        return f"[python_exec error] {type(e).__name__}: {e}"
    finally:
        try:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    out_str = proc.stdout or ""
    err_str = proc.stderr or ""

    if proc.returncode != 0:
        msg = (
            f"[python_exec error] returncode={proc.returncode}\n"
            f"STDOUT:\n{out_str}\n"
            f"STDERR:\n{err_str}"
        )
        if cb.truncate_output is not None:
            return cb.truncate_output("python_exec", msg, 400_000)
        return msg

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += f"\n[stderr]\n{err_str}"

    if cb.truncate_output is not None:
        return cb.truncate_output("python_exec", out_str, 400_000)
    return out_str
