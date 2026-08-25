"""Report a concise, read-only status of the current workspace."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
_GIT_COMMAND_TIMEOUT = 5
_MAX_CHANGE_PREVIEW = 100


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "devel",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "workspace_status",
        "description": _(
            "tool.description",
            default="Inspect the current workspace, including Git status and the local runtime.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "workspace status",
                "repository status",
                "git status",
                "development environment",
            ],
        ),
        "x_search_terms_en": [
            "workspace status",
            "repository status",
            "git status",
            "development environment",
        ],
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}


def _run(command: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a fixed read-only command without invoking a shell."""
    try:
        run_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": _GIT_COMMAND_TIMEOUT,
            "check": False,
        }
        if os.name == "nt":
            run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(command, **run_kwargs)
    except FileNotFoundError:
        return 127, "", "git_unavailable"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _parse_git_status(porcelain: str) -> dict[str, Any]:
    branch: str | None = None
    head: str | None = None
    upstream: str | None = None
    ahead: int | None = None
    behind: int | None = None
    changes: list[str] = []

    for line in porcelain.splitlines():
        if line.startswith("# branch.head "):
            value = line.removeprefix("# branch.head ").strip()
            branch = None if value in {"", "(detached)"} else value
        elif line.startswith("# branch.oid "):
            value = line.removeprefix("# branch.oid ").strip()
            head = None if value in {"", "(initial)"} else value[:7]
        elif line.startswith("# branch.upstream "):
            value = line.removeprefix("# branch.upstream ").strip()
            upstream = value or None
        elif line.startswith("# branch.ab "):
            values = line.removeprefix("# branch.ab ").split()
            try:
                if len(values) >= 2:
                    ahead = int(values[0].lstrip("+"))
                    behind = int(values[1].lstrip("-"))
            except ValueError:
                ahead = behind = None
        elif line and not line.startswith("#"):
            changes.append(line)

    staged_count = 0
    unstaged_count = 0
    untracked_count = 0
    conflict_count = 0
    for change in changes:
        if change.startswith("?"):
            untracked_count += 1
            continue
        fields = change.split(" ", 2)
        xy = fields[1] if len(fields) > 1 else ""
        if xy.startswith("U") or len(xy) > 1 and xy[1] == "U":
            conflict_count += 1
        if xy and xy[0] != ".":
            staged_count += 1
        if len(xy) > 1 and xy[1] != ".":
            unstaged_count += 1

    return {
        "branch": branch,
        "head": head,
        "has_commits": head is not None,
        "upstream": upstream,
        "tracking": upstream is not None,
        "ahead": ahead,
        "behind": behind,
        "changed_file_count": len(changes),
        "dirty": bool(changes),
        "staged_count": staged_count,
        "unstaged_count": unstaged_count,
        "untracked_count": untracked_count,
        "conflict_count": conflict_count,
        "has_conflicts": conflict_count > 0,
        "changes": changes[:_MAX_CHANGE_PREVIEW],
        "changes_truncated": len(changes) > _MAX_CHANGE_PREVIEW,
    }


def _git_status(cwd: str) -> dict[str, Any]:
    code, root, stderr = _run(["git", "rev-parse", "--show-toplevel"], cwd)
    if code != 0:
        reason = stderr if stderr == "git_unavailable" else "git_error"
        if "not a git repository" in stderr.lower():
            reason = "not_a_repository"
        elif "timed out" in stderr.lower():
            reason = "timeout"
        return {"is_repository": False, "reason": reason}

    status_code, porcelain, status_error = _run(
        ["git", "--no-optional-locks", "status", "--porcelain=v2", "--branch"], cwd
    )
    if status_code != 0:
        reason = "timeout" if "timed out" in status_error.lower() else "git_error"
        return {"is_repository": True, "root": root, "reason": reason}

    result = _parse_git_status(porcelain)
    return {"is_repository": True, "root": root, **result}


def _safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def run_tool(args: dict[str, Any]) -> str:
    """Return a JSON summary of the active workspace without modifying it."""
    del args
    cwd = os.getcwd()
    git_info = _git_status(cwd)
    marker_root = Path(git_info.get("root") or cwd)
    markers = {
        name: _safe_exists(marker_root / name)
        for name in ("AGENTS.md", "pyproject.toml", "package.json", "requirements.txt")
    }
    return json.dumps(
        {
            "cwd": cwd,
            "git": git_info,
            "runtime": {
                "python_executable": sys.executable,
                "python_version": sys.version.split()[0],
                "virtual_environment": sys.prefix != sys.base_prefix,
            },
            "project_markers": markers,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    print(run_tool({}))
