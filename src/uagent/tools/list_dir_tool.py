from __future__ import annotations

import json
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
    "function": {
        "name": "list_dir",
        "description": _(
            "tool.description",
            default="List entries in a directory with pagination, similar to ls.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "List directory entries and return a paginated listing. "
                "Use page and max_results for pagination. "
                "If show_hidden is false, omit hidden entries (dotfiles and dot-directories)."
            ),
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
                        default="Directory to list (default: current directory). Alias of root_path.",
                    ),
                },
                "root_path": {
                    "type": "string",
                    "description": _(
                        "param.root_path.description",
                        default="Alias of path for backward compatibility.",
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
                "max_results": {
                    "type": "integer",
                    "description": _(
                        "param.max_results.description",
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
            if (not show_hidden) and entry.name.startswith('.'):
                continue

            kind = _entry_kind(entry)
            size: int | None = None
            target: str | None = None

            try:
                st = entry.stat(follow_symlinks=False)
                if kind == 'file':
                    size = int(st.st_size)
            except Exception:
                pass

            if kind == 'link':
                try:
                    target = os.readlink(entry.path)
                except Exception:
                    target = None

            results.append(
                {
                    'name': entry.name,
                    'kind': kind,
                    'size': size,
                    'target': target,
                }
            )

    kind_order = {'dir': 0, 'link': 1, 'file': 2, 'other': 3}
    results.sort(
        key=lambda item: (
            kind_order.get(item['kind'], 9),
            item['name'].casefold(),
        )
    )
    return results


def run_tool(args: dict[str, Any]) -> str:
    root_path = str((args or {}).get('path') or (args or {}).get('root_path') or '.')
    show_hidden = bool((args or {}).get('show_hidden', False))

    max_results_raw = (args or {}).get('max_results', 50)
    page_raw = (args or {}).get('page', 1)

    try:
        max_results = int(max_results_raw)
    except Exception:
        max_results = 50
    if max_results <= 0:
        max_results = 50

    try:
        page = int(page_raw)
    except Exception:
        page = 1
    if page < 1:
        page = 1

    root_abs = os.path.abspath(os.path.expanduser(root_path))

    if not os.path.exists(root_abs):
        return _(
            'err.dir_not_exist',
            default='[list_dir error] Directory does not exist: {path}',
        ).format(path=root_path)

    if not os.path.isdir(root_abs):
        return _(
            'err.path_not_dir',
            default='[list_dir error] Path is not a directory: {path}',
        ).format(path=root_path)

    try:
        entries = _scan_dir(root_abs, show_hidden=show_hidden)
    except Exception as e:
        return _json_err(f'[list_dir error] {type(e).__name__}: {e}', path=root_abs)

    if not entries:
        return '\n'.join(
            [
                _(
                    'out.path',
                    default='Path: {path}',
                ).format(path=root_abs),
                _(
                    'out.no_entries',
                    default='[list_dir] No entries found.',
                ),
            ]
        )

    page_results, page, total_pages, total_results = paginate_results(
        entries, page, max_results
    )

    out_lines: list[str] = [
        _(
            'out.found_paginated',
            default='[list_dir] Page {page} of {total_pages} (Total {total} entries, showing {showing})',
        ).format(
            page=page,
            total_pages=total_pages,
            total=total_results,
            showing=len(page_results),
        ),
        _(
            'out.path',
            default='Path: {path}',
        ).format(path=root_abs),
    ]

    for item in page_results:
        kind = item['kind']
        name = item['name']

        if kind == 'dir':
            out_lines.append(
                _(
                    'out.entry.dir',
                    default='[DIR] {name}/',
                ).format(name=name)
            )
        elif kind == 'file':
            out_lines.append(
                _(
                    'out.entry.file',
                    default='[FILE] {name} ({size})',
                ).format(name=name, size=_format_size(item.get('size')))
            )
        elif kind == 'link':
            target = item.get('target')
            out_lines.append(
                _(
                    'out.entry.link',
                    default='[LINK] {name}{target}',
                ).format(name=name, target=f' -> {target}' if target else '')
            )
        else:
            out_lines.append(
                _(
                    'out.entry.other',
                    default='[OTHER] {name}',
                ).format(name=name)
            )

    return '\n'.join(out_lines)
