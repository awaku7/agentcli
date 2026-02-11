# tools/spawn_process.py
import os
import subprocess
from typing import Any, Dict

TOOL_SPEC: Dict[str, Any] = {
    "function": {
        "description": "Asynchronously start an external GUI or browser process. Avoid repeated spawns for the "
        "same request.",
        "name": "spawn_process",
        "parameters": {
            "properties": {
                "command": {"description": "Command line to execute.", "type": "string"}
            },
            "required": ["command"],
            "type": "object",
        },
        "system_prompt": "This tool performs the operation described by the tool name 'spawn_process'. Use it "
        "when that action is needed.",
    },
    "type": "function",
}


def _validate_command(raw: str) -> str | None:
    """
    コマンドのざっくりバリデーション。
    問題があればエラーメッセージ文字列を返し、正常なら None。
    """
    if not raw:
        return "[spawn_process error] command が空です"

    if os.name == "nt":
        lower = raw.strip().lower()
        # 'start' または 'start ""' だけは実行対象がないので NG
        if lower == "start" or lower == 'start ""':
            return (
                "[spawn_process error] Windows の start コマンドに "
                "URL や実行ファイルのパスが指定されていません。\n"
                '例: start "" https://www.google.com のように指定してください。'
            )

    return None


def run_tool(args: Dict[str, Any]) -> str:
    raw = (args.get("command") or "").strip()
    print(raw)
    err = _validate_command(raw)
    if err is not None:
        return err

    # ここから実行
    try:
        if os.name == "nt":
            # そのまま cmd.exe /c に渡す
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

        return f"[spawn_process] 次のコマンドでプロセス起動を試みました:\n{cmdline}"
    except Exception as e:
        # 失敗しても「どう実行しようとしたか」を必ず返す
        return (
            "[spawn_process error] コマンド実行時に例外が発生しました。\n"
            f"command={raw!r}\n"
            f"error={type(e).__name__}: {e}"
        )
