# tools/lint_format_tool.py
"""lint_format_tool

Wrapper tool for running static analysis and formatters.

- Python: Prioritizes ruff / black / mypy
- JavaScript: Does not execute npx aggressively for safety (avoids unintended downloads)

Safety:
- mode=fix modifies files, so it requires human_ask confirmation.
- Arguments are received as an array and rejected if they contain dangerous shell metacharacters.

Implementation:
- Utilizes cmd_exec_json_tool.
"""

from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Optional

from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:lint_format"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "devel",
    "type": "function",
    "function": {
        "name": "lint_format",
        "description": _(
            "tool.description",
            default="Run static analysis/formatters (e.g., ruff/black/mypy). mode=fix modifies files and requires confirmation.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="Run static analysis/formatters. If additional user confirmation is required (e.g., mode=fix), use human_ask.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "lint_format",
                "lint format",
                "lint",
                "format",
                "ruff",
                "black",
            ],
        ),
        "x_search_terms_en": [
            "lint_format",
            "lint format",
            "lint",
            "format",
            "ruff",
            "black",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": _(
                        "param.tools.description",
                        default="An array of tool names to run. If empty, tools are auto-selected (ruff, black, mypy in that order).",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["check", "fix"],
                    "default": "check",
                    "description": _(
                        "param.mode.description",
                        default="Execution mode: check=check only / fix=auto-fix",
                    ),
                },
                "targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["."],
                    "description": _(
                        "param.targets.description",
                        default="An array of target paths (must be under workdir).",
                    ),
                },
                "extra_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": _(
                        "param.extra_args.description",
                        default="Additional arguments (array). Dangerous metacharacters are rejected.",
                    ),
                },
                "cwd": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": _(
                        "param.cwd.description",
                        default="Working directory (must be under workdir). Defaults to current directory if null.",
                    ),
                },
            },
        },
    },
}


_META_RE = re.compile(r"(&&|\|\||[&|;!<>`$])")


def _reject_if_meta(s: str) -> Optional[str]:
    if _META_RE.search(s or ""):
        return f"shell metacharacters are not allowed in arguments: {s!r}"
    return None


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


def _quote_cmd_parts(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([str(p) for p in parts])
    return " ".join(shlex.quote(str(p)) for p in parts)


def _cmd_exec_json(
    command: str, cwd: Optional[str]
) -> tuple[str, str, int, Optional[str]]:
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


def _tool_exists_py(module: str) -> bool:
    """Return True if `python -m <module> --version` succeeds."""
    so, se, code, _ = _cmd_exec_json(f"python -m {module} --version", cwd=None)
    return code == 0


def _tool_exists_mdformat() -> bool:
    """mdformat doesn't have a stable `--version`; use `--help` to detect."""
    so, se, code, _ = _cmd_exec_json("python -m mdformat --help", cwd=None)
    return code == 0


_TOOL_SUFFIXES: dict[str, set[str]] = {
    "ruff": {".py"},
    "black": {".py"},
    "mypy": {".py"},
    "mdformat": {".md"},
}


def _collect_targets_for_tool(targets: list[str], tool: str) -> tuple[list[str], list[str]]:
    suffixes = _TOOL_SUFFIXES.get(tool, set())
    matched: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for target in targets:
        p = Path(target)
        if not p.exists():
            missing.append(str(p))
            continue

        if p.is_file():
            if p.suffix.lower() in suffixes:
                item = str(p)
                if item not in seen:
                    seen.add(item)
                    matched.append(item)
            continue

        if p.is_dir():
            for child in p.rglob('*'):
                if child.is_file() and child.suffix.lower() in suffixes:
                    item = str(child)
                    if item not in seen:
                        seen.add(item)
                        matched.append(item)
            continue

    return matched, missing


def _human_confirm(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        res_json = human_ask({"message": message})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        return user_reply in ("y", "yes")
    except Exception:
        try:
            resp = input(message + " [y/c/N]: ")
            return resp.strip().lower() == "y"
        except Exception:
            return False


def run_tool(args: dict[str, Any]) -> str:
    tools = args.get("tools", []) or []
    mode = str(args.get("mode") or "check")
    targets = args.get("targets", ["."]) or ["."]
    extra_args = args.get("extra_args", []) or []
    cwd = args.get("cwd", None)

    if mode not in ("check", "fix"):
        return json.dumps(
            {"ok": False, "error": f"invalid mode: {mode}"}, ensure_ascii=False
        )

    sanitized_extra: list[str] = []
    for a in extra_args:
        a = str(a)
        err = _reject_if_meta(a)
        if err:
            return json.dumps({"ok": False, "error": err}, ensure_ascii=False)
        sanitized_extra.append(a)

    safe_targets: list[str] = []
    for t in targets:
        t = str(t)
        if is_path_dangerous(t):
            return json.dumps(
                {"ok": False, "error": f"dangerous target rejected: {t}"},
                ensure_ascii=False,
            )
        try:
            safe_targets.append(ensure_within_workdir(t))
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"target not allowed: {e}"}, ensure_ascii=False
            )

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

    selected: list[str] = []
    if tools:
        selected = [str(x) for x in tools]
    else:
        if _tool_exists_py("ruff"):
            selected.append("ruff")
        if _tool_exists_py("black"):
            selected.append("black")
        if _tool_exists_py("mypy"):
            selected.append("mypy")
        if _tool_exists_mdformat():
            selected.append("mdformat")

    if not selected:
        return json.dumps(
            {"ok": False, "error": "no supported tools found (ruff/black/mypy)"},
            ensure_ascii=False,
        )

    if mode == "fix":
        msg = _(
            "confirm.msg",
            default=(
                "lint_format(mode=fix) might overwrite files.\n"
                "tools: {tools}\n"
                "targets: {targets}\n"
                "cwd: {cwd}\n\n"
                "Reply with y to proceed, or c to cancel."
            ),
        ).format(
            tools=", ".join(selected),
            targets=", ".join(safe_targets),
            cwd=run_cwd,
        )
        if not _human_confirm(msg):
            return json.dumps(
                {"ok": False, "error": "cancelled by user"}, ensure_ascii=False
            )

    overall_ok = True
    results: list[dict[str, Any]] = []

    for tool in selected:
        tool_safe_targets = tool_targets[tool]

        if tool == "ruff":
            if mode == "check":
                cmd_parts = (
                    ["python", "-m", "ruff", "check"]
                    + tool_safe_targets
                    + sanitized_extra
                )
            else:
                cmd_parts = (
                    ["python", "-m", "ruff", "check", "--fix"]
                    + tool_safe_targets
                    + sanitized_extra
                )
        elif tool == "black":
            if mode == "check":
                cmd_parts = (
                    ["python", "-m", "black", "--check"]
                    + tool_safe_targets
                    + sanitized_extra
                )
            else:
                cmd_parts = ["python", "-m", "black"] + tool_safe_targets + sanitized_extra
        elif tool == "mypy":
            cmd_parts = ["python", "-m", "mypy"] + tool_safe_targets + sanitized_extra
        elif tool == "mdformat":
            if mode == "check":
                cmd_parts = (
                    ["python", "-m", "mdformat", "--check"]
                    + tool_safe_targets
                    + sanitized_extra
                )
            else:
                cmd_parts = (
                    ["python", "-m", "mdformat"] + tool_safe_targets + sanitized_extra
                )
        else:
            results.append({"tool": tool, "ok": False, "error": "unsupported tool"})
            overall_ok = False
            continue

        cmd_str = _quote_cmd_parts(cmd_parts)
        so, se, code, err_tag = _cmd_exec_json(cmd_str, cwd=run_cwd)
        so_t = _truncate(f"{tool} stdout", so)
        se_t = _truncate(f"{tool} stderr", se)

        ok = code == 0
        if not ok:
            overall_ok = False

        r: dict[str, Any] = {
            "tool": tool,
            "command": cmd_str,
            "cwd": run_cwd,
            "returncode": code,
            "ok": ok,
            "stdout": so_t,
            "stderr": se_t,
        }
        if err_tag:
            r["error_tag"] = err_tag
        results.append(r)

    return json.dumps(
        {"ok": overall_ok, "mode": mode, "results": results}, ensure_ascii=False
    )
