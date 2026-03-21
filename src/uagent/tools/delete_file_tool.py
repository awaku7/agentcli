# tools/delete_file_tool.py
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": _(
            "tool.description",
            default=(
                "Delete the specified file or directory (directories are deleted recursively). "
                "Because this is dangerous, confirmation may be required."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Delete the specified path only after confirming with the user if it is a potentially "
                "destructive operation."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": _(
                        "param.filename.description",
                        default="Path to delete, or a list of paths/glob patterns to delete.",
                    ),
                },
                "path": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": _(
                        "param.path.description",
                        default="(Compatibility) Alias of filename.",
                    ),
                },
                "missing_ok": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.missing_ok.description",
                        default="If true, do not error when the path does not exist.",
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.dry_run.description",
                        default="If true, only list matched paths and do not delete anything.",
                    ),
                },
                "allow_dir": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.allow_dir.description",
                        default="If true, allow deleting directories matched by glob.",
                    ),
                },
            },
            "required": [],
        },
    },
}


def _human_confirm(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        res_json = human_ask({"message": message})
        payload = json.loads(res_json)
        user_reply = (payload.get("user_reply") or "").strip().lower()
        cancelled = bool(payload.get("cancelled", False))
        return (not cancelled) and user_reply in ("y", "yes")
    except Exception:
        return False


def _has_glob_meta(s: str) -> bool:
    # Spec: treat as glob only when meta characters are present.
    return any(ch in s for ch in ("*", "?", "["))


def _resolve_matches(raw_item: str, allow_dir: bool) -> List[str]:
    """Resolve one path/glob input into concrete absolute paths under workdir."""

    if not _has_glob_meta(raw_item):
        safe_path = ensure_within_workdir(raw_item)
        if not os.path.exists(safe_path):
            return []
        if os.path.isdir(safe_path) and not allow_dir:
            return []
        return [safe_path]

    import glob

    pat_norm = raw_item.replace("\\", "/")

    if "/" in pat_norm:
        base_dir = pat_norm.rsplit("/", 1)[0] or "."
    else:
        base_dir = "."

    safe_base_dir = ensure_within_workdir(base_dir)

    if base_dir in (".", ""):
        sub_pat = pat_norm
    else:
        sub_pat = pat_norm[len(base_dir) + 1 :]

    search_pat = os.path.join(safe_base_dir, sub_pat)
    matches = sorted(set(glob.glob(search_pat, recursive=True)))

    filtered: List[str] = []
    for m in matches:
        try:
            rel = os.path.relpath(m, os.getcwd())
            safe_m = ensure_within_workdir(rel)
        except Exception:
            continue
        if os.path.isdir(safe_m) and not allow_dir:
            continue
        filtered.append(safe_m)

    return filtered


def run_tool(args: Dict[str, Any]) -> str:
    raw_input = args.get("filename")
    if raw_input is None:
        raw_input = args.get("path")

    missing_ok_raw = args.get("missing_ok", False)
    dry_run_is_set = "dry_run" in args
    dry_run_raw = args.get("dry_run", None)
    allow_dir_raw = args.get("allow_dir", True)

    if not isinstance(missing_ok_raw, bool):
        raise ValueError("missing_ok must be a boolean")
    if dry_run_is_set and not isinstance(dry_run_raw, bool):
        raise ValueError("dry_run must be a boolean")
    if not isinstance(allow_dir_raw, bool):
        raise ValueError("allow_dir must be a boolean")

    missing_ok = missing_ok_raw
    allow_dir = allow_dir_raw

    if isinstance(raw_input, str):
        items = [raw_input.strip()] if raw_input.strip() else []
    elif isinstance(raw_input, list):
        items = []
        for i, v in enumerate(raw_input):
            if not isinstance(v, str):
                raise ValueError(
                    f"filename/path list item at index {i} must be a string"
                )
            vv = v.strip()
            if vv:
                items.append(vv)
    else:
        raise ValueError("filename/path must be a string or a list of strings")

    if not items:
        raise ValueError("filename/path is required")

    # Default behavior (matches tests/spec intent):
    # - If dry_run is explicitly provided, honor it.
    # - Otherwise, default to dry_run=True when any glob pattern is used.
    if dry_run_is_set:
        dry_run = dry_run_raw
    else:
        dry_run = any(_has_glob_meta(it) for it in items)

    missing_items: List[str] = []
    all_matches: List[str] = []
    seen: set[str] = set()

    for item in items:
        matches = _resolve_matches(item, allow_dir=allow_dir)
        if not matches:
            missing_items.append(item)
            continue
        for p in matches:
            if p not in seen:
                seen.add(p)
                all_matches.append(p)

    if missing_items and not missing_ok:
        raise FileNotFoundError(f"No paths matched: {missing_items[0]}")

    if not all_matches:
        return json.dumps(
            {
                "ok": True,
                "deleted": False,
                "matches": [],
                "count": 0,
                "missing": missing_items,
            },
            ensure_ascii=False,
        )

    if dry_run:
        return json.dumps(
            {
                "ok": True,
                "dry_run": True,
                "matches": all_matches,
                "count": len(all_matches),
                "missing": missing_items,
            },
            ensure_ascii=False,
        )

    preview_list = "\n".join(all_matches)
    msg = _(
        "confirm.delete_paths_bulk",
        default=(
            "Delete {count} paths?\n\n{paths}\n\n" "Enter y to proceed, or c to cancel."
        ),
    ).format(count=len(all_matches), paths=preview_list)

    if not _human_confirm(msg):
        return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)

    deleted: List[str] = []
    for p in all_matches:
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)
        deleted.append(p)

    payload: Dict[str, Any] = {
        "ok": True,
        "deleted": True,
        "matches": deleted,
        "count": len(deleted),
        "missing": missing_items,
    }

    if len(items) == 1 and len(deleted) == 1 and not _has_glob_meta(items[0]):
        payload["path"] = deleted[0]

    return json.dumps(payload, ensure_ascii=False)
