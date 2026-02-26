"""Safe wrappers for Git operations.

Operational guidelines:
- Avoid interactive operations (PAGER/EDITOR disabled).
- Dangerous operations (force, destructive resets) are blocked unless allow_danger=true is specified.
- Arguments are whitelisted and checked for shell metacharacters.

Notes:
- Not all Git features are available.
- Security and stability are prioritized over completeness.
"""

from __future__ import annotations

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
            default="Run Git commands with safety-first restrictions.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used to run Git commands.\n"
                "\n"
                "Important: args must not include shell metacharacters. For safety, any argument containing the following characters/sequences will be rejected: ; && || | > < `\n"
                "In particular, a git commit -m message containing ';' will be rejected. Use ',' or ':' as separators instead.\n"
                "Examples: NG: Fix X; do Y / OK: Fix X, then do Y\n"
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
                        default="Whether to allow dangerous operations (default false). Example: push --force, reset --hard.",
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


def run_git_command(args: List[str], timeout_sec: int = 30) -> str:
    """Helper to run the actual git command."""
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

        decoded = _decode_bytes(stdout_b)
        decoded_stderr = _decode_bytes(stderr_b)

        output = decoded
        if decoded_stderr.strip():
            output += f"\n[stderr]\n{decoded_stderr}"

        if result.returncode != 0:
            return _(
                "error.command_failed",
                default="[git_ops error] command failed (code={code}):\n{output}",
            ).format(code=result.returncode, output=output.strip())

        return output.strip()

    except FileNotFoundError:
        return _(
            "error.git_not_found",
            default="[git_ops error] git command not found. Please ensure Git is installed.",
        )
    except subprocess.TimeoutExpired:
        return _("error.timeout", default="[git_ops error] command timed out.")
    except Exception as e:
        return _(
            "error.unexpected", default="[git_ops error] unexpected error: {error}"
        ).format(error=e)


def _contains_any(args: List[str], needles: List[str]) -> bool:
    for a in args:
        for n in needles:
            if a == n or a.startswith(n + "="):
                return True
    return False


def _validate_no_shell_metacharacters(args: List[str]) -> None:
    bad = [";", "&&", "||", "|", ">", "<", "`"]
    for a in args:
        for b in bad:
            if b in a:
                raise GitArgsError(
                    _(
                        "error.meta_char",
                        default="Dangerous metacharacter is not allowed in args: {arg}",
                    ).format(arg=a)
                )


def _validate_paths(args: List[str], *, allow_outside_workdir: bool = False) -> None:
    """Validate that non-option arguments are within workdir."""
    workdir = os.getcwd()
    from uagent.utils.paths import get_tmp_patch_dir

    scheck_patch_tmp = str(get_tmp_patch_dir())

    for a in args:
        if a == "--" or a.startswith("-"):
            continue

        abs_path = os.path.abspath(a)
        if abs_path.startswith(workdir + os.sep) or abs_path == workdir:
            continue

        if allow_outside_workdir:
            if (
                abs_path.startswith(scheck_patch_tmp + os.sep)
                or abs_path == scheck_patch_tmp
            ):
                continue

        raise GitArgsError(
            _(
                "error.path_outside_workdir",
                default="Disallowed path (outside workdir): {path}",
            ).format(path=a)
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
                _(
                    "error.option_denied", default="Disallowed option is present: {opt}"
                ).format(opt=opt)
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


def run_tool(args: Dict[str, Any]) -> str:
    """Git operation tool with safety restrictions."""
    command = args.get("command", "")
    cmd_args: List[str] = args.get("args", [])
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
        return _(
            "error.invalid_command",
            default="[git_ops error] unsupported or invalid command: {command}",
        ).format(command=command)

    # --------------------
    # status
    # --------------------
    if command == "status":
        try:
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
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["status"] + cmd_args)

    # --------------------
    # diff
    # --------------------
    if command == "diff":
        try:
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
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["diff"] + cmd_args)

    # --------------------
    # log
    # --------------------
    if command == "log":
        try:
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
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        if not any(a.startswith("-n") or a.startswith("--max-count") for a in cmd_args):
            cmd_args = ["-n", "10"] + cmd_args
        return run_git_command(["log"] + cmd_args)

    # --------------------
    # apply
    # --------------------
    if command == "apply":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--check",
                    "--numstat",
                    "--whitespace",
                    "--ignore-whitespace",
                    "-p",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            _validate_paths(cmd_args, allow_outside_workdir=True)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["apply"] + cmd_args)

    # --------------------
    # add
    # --------------------
    if command == "add":
        if not cmd_args:
            return _(
                "error.add_requires_path",
                default="[git_ops error] git add requires a target path ('.' is allowed).",
            )
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-A",
                    "--all",
                    "-u",
                    "--update",
                    "-N",
                    "--intent-to-add",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["add"] + cmd_args)

    # --------------------
    # commit
    # --------------------
    if command == "commit":
        has_message = any(
            a == "-m"
            or a.startswith("-m")
            or a == "--message"
            or a.startswith("--message")
            for a in cmd_args
        )
        if not has_message:
            return _(
                "error.commit_requires_message",
                default="[git_ops error] Commit message is required. Include ['-m','message'] in args.",
            )
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-m",
                    "--message",
                    "--no-verify",
                    "--amend",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("--amend",),
                deny_prefixes=("--interactive", "-i", "--patch", "-p"),
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        final_args = ["commit"] + cmd_args
        if "--no-edit" not in final_args:
            final_args.append("--no-edit")
        return run_git_command(final_args)

    # --------------------
    # show
    # --------------------
    if command == "show":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--stat",
                    "--name-only",
                    "--name-status",
                    "--oneline",
                    "--",
                    "-U",
                    "--unified",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["show"] + (cmd_args if cmd_args else ["--stat"]))

    # --------------------
    # rev-parse
    # --------------------
    if command == "rev-parse":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--abbrev-ref",
                    "--verify",
                    "--show-toplevel",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["rev-parse"] + cmd_args)

    # --------------------
    # branch
    # --------------------
    if command == "branch":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-a",
                    "--all",
                    "-v",
                    "--verbose",
                    "--show-current",
                    "--",
                    "-d",
                    "-D",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("-D",),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["branch"] + cmd_args)

    # --------------------
    # switch / checkout
    # --------------------
    if command in ("switch", "checkout"):
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-c",
                    "--create",
                    "-C",
                    "--force-create",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("-C", "--force-create"),
                deny_prefixes=("-f", "--force"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command([command] + cmd_args)

    # --------------------
    # remote
    # --------------------
    if command == "remote":
        sub = cmd_args[0] if cmd_args else ""
        if sub in ("add", "remove", "set-url", "rename") and not allow_danger:
            return _(
                "error.remote_change_requires_allow_danger",
                default="[git_ops error] Changing remotes requires allow_danger=true.",
            )
        try:
            _ensure_allowed_flags(
                cmd_args[1:] if cmd_args else [],
                allowed_prefixes=("-v", "--verbose"),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["remote"] + cmd_args)

    # --------------------
    # fetch
    # --------------------
    if command == "fetch":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--all", "--prune", "--tags", "--"),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["fetch"] + cmd_args, timeout_sec=60)

    # --------------------
    # pull
    # --------------------
    if command == "pull":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--ff-only",
                    "--rebase",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("--rebase",),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        final = ["pull"] + cmd_args
        if "--ff-only" not in final and "--rebase" not in final:
            final.append("--ff-only")
        return run_git_command(final, timeout_sec=120)

    # --------------------
    # push
    # --------------------
    if command == "push":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-u",
                    "--set-upstream",
                    "--tags",
                    "--follow-tags",
                    "--",
                    "--force-with-lease",
                    "--force",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("--force", "--force-with-lease"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["push"] + cmd_args, timeout_sec=120)

    # --------------------
    # tag
    # --------------------
    if command == "tag":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-l",
                    "--list",
                    "-n",
                    "-a",
                    "-d",
                    "--delete",
                    "-m",
                    "--message",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("-d", "--delete"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["tag"] + cmd_args)

    # --------------------
    # merge
    # --------------------
    if command == "merge":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--no-ff", "--ff-only", "--abort", "--"),
                allow_danger=allow_danger,
                deny_prefixes=("--strategy", "-s"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        final = ["merge"] + cmd_args
        if "--no-edit" not in final:
            final.append("--no-edit")
        return run_git_command(final, timeout_sec=120)

    # --------------------
    # rebase
    # --------------------
    if command == "rebase":
        if not allow_danger:
            return _(
                "error.rebase_requires_allow_danger",
                default="[git_ops error] rebase is dangerous and requires allow_danger=true.",
            )
        if _contains_any(cmd_args, ["--onto"]):
            return _(
                "error.rebase_onto_forbidden",
                default="[git_ops error] rebase --onto is forbidden because it is error-prone.",
            )
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--abort",
                    "--continue",
                    "--skip",
                    "--",
                    "--rebase-merges",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["rebase"] + cmd_args, timeout_sec=300)

    # --------------------
    # cherry-pick
    # --------------------
    if command == "cherry-pick":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--continue",
                    "--abort",
                    "--skip",
                    "-n",
                    "--no-commit",
                    "-x",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=(
                    "-m",
                    "--mainline",
                ),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["cherry-pick"] + cmd_args, timeout_sec=300)

    # --------------------
    # stash
    # --------------------
    if command == "stash":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "push",
                    "pop",
                    "apply",
                    "list",
                    "show",
                    "-m",
                    "--message",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["stash"] + cmd_args, timeout_sec=120)

    # --------------------
    # reset
    # --------------------
    if command == "reset":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--soft", "--mixed", "--hard", "--"),
                allow_danger=allow_danger,
                dangerous_prefixes=("--hard",),
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["reset"] + cmd_args)

    # --------------------
    # restore
    # --------------------
    if command == "restore":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--staged", "--worktree", "--", "--source"),
                allow_danger=allow_danger,
                dangerous_prefixes=("--source",),
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["restore"] + cmd_args)

    # --------------------
    # clone
    # --------------------
    if command == "clone":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--depth",
                    "--branch",
                    "--single-branch",
                    "--no-tags",
                    "--recurse-submodules",
                    "--shallow-submodules",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        nonopts = [a for a in cmd_args if a != "--" and not a.startswith("-")]
        if len(nonopts) >= 2:
            _validate_paths([nonopts[-1]])
        return run_git_command(["clone"] + cmd_args, timeout_sec=300)

    # --------------------
    # init
    # --------------------
    if command == "init":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--bare", "--initial-branch", "-b", "--"),
                allow_danger=allow_danger,
                dangerous_prefixes=("--bare",),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        _validate_paths(cmd_args)
        return run_git_command(["init"] + cmd_args, timeout_sec=60)

    # --------------------
    # blame
    # --------------------
    if command == "blame":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-L",
                    "--line-porcelain",
                    "--porcelain",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["blame"] + cmd_args, timeout_sec=60)

    # --------------------
    # reflog
    # --------------------
    if command == "reflog":
        if _contains_any(cmd_args, ["expire", "delete"]):
            return _(
                "error.option_denied",
                default="Disallowed option is present: {opt}",
            ).format(opt=cmd_args[0] if cmd_args else "reflog")
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "show",
                    "--date",
                    "--format",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        if not cmd_args:
            cmd_args = ["show"]
        return run_git_command(["reflog"] + cmd_args, timeout_sec=60)

    # --------------------
    # grep
    # --------------------
    if command == "grep":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-n",
                    "--line-number",
                    "-i",
                    "--ignore-case",
                    "-F",
                    "--fixed-strings",
                    "-E",
                    "--extended-regexp",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["grep"] + cmd_args, timeout_sec=60)

    # --------------------
    # ls-files
    # --------------------
    if command == "ls-files":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--cached",
                    "--modified",
                    "--others",
                    "--ignored",
                    "--exclude-standard",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["ls-files"] + cmd_args, timeout_sec=60)

    # --------------------
    # ls-tree
    # --------------------
    if command == "ls-tree":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-r",
                    "--recursive",
                    "-t",
                    "--tree",
                    "--name-only",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["ls-tree"] + cmd_args, timeout_sec=60)

    # --------------------
    # cat-file
    # --------------------
    if command == "cat-file":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-t",
                    "-s",
                    "-p",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"
        return run_git_command(["cat-file"] + cmd_args, timeout_sec=60)

    return _("error.internal_unknown", default="[git_ops error] unknown internal error")
