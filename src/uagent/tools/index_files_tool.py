from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import os
import glob
from typing import Any, Dict

try:
    from . import semantic_search_files_tool as vec_tool

    sync_file = getattr(vec_tool, "sync_file", None)
    _VEC_TOOL_ENABLED = isinstance(getattr(vec_tool, "TOOL_SPEC", None), dict)
except Exception:
    sync_file = None
    _VEC_TOOL_ENABLED = False

BUSY_LABEL = True
STATUS_LABEL = "tool:index_files"


if not _VEC_TOOL_ENABLED:
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC: Dict[str, Any] = {
        "type": "function",
        "function": {
            "name": "index_files",
            "description": _(
                "tool.description",
                default="Indexes specified files or directories (glob pattern) into the vector DB to enable semantic search (semantic_search_files). This is useful for preparing for search without reading file contents immediately.",
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": _(
                            "param.pattern.description",
                            default="The target file name, directory name, or glob pattern (e.g., 'src/**/*.py', '*.md').",
                        ),
                    },
                    "root_path": {
                        "type": "string",
                        "description": _(
                            "param.root_path.description",
                            default="The root directory for search and indexing. Defaults to current directory.",
                        ),
                        "default": ".",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": _(
                            "param.recursive.description",
                            default="Whether to search recursively when the pattern contains '**'.",
                        ),
                        "default": True,
                    },
                },
                "required": ["pattern"],
            },
        },
    }


def run_tool(args: Dict[str, Any]) -> str:
    if sync_file is None:
        return _(
            "err.vec_unavailable",
            default="Error: The semantic search module (semantic_search_files_tool) is not available, so indexing cannot be performed.",
        )

    pattern = str(args.get("pattern", ""))
    root_path = str(args.get("root_path", "."))
    recursive = bool(args.get("recursive", True))

    if not pattern:
        return _("err.pattern_required", default="Error: pattern is required.")

    root_abs = os.path.abspath(root_path)
    if not os.path.isdir(root_abs):
        return _(
            "err.root_not_dir",
            default="Error: root_path is not a directory: {root_path}",
        ).format(root_path=root_path)

    search_pattern = os.path.join(root_abs, pattern)

    try:
        files = glob.glob(search_pattern, recursive=recursive)
    except Exception as e:
        return _(
            "err.glob_fail", default="Error: Failed to parse pattern: {err}"
        ).format(err=e)

    from uagent.utils.scan_filters import is_ignored_path

    target_files = [f for f in files if os.path.isfile(f) and (not is_ignored_path(f))]

    if not target_files:
        return _(
            "out.not_found",
            default="No files were found matching the pattern '{pattern}'.",
        ).format(pattern=pattern)

    success_count = 0
    error_count = 0

    for fpath in target_files:
        try:
            sync_file(fpath, root_abs)
            success_count += 1
        except Exception:
            error_count += 1

    result = [
        _("out.completed", default="Indexing process completed."),
        _("out.pattern", default="Target pattern: {pattern}").format(pattern=pattern),
        _("out.root", default="Root directory: {root_abs}").format(root_abs=root_abs),
        _("out.success", default="Success: {count}").format(count=success_count),
    ]
    if error_count > 0:
        result.append(_("out.fail", default="Failed: {count}").format(count=error_count))

    result.append(
        _(
            "out.footer",
            default="\nYou can now search these files using `semantic_search_files`.",
        )
    )

    return "\n".join(result)
