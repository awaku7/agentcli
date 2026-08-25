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
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _git_status(cwd: str) -> dict[str, Any]:
    code, root, stderr = _run(["git", "rev-parse", "--show-toplevel"], cwd)
    if code != 0:
        err = stderr.lower()
        if "not a git repository" in err:
            reason = "not_a_repository"
        elif "not found" in err or "not recognized" in err:
            reason = "git_unavailable"
        elif "timed out" in err:
            reason = "timeout"
        else:
            reason = "git_error"
        return {"is_repository": False, "reason": reason}

    _, branch, _ = _run(["git", "branch", "--show-current"], cwd)
    head_code, head, _ = _run(["git", "rev-parse", "--short", "HEAD"], cwd)
    _, porcelain, _ = _run(["git", "status", "--porcelain=v1"], cwd)
    _, upstream, _ = _run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd,
    )
    _, counts, _ = _run(
        ["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"], cwd
    )

    ahead = behind = None
    if counts:
        try:
            behind, ahead = (int(value) for value in counts.split())
        except ValueError:
            pass
    changes = porcelain.splitlines() if porcelain else []
    staged_count = unstaged_count = untracked_count = conflict_count = 0
    for change in changes:
        if change.startswith("??"):
            untracked_count += 1
            continue
        if len(change) >= 2:
            index_status, worktree_status = change[0], change[1]
            if index_status != " ":
                staged_count += 1
            if worktree_status != " ":
                unstaged_count += 1
            if index_status == "U" or worktree_status == "U":
                conflict_count += 1
    return {
        "is_repository": True,
        "root": root,
        "branch": branch or None,
        "head": head or None,
        "has_commits": head_code == 0,
        "upstream": upstream or None,
        "tracking": bool(upstream),
        "ahead": ahead,
        "behind": behind,
        "changed_file_count": len(changes),
        "staged_count": staged_count,
        "unstaged_count": unstaged_count,
        "untracked_count": untracked_count,
        "conflict_count": conflict_count,
        "has_conflicts": conflict_count > 0,
        "changes": changes,
    }


def run_tool(args: dict[str, Any]) -> str:
    """Return a JSON summary of the active workspace without modifying it."""
    del args
    cwd = os.getcwd()
    git_info = _git_status(cwd)
    marker_root = Path(git_info.get("root") or cwd)
    markers = {
        name: (marker_root / name).exists()
        for name in ("AGENTS.md", "pyproject.toml", "package.json", "requirements.txt")
    }
    return json.dumps(
        {
            "cwd": cwd,
            "git": git_info,
            "runtime": {
                "python_executable": sys.executable,
                "python_version": sys.version.split()[0],
                "virtual_environment": sys.prefix
                != getattr(sys, "base_prefix", sys.prefix),
            },
            "project_markers": markers,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    print(run_tool({}))
