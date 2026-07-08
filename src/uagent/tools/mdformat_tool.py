# tools/mdformat_tool.py
# -*- coding: utf-8 -*-
"""mdformat_check tool

Purpose:
- Check Markdown file formatting using mdformat.
- Optionally auto-fix formatting issues.

Usage:
- Specify a glob pattern (e.g. "docs/**/*.md") or a single file path.
- By default runs in check-only mode (dry-run).
- Set fix=true to automatically format files in-place.
"""

from __future__ import annotations

import glob as glob_mod
import os
import subprocess
import sys
from typing import Any

from .i18n_helper import make_tool_translator
from .response_util import make_response

_ = make_tool_translator(__file__)


def _msg(key: str, default: str, **kwargs: Any) -> str:
    return _(key, default=default).format(**kwargs)


BUSY_LABEL = True
STATUS_LABEL = "tool:mdformat_check"


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "dev",
    "x_parallel_safe": True,
    "function": {
        "name": "mdformat_check",
        "description": _(
            "tool.description",
            default="Check Markdown file formatting with mdformat. Reports files that need formatting fixes. Optionally auto-fix.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["markdown", "format", "lint", "mdformat", "md", "style"],
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Glob pattern or file path to check (e.g. 'docs/**/*.md' or 'README.md').",
                    ),
                    "default": "**/*.md",
                },
                "fix": {
                    "type": "boolean",
                    "description": _(
                        "param.fix.description",
                        default="If true, auto-fix formatting issues instead of just checking.",
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _ensure_mdformat() -> None:
    """Auto-install mdformat and mdformat-frontmatter if missing."""
    from .._pip_auto import install_with_status as _install

    # Ensure mdformat itself
    try:
        import mdformat  # noqa: F401
    except ImportError:
        _install(
            "mdformat",
            display_name=_("pkg.mdformat", default="mdformat (Markdown formatter)"),
        )

    # Ensure YAML front matter plugin
    try:
        import mdformat_frontmatter  # noqa: F401
    except ImportError:
        _install(
            "mdformat-frontmatter",
            display_name=_(
                "pkg.mdformat_frontmatter",
                default="mdformat YAML front matter plugin",
            ),
        )


def run(args: dict[str, Any]) -> str:
    """Run mdformat on Markdown files matching the given path pattern."""
    _ensure_mdformat()
    path_pattern: str = str(args.get("path") or "**/*.md")
    fix_mode: bool = bool(args.get("fix", False))

    # Resolve files matching the pattern
    matched_files: list[str] = []
    if os.path.isfile(path_pattern):
        matched_files = [path_pattern]
    elif os.path.isdir(path_pattern):
        matched_files = glob_mod.glob(
            os.path.join(path_pattern, "**", "*.md"), recursive=True
        )
    else:
        matched_files = glob_mod.glob(path_pattern, recursive=True)

    # Markdown files directory-relative:
    if not matched_files:
        return make_response(
            ok=True,
            message=_msg(
                "result.no_match",
                "No Markdown files matched pattern: {pattern}",
                pattern=path_pattern,
            ),
        )

    # Build mdformat command
    cmd = [sys.executable, "-m", "mdformat"]
    if not fix_mode:
        cmd.append("--check")

    results: list[str] = []
    failed_count = 0
    ok_count = 0
    _ok_label = _("label.ok", default="OK")
    _fail_label = _("label.fail", default="FAIL")
    _timeout_label = _("label.timeout", default="TIMEOUT")
    _error_label = _("label.error", default="ERROR")

    for filepath in sorted(matched_files):
        try:
            proc = subprocess.run(
                cmd + [filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                ok_count += 1
                if fix_mode:
                    results.append(
                        _msg(
                            "result.ok_formatted",
                            "[{label}] formatted: {path}",
                            label=_ok_label,
                            path=filepath,
                        )
                    )
                else:
                    results.append(
                        _msg(
                            "result.ok",
                            "[{label}] {path}",
                            label=_ok_label,
                            path=filepath,
                        )
                    )
            else:
                failed_count += 1
                stderr_lines = [
                    l for l in proc.stderr.splitlines() if l.strip()
                ] or proc.stdout.splitlines()
                detail = (
                    stderr_lines[0].strip()
                    if stderr_lines
                    else _msg("result.fallback_detail", "formatting issue")
                )
                results.append(
                    _msg(
                        "result.fail",
                        "[{label}] {path}: {detail}",
                        label=_fail_label,
                        path=filepath,
                        detail=detail,
                    )
                )
        except subprocess.TimeoutExpired:
            failed_count += 1
            results.append(
                _msg(
                    "result.timeout",
                    "[{label}] {path}",
                    label=_timeout_label,
                    path=filepath,
                )
            )
        except Exception as e:
            failed_count += 1
            results.append(
                _msg(
                    "result.error",
                    "[{label}] {path}: {e}",
                    label=_error_label,
                    path=filepath,
                    e=e,
                )
            )

    summary = _msg(
        "result.summary",
        "mdformat_check: {total} files, {ok} ok, {failed} failed",
        total=len(matched_files),
        ok=ok_count,
        failed=failed_count,
    )

    if failed_count == 0:
        return make_response(ok=True, message=summary)

    # Show details on failure
    detail_lines = results[:50]
    if len(results) > 50:
        detail_lines.append(
            _msg(
                "result.more",
                "... and {count} more",
                count=len(results) - 50,
            )
        )
    detail = "\n".join(detail_lines)

    return make_response(
        ok=True,
        message=summary,
        data={"detail": detail},
    )
