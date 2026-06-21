from __future__ import annotations

import os
from typing import Any

from .i18n_helper import make_tool_translator
from .pagination_util import paginate_results

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:list_dir"

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "x_parallel_safe": True,
    "function": {
        "name": "list_dir",
        "description": _(
            "tool.description",
            default="List entries in a directory with pagination, similar to ls.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "list_dir",
                "ls",
                "directory listing",
                "folder listing",
                "list files",
                "list folders",
            ],
        ),
        "x_search_terms_en": [
            "list_dir",
            "ls",
            "directory listing",
            "folder listing",
            "list files",
            "list folders",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Directory to list (default: current directory).",
                    ),
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": _(
                        "param.show_hidden.description",
                        default="Include hidden entries in the listing.",
                    ),
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of entries to return per page (default: 50).",
                    ),
                    "default": 50,
                },
                "page": {
                    "type": "integer",
                    "description": _(
                        "param.page.description",
                        default="Page number to retrieve (default: 1).",
                    ),
                    "default": 1,
                },
            },
            "required": [],
        },
    },
}


def _json_err(message: str, **extra: Any) -> str:
    path = extra.get("path")
    if path:
        return f"{message}: {path}"
    return message


def _format_size(size: int | None) -> str:
    if size is None:
        return "unknown size"
    return f"{size:,} bytes"


def _entry_kind(entry: os.DirEntry[str]) -> str:
    try:
        if entry.is_dir(follow_symlinks=False):
            return "dir"
        if entry.is_file(follow_symlinks=False):
            return "file"
        if entry.is_symlink():
            return "link"
    except Exception:
        return "other"
    return "other"


def _scan_dir(root_abs: str, show_hidden: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    with os.scandir(root_abs) as it:
        for entry in it:
            if (not show_hidden) and entry.name.startswith("."):
                continue

            kind = _entry_kind(entry)
            size: int | None = None
            target: str | None = None

            try:
                st = entry.stat(follow_symlinks=False)
                if kind == "file":
                    size = int(st.st_size)
            except Exception:
                pass

            if kind == "link":
                try:
                    target = os.readlink(entry.path)
                except Exception:
                    target = None

            results.append(
                {
                    "name": entry.name,
                    "kind": kind,
                    "size": size,
                    "target": target,
                }
            )

    kind_order = {"dir": 0, "link": 1, "file": 2, "other": 3}
    results.sort(
        key=lambda item: (
            kind_order.get(item["kind"], 9),
            item["name"].casefold(),
        )
    )
    return results


def run_tool(args: dict[str, Any]) -> str:
    root_path = str((args or {}).get("path") or (args or {}).get("root_path") or ".")
    show_hidden = bool((args or {}).get("show_hidden", False))

    max_results_raw = (args or {}).get("limit", 50)
    page_raw = (args or {}).get("page", 1)

    limit = int(max_results_raw) if max_results_raw is not None else 50
    page = int(page_raw) if page_raw is not None else 1

    if limit <= 0:
        limit = 50
    if page <= 0:
        page = 1

    root_abs = os.path.abspath(root_path)

    if not os.path.isdir(root_abs):
        return _("err.not_a_dir", default="Error: not a directory: {path}").format(
            path=root_abs
        )

    all_entries = _scan_dir(root_abs, show_hidden)

    if not all_entries:
        return _("msg.empty_dir", default="(empty directory)")

    # Paginate
    page_entries = paginate_results(all_entries, page=page, limit=limit)

    lines = [
        (
            f"{'[DIR]' if e['kind'] == 'dir' else '[FILE]'}"
            f" {e['name']}"
            f"{' -> ' + e['target'] if e.get('target') else ''}"
            f" ({_format_size(e.get('size')) if e['kind'] == 'file' else e['kind']})"
        )
        for e in page_entries
    ]

    header = (
        _(
            "msg.paginate",
            default="Page {page} of {total_pages} (showing {count} of {total} entries)",
        ).format(
            page=page,
            total_pages=max(1, (len(all_entries) + limit - 1) // limit),
            count=len(page_entries),
            total=len(all_entries),
        )
    )

    return header + "\n" + "\n".join(lines)
