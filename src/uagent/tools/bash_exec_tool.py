from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

from .i18n_helper import make_tool_translator
from .safe_exec_ops import confirm_if_needed, decide_cmd_exec

_ = make_tool_translator(__file__)

BUSY_LABEL = True

_TOOL_AVAILABLE = os.name != "nt" and bool(shutil.which("bash"))

LOAD_DISABLED_REASON = _(
    "err.unavailable",
    default="This tool is available on Unix-like systems with bash installed.",
)

_COMMAND_SEPARATORS = {";", "&&", "||", "|", "&"}
_REDIRECTION_OPERATORS = {"<", ">", "<<", ">>"}
_INDIRECT_EXECUTORS = {
    "bash",
    "builtin",
    "chroot",
    "command",
    "doas",
    "env",
    "exec",
    "find",
    "nice",
    "nohup",
    "runuser",
    "setsid",
    "sh",
    "stdbuf",
    "su",
    "sudo",
    "time",
    "timeout",
    "xargs",
}
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.DOTALL)
_QUOTED_PUNCTUATION_MASK = str.maketrans(
    {character: chr(0xE000 + index) for index, character in enumerate(";&|<>()")}
)
_QUOTED_PUNCTUATION_RESTORE = {
    value: key for key, value in _QUOTED_PUNCTUATION_MASK.items()
}

TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "type": "function",
    "tool_genre": "exec",
    # Shell execution remains opt-in even when the backend is available.
    "tool_level": 1 if _TOOL_AVAILABLE else -1,
    "function": {
        "name": "bash_exec",
        "description": _(
            "tool.description",
            default=(
                "As a last resort, execute a bash command. Use only when no other appropriate tool is available."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "bash_exec",
                "bash exec",
                "bash",
                "shell command",
                "execute shell",
            ],
        ),
        "x_search_terms_en": [
            "bash_exec",
            "bash exec",
            "bash",
            "shell command",
            "execute shell",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="Command string passed to bash -lc.",
                    ),
                }
            },
            "required": ["command"],
        },
    },
}


def _mask_quoted_shell_punctuation(command: str) -> str:
    """Hide quoted operator characters from ``shlex`` punctuation splitting."""
    output: list[str] = []
    quote: str | None = None
    escaped = False
    for character in command:
        if escaped:
            output.append(character.translate(_QUOTED_PUNCTUATION_MASK))
            escaped = False
            continue
        if character == "\\" and quote != "'":
            output.append(character)
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            output.append(character)
            continue
        output.append(
            character.translate(_QUOTED_PUNCTUATION_MASK) if quote else character
        )
    return "".join(output)


def _has_active_shell_substitution(command: str) -> bool:
    """Detect substitutions that are active outside single-quoted literals."""
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(command):
        character = command[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if character == "\\" and quote != "'":
            escaped = True
            index += 1
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            index += 1
            continue
        if quote != "'":
            if character == "`":
                return True
            if command.startswith(("$(", "<(", ">("), index):
                return True
        index += 1
    return False


def _allowlisted_executables(command: str) -> tuple[list[str], str | None]:
    """Return every command head in a conservatively supported shell command.

    The non-interactive allowlist is a guard around ``bash -lc``, not a full
    shell sandbox. Support ordinary chaining and pipelines, but reject shell
    constructs that can hide another executable from command-head inspection.
    """
    if "\n" in command or "\r" in command:
        return [], "multiline shell commands are not supported in allowlist mode"
    if _has_active_shell_substitution(command):
        return [], "shell substitution is not supported in allowlist mode"

    try:
        lexer = shlex.shlex(
            _mask_quoted_shell_punctuation(command),
            posix=True,
            punctuation_chars=";&|<>()",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = [token.translate(_QUOTED_PUNCTUATION_RESTORE) for token in lexer]
    except ValueError as exc:
        return [], f"command could not be parsed safely: {exc}"

    if not tokens:
        return [], "empty command"

    executables: list[str] = []
    expect_command = True
    skip_redirection_target = False
    for token in tokens:
        if token in {"(", ")"}:
            return [], "subshell grouping is not supported in allowlist mode"
        if token in _COMMAND_SEPARATORS:
            if expect_command:
                return [], f"unexpected shell operator '{token}'"
            expect_command = True
            skip_redirection_target = False
            continue
        if token in _REDIRECTION_OPERATORS:
            skip_redirection_target = True
            continue
        if skip_redirection_target:
            skip_redirection_target = False
            continue
        if not expect_command:
            continue
        if token == "!" or _ASSIGNMENT_RE.match(token):
            continue

        executable = os.path.basename(token).strip().lower()
        if not executable:
            return [], "empty executable name"
        if executable in _INDIRECT_EXECUTORS:
            return [], (
                f"indirect executor '{executable}' is not supported in "
                "allowlist mode"
            )
        executables.append(executable)
        expect_command = False

    if skip_redirection_target:
        return [], "redirection target is missing"
    if expect_command:
        return [], "command is missing after a shell operator"
    return executables, None


def _scope_tokens(command: str) -> tuple[list[str], str | None]:
    """Tokenize command arguments for optional path/network scope checks."""
    try:
        lexer = shlex.shlex(
            _mask_quoted_shell_punctuation(command),
            posix=True,
            punctuation_chars=";&|<>()",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        return [
            token.translate(_QUOTED_PUNCTUATION_RESTORE) for token in lexer
        ], None
    except ValueError as exc:
        return [], f"command could not be parsed safely: {exc}"


def _split_scope_values(name: str) -> list[str]:
    return [
        os.path.abspath(os.path.expanduser(item.strip()))
        for item in os.environ.get(name, "").split(os.pathsep)
        if item.strip()
    ]


def _path_scope_reason(command: str) -> str | None:
    roots = _split_scope_values("UAGENT_BASH_EXEC_ALLOWED_PATHS")
    if not roots:
        return None
    tokens, parse_error = _scope_tokens(command)
    if parse_error:
        return parse_error
    operators = _COMMAND_SEPARATORS | _REDIRECTION_OPERATORS | {"(", ")"}
    for token in tokens:
        if not token or token in operators or token.startswith("-"):
            continue
        if "://" in token or _ASSIGNMENT_RE.match(token):
            continue
        looks_like_path = (
            token.startswith(("/", "./", "../", "~/"))
            or bool(re.match(r"^[A-Za-z]:[\\/]", token))
            or os.path.exists(os.path.expanduser(token))
        )
        if not looks_like_path:
            continue
        candidate = os.path.abspath(os.path.expanduser(token))
        try:
            in_scope = any(
                os.path.commonpath((candidate, root)) == root for root in roots
            )
        except ValueError:
            in_scope = False
        if not in_scope:
            return (
                f"path '{token}' is outside UAGENT_BASH_EXEC_ALLOWED_PATHS "
                f"({os.pathsep.join(roots)})"
            )
    return None


def _network_scope_reason(command: str) -> str | None:
    allowed = {
        item.strip().lower().rstrip(".")
        for item in os.environ.get("UAGENT_BASH_EXEC_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    if not allowed:
        return None
    tokens, parse_error = _scope_tokens(command)
    if parse_error:
        return parse_error
    for token in tokens:
        parsed = urlparse(token)
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            continue
        if not any(host == item or host.endswith("." + item) for item in allowed):
            return (
                f"host '{host}' is outside UAGENT_BASH_EXEC_ALLOWED_HOSTS "
                f"({','.join(sorted(allowed))})"
            )
    return None


def _policy_block_reason(command: str) -> str | None:
    policy = os.environ.get("UAGENT_BASH_EXEC_POLICY", "").strip().lower()
    if policy in {"deny", "off", "disabled", "0", "false", "no"}:
        return "disabled by UAGENT_BASH_EXEC_POLICY"

    non_interactive = os.environ.get("UAGENT_NON_INTERACTIVE", "").strip().lower()
    allow = os.environ.get("UAGENT_ALLOW_BASH_EXEC", "").strip().lower()
    is_non_interactive = non_interactive in {"1", "true", "yes", "on"}
    if is_non_interactive and allow not in {"1", "true", "yes", "on"}:
        return (
            "disabled in non-interactive mode; set UAGENT_ALLOW_BASH_EXEC=1 "
            "for explicit opt-in"
        )

    raw_allowlist = os.environ.get("UAGENT_BASH_EXEC_ALLOWLIST", "")
    allowlist = {
        item.strip().lower() for item in raw_allowlist.split(",") if item.strip()
    }
    require_allowlist = os.environ.get(
        "UAGENT_BASH_EXEC_REQUIRE_ALLOWLIST", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if is_non_interactive and not allowlist:
        require_allowlist = True
    if not allowlist and require_allowlist:
        return (
            "no bash command allowlist configured; set "
            "UAGENT_BASH_EXEC_ALLOWLIST=command1,command2"
        )

    if allowlist:
        executables, parse_error = _allowlisted_executables(command)
        if parse_error:
            return parse_error
        blocked = [name for name in executables if name not in allowlist]
        if blocked:
            return (
                f"command '{blocked[0]}' is not in UAGENT_BASH_EXEC_ALLOWLIST "
                f"({','.join(sorted(allowlist))})"
            )
    path_reason = _path_scope_reason(command)
    if path_reason:
        return path_reason
    network_reason = _network_scope_reason(command)
    if network_reason:
        return network_reason
    return None


def _timeout_seconds() -> float:
    raw = os.environ.get("UAGENT_BASH_EXEC_TIMEOUT_SEC", "120").strip()
    try:
        return min(900.0, max(1.0, float(raw)))
    except ValueError:
        return 120.0


def run_tool(args: dict[str, Any]) -> str:
    command = str(args.get("command", "") or "")
    if not command:
        raise ValueError("command is required")

    policy_reason = _policy_block_reason(command)
    if policy_reason:
        return _(
            "err.blocked",
            default="[bash_exec blocked] %(reason)s",
        ) % {"reason": policy_reason}

    if not _TOOL_AVAILABLE:
        return _(
            "err.unavailable",
            default="This tool is available on Unix-like systems with bash installed.",
        )

    decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=True)
    if not decision.allowed:
        return _(
            "err.blocked",
            default="[bash_exec blocked] %(reason)s",
        ) % {"reason": decision.reason}

    confirm_err = confirm_if_needed(decision)
    if confirm_err is not None:
        return confirm_err

    try:
        p = subprocess.run(
            ["bash", "-lc", command],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
        )
    except subprocess.TimeoutExpired:
        return _(
            "err.timeout",
            default="[bash_exec timeout] command exceeded the configured timeout: {seconds}s",
        ).format(seconds=_timeout_seconds())
    except Exception as e:
        return _(
            "err.exception",
            default="[bash_exec error] %(type)s: %(message)s",
        ) % {"type": type(e).__name__, "message": str(e)}

    out = p.stdout or ""
    err = p.stderr or ""

    if p.returncode != 0:
        return _(
            "err.returncode",
            default="[bash_exec]\n(returncode=%(code)s)\nSTDOUT:\n%(stdout)s\nSTDERR:\n%(stderr)s",
        ) % {
            "code": p.returncode,
            "stdout": out,
            "stderr": err,
        }

    return "[bash_exec]\n" + out
