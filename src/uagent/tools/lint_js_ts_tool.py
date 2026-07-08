# tools/lint_js_ts_tool.py
# -*- coding: utf-8 -*-
"""lint_js_ts tool

Purpose:
- Lint JavaScript/TypeScript files using Biome.
- Optionally auto-fix lint issues.

Usage:
- Specify a glob pattern (e.g. "src/**/*.{js,ts,tsx}").
- By default runs in check-only mode.
- Set fix=true to automatically apply safe fixes in-place.
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
STATUS_LABEL = "tool:lint_js_ts"


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "dev",
    "x_parallel_safe": True,
    "function": {
        "name": "lint_js_ts",
        "description": _(
            "tool.description",
            default="Lint JavaScript/TypeScript files using Biome. Reports issues and optionally auto-fixes them.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "javascript",
                "typescript",
                "lint",
                "biome",
                "eslint",
                "code style",
                "static analysis",
                "js lint",
                "ts lint",
                "format",
            ],
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Glob pattern or file path to lint (e.g. 'src/**/*.{js,ts,tsx,jsx}' or 'src/app.ts').",
                    ),
                    "default": "**/*.{js,ts,tsx,jsx}",
                },
                "fix": {
                    "type": "boolean",
                    "description": _(
                        "param.fix.description",
                        default="If true, apply safe auto-fixes instead of just checking.",
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _ensure_npx() -> str | None:
    """Check if npx (Node.js) is available; return path or None."""
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["where", "npx"], capture_output=True, text=True, timeout=5
            )
        else:
            result = subprocess.run(
                ["which", "npx"], capture_output=True, text=True, timeout=5
            )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _ensure_biome_cli() -> bool:
    """Ensure Biome CLI is available via npx. Returns True if usable."""
    npx_path = _ensure_npx()
    if not npx_path:
        return False
    # Verify biome works by asking for version
    try:
        result = subprocess.run(
            [npx_path, "--yes", "@biomejs/biome", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_tool(args: dict[str, Any]) -> str:
    """Run Biome lint on JS/TS files matching the given path pattern."""
    # Check npx availability
    npx_path = _ensure_npx()
    if not npx_path:
        return make_response(
            ok=False,
            message=_msg(
                "err.no_npx",
                "Node.js/npx is not available. Please install Node.js (https://nodejs.org) to use this tool.",
            ),
        )

    path_pattern: str = str(args.get("path") or "**/*.{js,ts,tsx,jsx}")
    fix_mode: bool = bool(args.get("fix", False))

    # Resolve files matching the pattern
    matched_files: list[str] = []
    if os.path.isfile(path_pattern):
        matched_files = [path_pattern]
    elif os.path.isdir(path_pattern):
        matched_files = glob_mod.glob(
            os.path.join(path_pattern, "**", "*.*"), recursive=True
        )
        # Filter by extension
        exts = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
        matched_files = [f for f in matched_files if os.path.splitext(f)[1].lower() in exts]
    else:
        matched_files = glob_mod.glob(path_pattern, recursive=True)

    if not matched_files:
        return make_response(
            ok=True,
            message=_msg(
                "result.no_match",
                "No JS/TS files matched pattern: {pattern}",
                pattern=path_pattern,
            ),
        )

    # Build Biome command
    cmd = [npx_path, "--yes", "@biomejs/biome", "check"]
    if fix_mode:
        cmd.append("--apply")
    cmd.append("--reporter")
    cmd.append("json")

    results: list[str] = []
    failed_count = 0
    ok_count = 0
    _ok_label = _("label.ok", default="OK")
    _fail_label = _("label.fail", default="FAIL")
    _error_label = _("label.error", default="ERROR")
    _no_issues = _("label.no_issues", default="No issues found")

    for filepath in sorted(matched_files):
        try:
            proc = subprocess.run(
                cmd + [filepath],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0:
                ok_count += 1
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
                # Parse Biome JSON output for diagnostics
                diagnostics = _parse_biome_output(proc.stdout)
                if diagnostics:
                    results.append(
                        _msg(
                            "result.fail_with_count",
                            "[{label}] {path}: {count} issue(s)",
                            label=_fail_label,
                            path=filepath,
                            count=diagnostics,
                        )
                    )
                else:
                    results.append(
                        _msg(
                            "result.fail",
                            "[{label}] {path}",
                            label=_fail_label,
                            path=filepath,
                        )
                    )
        except subprocess.TimeoutExpired:
            failed_count += 1
            results.append(
                _msg(
                    "result.timeout",
                    "[{label}] {path}: timeout",
                    label=_error_label,
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
        "lint_js_ts: {total} files, {ok} ok, {failed} failed",
        total=len(matched_files),
        ok=ok_count,
        failed=failed_count,
    )

    if failed_count == 0:
        return make_response(ok=True, message=summary)

    # Show details
    detail_lines = results[:50]
    if len(results) > 50:
        detail_lines.append(
            _msg("result.more", "... and {count} more", count=len(results) - 50)
        )
    detail = "\n".join(detail_lines)

    return make_response(ok=True, message=summary, data={"detail": detail})


def _parse_biome_output(output: str) -> int:
    """Parse Biome JSON output and return total diagnostic count."""
    import json as json_mod

    try:
        data = json_mod.loads(output)
        if isinstance(data, dict):
            summary = data.get("summary", {})
            return int(summary.get("diagnostics", 0))
        if isinstance(data, list):
            total = 0
            for item in data:
                s = item.get("summary", {})
                total += int(s.get("diagnostics", 0))
            return total
    except Exception:
        pass
    return 0
