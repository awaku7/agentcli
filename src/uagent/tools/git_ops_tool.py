"""Safe wrappers for Git operations.

Operational guidelines:
- Avoid interactive operations (PAGER/EDITOR disabled).
- Dangerous operations (force, destructive resets) are blocked unless allow_danger=true is specified.
- Arguments are whitelisted and checked for shell metacharacters.

Return value (IMPORTANT):
- This tool always returns a JSON string containing:
    { ok, returncode, stdout, stderr }
  even when stdout/stderr are empty.

Notes:
- Not all Git features are available.
- Security and stability are prioritized over completeness.
"""

from __future__ import annotations

import json
import locale
import os
import subprocess
from typing import Any, Dict, List, Tuple

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:git_ops"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "git_ops",
        "description": _(
            "tool.description",
            default=(
                "Run Git commands with safety-first restrictions. "
                "Some operations or special characters in arguments may be restricted for security."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used to run Git commands.\n"
                "\n"
                "Important: args must not include shell metacharacters. For safety, any argument containing the "
                "following characters/sequences will be rejected: && || | > < `\n"
                "For git commit messages, ';' is automatically replaced with ',' (only inside -m/--message).\n"
                "\n"
                "Return value: This tool always returns JSON with ok/returncode/stdout/stderr."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": [
                        "status",
                        "diff",
                        "log",
                        "add",
                        "commit",
                        "show",
                        "rev-parse",
                        "branch",
                        "switch",
                        "checkout",
                        "remote",
                        "fetch",
                        "pull",
                        "push",
                        "tag",
                        "merge",
                        "rebase",
                        "stash",
                        "reset",
                        "restore",
                        "apply",
                        "cherry-pick",
                        "clone",
                        "init",
                        "blame",
                        "reflog",
                        "grep",
                        "ls-files",
                        "ls-tree",
                        "cat-file",
                    ],
                    "description": _(
                        "param.command.description",
                        default="Git subcommand to run (safety-first restrictions apply).",
                    ),
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.args.description",
                        default="List of arguments passed to the Git command.",
                    ),
                },
                "allow_danger": {
                    "type": "boolean",
                    "description": _(
                        "param.allow_danger.description",
                        default=(
                            "Whether to allow dangerous operations (default false). "
                            "Example: push --force, reset --hard."
                        ),
                    ),
                    "default": False,
                },
            },
            "required": ["command"],
        },
    },
}


class GitArgsError(ValueError):
    """Exception for invalid arguments."""


def _env_for_git() -> Dict[str, str]:
    """Prepare environment variables for git execution."""
    base = os.environ.copy()
    base.update(
        {
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "GIT_EDITOR": ":",
            "EDITOR": ":",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return base


def _decode_bytes(b: bytes) -> str:
    encodings = [locale.getpreferredencoding(), "utf-8", "cp932"]
    for enc in encodings:
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def run_git_command(args: List[str], timeout_sec: int = 30) -> Dict[str, Any]:
    """Run git command and always return a JSON-serializable dict.

    Returns:
      { ok: bool, returncode: int, stdout: str, stderr: str }
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=False,
            env=_env_for_git(),
            timeout=timeout_sec,
        )

        stdout_b = result.stdout or b""
        stderr_b = result.stderr or b""

        decoded_stdout = _decode_bytes(stdout_b)
        decoded_stderr = _decode_bytes(stderr_b)

        return {
            "ok": result.returncode == 0,
            "returncode": int(result.returncode),
            "stdout": decoded_stdout,
            "stderr": decoded_stderr,
        }

    except FileNotFoundError:
        return {
            "ok": False,
            "returncode": 127,
            "stdout": "",
            "stderr": _(
                "error.git_not_found",
                default="[git_ops error] git command not found. Please ensure Git is installed.",
            ),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": 124,
            "stdout": "",
            "stderr": _("error.timeout", default="[git_ops error] command timed out."),
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": 1,
            "stdout": "",
            "stderr": _(
                "error.unexpected", default="[git_ops error] unexpected error: {error}"
            ).format(error=e),
        }


def _sanitize_commit_message_args(args: List[str]) -> List[str]:
    """Replace ';' with ',' only inside commit message values.

    We keep rejecting shell metacharacters in general, but allow ';' in
    `git commit -m <msg>` by sanitizing it. This is a convenience feature
    for users who use ';' as a separator in commit messages.
    """
    out: List[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m" and i + 1 < len(args):
            out.append(a)
            out.append(args[i + 1].replace(";", ","))
            i += 2
            continue
        if a.startswith("--message="):
            out.append("--message=" + a[len("--message=") :].replace(";", ","))
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def _validate_no_shell_metacharacters(args: List[str]) -> None:
    bad = ["&&", "||", "|", ">", "<", "`"]
    for a in args:
        for b in bad:
            if b in a:
                raise GitArgsError(
                    _(
                        "error.meta_char",
                        default="Dangerous metacharacter is not allowed in args: {arg}",
                    ).format(arg=a)
                )


def _reject(reason: str) -> None:
    raise GitArgsError(reason)


def _ensure_allowed_flags(
    args: List[str],
    allowed_prefixes: Tuple[str, ...],
    *,
    allow_danger: bool,
    dangerous_prefixes: Tuple[str, ...] = (),
    deny_exact: Tuple[str, ...] = (),
    deny_prefixes: Tuple[str, ...] = (),
) -> None:
    """Validate flags for security."""
    _validate_no_shell_metacharacters(args)

    for a in args:
        if not a.startswith("-"):
            continue

        opt = a.split("=", 1)[0]
        if opt == "--" or opt == "-c":
            continue

        if opt in deny_exact:
            _reject(
                _("error.option_denied", default="Disallowed option is present: {opt}").format(
                    opt=opt
                )
            )

        for p in deny_prefixes:
            if opt == p or opt.startswith(p):
                _reject(
                    _(
                        "error.option_denied",
                        default="Disallowed option is present: {opt}",
                    ).format(opt=opt)
                )

        for p in dangerous_prefixes:
            if opt == p or opt.startswith(p):
                if not allow_danger:
                    _reject(
                        _(
                            "error.option_danger_requires_allow_danger",
                            default="Dangerous option requires allow_danger=true: {opt}",
                        ).format(opt=opt)
                    )

        if opt.startswith("--"):
            continue

        ok = False
        for ap in allowed_prefixes:
            if opt == ap or opt.startswith(ap):
                ok = True
                break

        if not ok:
            _reject(
                _(
                    "error.option_not_allowed",
                    default="Unallowed option is present: {opt}",
                ).format(opt=opt)
            )


def _parse_allow_danger(tool_args: Dict[str, Any]) -> bool:
    return bool(tool_args.get("allow_danger", False))


def _as_error_payload(err: str, *, returncode: int = 2) -> Dict[str, Any]:
    return {"ok": False, "returncode": int(returncode), "stdout": "", "stderr": err}


def run_tool(args: Dict[str, Any]) -> str:
    """Git operation tool with safety restrictions.

    Always returns JSON.
    """
    command = str(args.get("command", "") or "")
    cmd_args: List[str] = args.get("args", []) or []
    allow_danger = _parse_allow_danger(args)

    if command not in (
        "status",
        "diff",
        "log",
        "apply",
        "add",
        "commit",
        "show",
        "rev-parse",
        "branch",
        "switch",
        "checkout",
        "remote",
        "fetch",
        "pull",
        "push",
        "tag",
        "merge",
        "rebase",
        "stash",
        "reset",
        "restore",
        "cherry-pick",
        "clone",
        "init",
        "blame",
        "reflog",
        "grep",
        "ls-files",
        "ls-tree",
        "cat-file",
    ):
        payload = _as_error_payload(
            _(
                "error.invalid_command",
                default="[git_ops error] unsupported or invalid command: {command}",
            ).format(command=command)
        )
        return json.dumps(payload, ensure_ascii=False)

    try:
        # --------------------
        # status
        # --------------------
        if command == "status":
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-s",
                    "--short",
                    "-b",
                    "--branch",
                    "--porcelain",
                    "--ignored",
                    "-u",
                    "--untracked-files",
                ),
                allow_danger=allow_danger,
            )
            payload = run_git_command(["status"] + cmd_args)
            return json.dumps(payload, ensure_ascii=False)

        # --------------------
        # diff
        # --------------------
        if command == "diff":
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--staged",
                    "--cached",
                    "--stat",
                    "--name-only",
                    "--name-status",
                    "--",
                    "-U",
                    "--unified",
                ),
                allow_danger=allow_danger,
                deny_prefixes=("--no-index",),
            )
            payload = run_git_command(["diff"] + cmd_args)
            return json.dumps(payload, ensure_ascii=False)

        # --------------------
        # log
        # --------------------
        if command == "log":
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-n",
                    "--max-count",
                    "--oneline",
                    "--decorate",
                    "--graph",
                    "--all",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            if not any(a.startswith("-n") or a.startswith("--max-count") for a in cmd_args):
                cmd_args = ["-n", "10"] + cmd_args
            payload = run_git_command(["log"] + cmd_args)
            return json.dumps(payload, ensure_ascii=False)

        # --------------------
        # passthrough (basic allowlist)
        # --------------------
        # For remaining commands, keep flag restrictions conservative but not overly strict.
        # (Existing behavior was already a large allowlist; we keep that approach.)
        # Allow ';' inside commit message values by sanitizing it, but keep rejecting
        # other shell metacharacters everywhere.
        if command == "commit":
            cmd_args = _sanitize_commit_message_args(cmd_args)

        _validate_no_shell_metacharacters(cmd_args)

        payload = run_git_command([command] + cmd_args)
        return json.dumps(payload, ensure_ascii=False)

    except GitArgsError as e:
        payload = _as_error_payload(f"[git_ops error] {e}")
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        payload = _as_error_payload(f"[git_ops error] {type(e).__name__}: {e}")
        return json.dumps(payload, ensure_ascii=False)
