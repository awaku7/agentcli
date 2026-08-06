# tools/mdformat_tool.py
# -*- coding: utf-8 -*-
"""mdformat_check tool

Purpose:
- Check Markdown file formatting using mdformat.
- Optionally auto-fix formatting issues.
- Preserve and format YAML front matter, including Agent Skill files.

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

from .agent_skills_shared import (
    load_skill_frontmatter_only,
    skill_md_path,
    validate_skill_frontmatter,
)
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
                "validate_skills": {
                    "type": "boolean",
                    "description": _(
                        "param.validate_skills.description",
                        default="Validate SKILL.md files against the Agent Skills frontmatter specification.",
                    ),
                    "default": True,
                },
                "strict_skills": {
                    "type": "boolean",
                    "description": _(
                        "param.strict_skills.description",
                        default="Treat Agent Skills validation warnings as errors.",
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _ensure_mdformat() -> bool:
    """Auto-install mdformat and return whether front matter support is ready."""
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

    try:
        import mdformat_frontmatter  # noqa: F401
    except ImportError:
        return False
    return True


def _has_yaml_frontmatter(filepath: str) -> bool:
    """Return whether a Markdown file starts with YAML front matter."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as handle:
            return handle.readline().strip() == "---"
    except (OSError, UnicodeError):
        return False


def _document_type(filepath: str) -> str:
    """Classify Markdown for explicit LLM-facing tool output."""
    if os.path.basename(filepath) == "SKILL.md":
        return "agent_skill" if _has_yaml_frontmatter(filepath) else "agent_skill_candidate"
    return "markdown_with_frontmatter" if _has_yaml_frontmatter(filepath) else "markdown"


def _validate_skill_file(filepath: str, *, strict: bool) -> dict[str, Any]:
    """Validate one ``SKILL.md`` using the shared Agent Skills validator."""
    skill_dir = os.path.dirname(filepath)
    try:
        if skill_md_path(skill_dir) != filepath:
            return {"ok": False, "errors": ["SKILL.md path mismatch"], "warnings": []}
        frontmatter = load_skill_frontmatter_only(skill_dir)
        ok, errors, warnings = validate_skill_frontmatter(
            skill_dir, frontmatter, strict=strict
        )
        return {"ok": ok, "errors": errors, "warnings": warnings}
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"Failed to validate Agent Skill: {exc!r}"],
            "warnings": [],
        }


def run_tool(args: dict[str, Any]) -> str:
    """Run mdformat, preserving YAML front matter when present."""
    frontmatter_ready = _ensure_mdformat()
    path_pattern: str = str(args.get("path") or "**/*.md")
    fix_mode: bool = bool(args.get("fix", False))
    validate_skills: bool = bool(args.get("validate_skills", True))
    strict_skills: bool = bool(args.get("strict_skills", False))

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
    # mdformat discovers installed extension plugins through entry points.
    # The front-matter plugin is ensured above so SKILL.md YAML is preserved.
    cmd = [sys.executable, "-m", "mdformat"]
    if not fix_mode:
        cmd.append("--check")

    results: list[str] = []
    failed_count = 0
    ok_count = 0
    type_counts: dict[str, int] = {}
    skill_invalid_count = 0
    _ok_label = _("label.ok", default="OK")
    _fail_label = _("label.fail", default="FAIL")
    _timeout_label = _("label.timeout", default="TIMEOUT")
    _error_label = _("label.error", default="ERROR")

    for filepath in sorted(matched_files):
        doc_type = _document_type(filepath)
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        try:
            if _has_yaml_frontmatter(filepath) and not frontmatter_ready:
                failed_count += 1
                results.append(
                    _msg(
                        "result.frontmatter_missing",
                        "[{label}] type={doc_type} {path}: YAML front matter support is unavailable; install mdformat-frontmatter",
                        label=_error_label,
                        doc_type=doc_type,
                        path=filepath,
                    )
                )
                continue
            proc = subprocess.run(
                cmd + [filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                skill_result = None
                if validate_skills and os.path.basename(filepath) == "SKILL.md":
                    skill_result = _validate_skill_file(
                        filepath, strict=strict_skills
                    )
                    if not skill_result["ok"]:
                        failed_count += 1
                        skill_invalid_count += 1
                        results.append(
                            _msg(
                                "result.skill_invalid",
                                "[{label}] type={doc_type} {path}: Agent Skills validation failed: {detail}",
                                label=_fail_label,
                                doc_type=doc_type,
                                path=filepath,
                                detail="; ".join(skill_result["errors"]),
                            )
                        )
                        continue

                ok_count += 1
                if fix_mode:
                    results.append(
                        _msg(
                            "result.ok_formatted",
                            "[{label}] type={doc_type} formatted: {path}",
                            label=_ok_label,
                            doc_type=doc_type,
                            path=filepath,
                        )
                    )
                else:
                    results.append(
                        _msg(
                            "result.ok",
                            "[{label}] type={doc_type} {path}",
                            label=_ok_label,
                            doc_type=doc_type,
                            path=filepath,
                        )
                    )
            else:
                failed_count += 1
                stderr_lines = [
                    line for line in proc.stderr.splitlines() if line.strip()
                ] or proc.stdout.splitlines()
                detail = (
                    stderr_lines[0].strip()
                    if stderr_lines
                    else _msg("result.fallback_detail", "formatting issue")
                )
                results.append(
                    _msg(
                        "result.fail",
                        "[{label}] type={doc_type} {path}: {detail}",
                        label=_fail_label,
                        doc_type=doc_type,
                        path=filepath,
                        detail=detail,
                    )
                )
        except subprocess.TimeoutExpired:
            failed_count += 1
            results.append(
                _msg(
                    "result.timeout",
                    "[{label}] type={doc_type} {path}",
                    label=_timeout_label,
                    doc_type=doc_type,
                    path=filepath,
                )
            )
        except Exception as e:
            failed_count += 1
            results.append(
                _msg(
                    "result.error",
                    "[{label}] type={doc_type} {path}: {e}",
                    label=_error_label,
                    doc_type=doc_type,
                    path=filepath,
                    e=e,
                )
            )

    type_summary = ", ".join(
        f"{kind}={count}" for kind, count in sorted(type_counts.items())
    )
    summary = _msg(
        "result.summary",
        "mdformat_check: {total} files, {ok} ok, {failed} failed",
        total=len(matched_files),
        ok=ok_count,
        failed=failed_count,
    )
    summary += (
        f"; document_types={type_summary or 'none'}"
        f"; agent_skill_invalid={skill_invalid_count}"
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
