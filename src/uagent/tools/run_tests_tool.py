"""run_tests_tool

テストを実行するためのラッパーツール。

目的:
- cmd_exec/pwsh_exec を直接呼ぶよりも、テスト実行を定型化し、結果を構造化して返す。
- framework=auto で pytest / unittest / npm を簡易検出する。

安全方針:
- テスト実行は基本的に危険操作ではないため human_ask は行わない。
- ただしコマンド注入的な入力（&&, |, > 等）を含む extra_args は拒否する。

実装:
- 内部では cmd_exec_json_tool を利用し、returncode/stdout/stderr を扱う。
- stdout/stderr は callbacks.truncate_output があれば適用する。
- cwd 指定は cmd_exec_json の cwd 引数を使う（cd && は使わない）。

追加機能:
- pythonpath: 追加の PYTHONPATH を設定してテストを実行する。
  - Windows: set PYTHONPATH=<pythonpath>;%PYTHONPATH% && <cmd>
  - POSIX : PYTHONPATH=<pythonpath>:$PYTHONPATH <cmd>

"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:run_tests"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "run_tests",
        "description": (
            "テストを実行します。framework=auto で pytest/unittest/npm を簡易検出します。"
            " extra_args は配列で受け取り、危険なシェルメタ文字を含むものは拒否します。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "framework": {
                    "type": "string",
                    "enum": ["auto", "pytest", "unittest", "npm"],
                    "default": "auto",
                    "description": "テストフレームワーク種別",
                },
                "target": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "対象（pytestのパス、unittestの開始ディレクトリ、npm script等）。nullなら既定。",
                },
                "extra_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "追加引数（配列）。危険なメタ文字を含む場合は拒否します。",
                },
                "cwd": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "実行ディレクトリ（workdir配下のみ許可）。nullなら現在。",
                },
                "pythonpath": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "追加のPYTHONPATH（例: 'src'）。指定した場合、テスト実行時にPYTHONPATHへ先頭追加します。Windowsは cmd の set を使って適用します。",
                },
                "report": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "json",
                    "description": "出力形式",
                },
            },
        },
    },
}


_META_RE = re.compile(r"(&&|\|\||\||>>|>|<)")


def _reject_if_meta(s: str) -> Optional[str]:
    if _META_RE.search(s or ""):
        return f"shell metacharacters are not allowed in arguments: {s!r}"
    return None


def _exists_any(names: List[str]) -> bool:
    return any(os.path.exists(n) for n in names)


def _detect_framework() -> str:
    if _exists_any(["pytest.ini", "conftest.py"]):
        return "pytest"
    if os.path.exists("package.json"):
        return "npm"
    if os.path.isdir("tests"):
        return "unittest"
    return "auto"


def _truncate(label: str, text: str) -> str:
    from .context import get_callbacks

    cb = get_callbacks()
    trunc = getattr(cb, "truncate_output", None) if cb is not None else None
    if callable(trunc):
        try:
            return trunc(label, text, 400_000)
        except Exception:
            return text
    return text


def _cmd_exec_json(
    command: str, cwd: Optional[str]
) -> Tuple[str, str, int, Optional[str]]:
    try:
        from .cmd_exec_json_tool import run_tool as cmd_exec_json

        out = cmd_exec_json({"command": command, "cwd": cwd})
        obj = json.loads(out)
        if obj.get("blocked"):
            return "", "", 1, str(obj.get("reason") or "blocked")
        if obj.get("timeout"):
            return "", "", 124, str(obj.get("message") or "timeout")
        stdout = str(obj.get("stdout") or "")
        stderr = str(obj.get("stderr") or "")
        code = int(obj.get("returncode") or 0)
        return stdout, stderr, code, None
    except Exception as e:
        return (
            "",
            f"cmd_exec_json unavailable: {type(e).__name__}: {e}",
            1,
            "unavailable",
        )


def _apply_pythonpath_prefix(cmd_str: str, pythonpath: Optional[str]) -> str:
    if not pythonpath:
        return cmd_str

    pp = str(pythonpath)

    # Very small guard: reject shell metacharacters in pythonpath
    err = _reject_if_meta(pp)
    if err:
        # Keep behavior consistent with other validation paths
        raise ValueError(err)

    if os.name == "nt":
        return f"set PYTHONPATH={pp};%PYTHONPATH% && {cmd_str}"

    # POSIX style
    return f"PYTHONPATH={pp}:$PYTHONPATH {cmd_str}"


def run_tool(args: Dict[str, Any]) -> str:
    framework = str(args.get("framework") or "auto")
    target = args.get("target", None)
    extra_args = args.get("extra_args", []) or []
    cwd = args.get("cwd", None)
    pythonpath = args.get("pythonpath", None)
    report = str(args.get("report") or "json")

    if framework not in ("auto", "pytest", "unittest", "npm"):
        return json.dumps(
            {"ok": False, "error": f"invalid framework: {framework}"},
            ensure_ascii=False,
        )

    if report not in ("text", "json"):
        return json.dumps(
            {"ok": False, "error": f"invalid report: {report}"}, ensure_ascii=False
        )

    sanitized_args: List[str] = []
    for a in extra_args:
        a = str(a)
        err = _reject_if_meta(a)
        if err:
            return json.dumps({"ok": False, "error": err}, ensure_ascii=False)
        sanitized_args.append(a)

    run_cwd: Optional[str] = None
    if cwd is not None:
        if is_path_dangerous(str(cwd)):
            return json.dumps(
                {"ok": False, "error": f"dangerous cwd rejected: {cwd}"},
                ensure_ascii=False,
            )
        try:
            run_cwd = ensure_within_workdir(str(cwd))
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"cwd not allowed: {e}"}, ensure_ascii=False
            )

    detected = None
    if framework == "auto":
        detected = _detect_framework()
        if detected == "auto":
            return json.dumps(
                {"ok": False, "error": "framework auto-detect failed"},
                ensure_ascii=False,
            )
        framework = detected

    cmd_parts: List[str] = []
    if framework == "pytest":
        cmd_parts = ["python", "-m", "pytest", "-q"]
        if target:
            cmd_parts.append(str(target))
        cmd_parts.extend(sanitized_args)
    elif framework == "unittest":
        cmd_parts = ["python", "-m", "unittest", "discover"]
        if target:
            cmd_parts.extend(["-s", str(target)])
        else:
            cmd_parts.extend(["-s", "tests"])
        cmd_parts.extend(sanitized_args)
    elif framework == "npm":
        cmd_parts = ["npm", "test"]
        if target:
            cmd_parts.append(str(target))
        cmd_parts.extend(sanitized_args)
    else:
        return json.dumps(
            {"ok": False, "error": f"unsupported framework: {framework}"},
            ensure_ascii=False,
        )

    def q(x: str) -> str:
        x = str(x)
        if not x:
            return '""'
        if " " in x or "\t" in x or '"' in x:
            x = x.replace('"', '\\"')
            return f'"{x}"'
        return x

    cmd_str = " ".join(q(p) for p in cmd_parts)

    try:
        cmd_str = _apply_pythonpath_prefix(cmd_str, pythonpath)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    stdout, stderr, code, err_tag = _cmd_exec_json(cmd_str, cwd=run_cwd)

    stdout_t = _truncate("run_tests stdout", stdout)
    stderr_t = _truncate("run_tests stderr", stderr)

    result: Dict[str, Any] = {
        "ok": code == 0,
        "framework": framework,
        "detected": detected,
        "command": cmd_str,
        "cwd": run_cwd,
        "returncode": code,
        "stdout": stdout_t,
        "stderr": stderr_t,
    }
    if err_tag:
        result["error_tag"] = err_tag

    if report == "text":
        return (
            f"framework={framework}\n"
            f"cwd={run_cwd}\n"
            f"command={cmd_str}\n"
            f"returncode={code}\n\n"
            f"[stdout]\n{stdout_t}\n\n"
            f"[stderr]\n{stderr_t}\n"
        )

    return json.dumps(result, ensure_ascii=False)
