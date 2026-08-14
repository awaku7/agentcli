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
    code, root, _ = _run(["git", "rev-parse", "--show-toplevel"], cwd)
    if code != 0:
        return {"is_repository": False}

    _, branch, _ = _run(["git", "branch", "--show-current"], cwd)
    _, head, _ = _run(["git", "rev-parse", "--short", "HEAD"], cwd)
    _, porcelain, _ = _run(["git", "status", "--porcelain=v1"], cwd)
    _, upstream, _ = _run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd,
    )
    _, counts, _ = _run(["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"], cwd)

    ahead = behind = None
    if counts:
        try:
            behind, ahead = (int(value) for value in counts.split())
        except ValueError:
            pass
    changes = porcelain.splitlines() if porcelain else []
    return {
        "is_repository": True,
        "root": root,
        "branch": branch or None,
        "head": head or None,
        "upstream": upstream or None,
        "ahead": ahead,
        "behind": behind,
        "changed_file_count": len(changes),
        "changes": changes,
    }


def run_tool(args: dict[str, Any]) -> str:
    """Return a JSON summary of the active workspace without modifying it."""
    del args
    cwd = os.getcwd()
    workspace = Path(cwd)
    markers = {
        name: (workspace / name).exists()
        for name in ("AGENTS.md", "pyproject.toml", "package.json", "requirements.txt")
    }
    return json.dumps(
        {
            "cwd": cwd,
            "git": _git_status(cwd),
            "runtime": {
                "python_executable": sys.executable,
                "python_version": sys.version.split()[0],
                "virtual_environment": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
            },
            "project_markers": markers,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    print(run_tool({}))
