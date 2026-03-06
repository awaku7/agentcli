# tools/delete_file_tool.py
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict

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
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="Path to the file to delete.",
                    ),
                },
                "path": {
                    "type": "string",
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


def run_tool(args: Dict[str, Any]) -> str:
    raw_filename = str(args.get("filename") or args.get("path") or "").strip()
    missing_ok_raw = args.get("missing_ok", False)
    dry_run_raw = args.get("dry_run", True)
    allow_dir_raw = args.get("allow_dir", True)

    if not isinstance(missing_ok_raw, bool):
        raise ValueError("missing_ok must be a boolean")
    if not isinstance(dry_run_raw, bool):
        raise ValueError("dry_run must be a boolean")
    if not isinstance(allow_dir_raw, bool):
        raise ValueError("allow_dir must be a boolean")

    missing_ok = missing_ok_raw
    dry_run = dry_run_raw
    allow_dir = allow_dir_raw

    if not raw_filename:
        raise ValueError("filename/path is required")

    # --- Non-glob path (backward compatible) ---
    if not _has_glob_meta(raw_filename):
        safe_path = ensure_within_workdir(raw_filename)

        if not os.path.exists(safe_path):
            if missing_ok:
                return json.dumps({"ok": True, "deleted": False, "path": safe_path})
            raise FileNotFoundError(safe_path)

        msg = _(
            "confirm.delete_path",
            default="Delete path: {path}?\nEnter y to proceed, or c to cancel.",
        ).format(path=safe_path)
        if not _human_confirm(msg):
            return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)

        if os.path.isdir(safe_path):
            shutil.rmtree(safe_path)
        else:
            os.remove(safe_path)

        return json.dumps(
            {"ok": True, "deleted": True, "path": safe_path}, ensure_ascii=False
        )

    # --- Glob path ---
    import glob

    pat_norm = raw_filename.replace("\\", "/")

    if "/" in pat_norm:
        base_dir = pat_norm.rsplit("/", 1)[0] or "."
    else:
        base_dir = "."

    safe_base_dir = ensure_within_workdir(base_dir)

    # Make pattern relative to base_dir, then join with safe_base_dir.
    if base_dir in (".", ""):
        sub_pat = pat_norm
    else:
        sub_pat = pat_norm[len(base_dir) + 1 :]

    search_pat = os.path.join(safe_base_dir, sub_pat)
    matches = sorted(set(glob.glob(search_pat, recursive=True)))

    filtered: list[str] = []
    for m in matches:
        try:
            rel = os.path.relpath(m, os.getcwd())
            safe_m = ensure_within_workdir(rel)
        except Exception:
            continue
        if os.path.isdir(safe_m) and not allow_dir:
            continue
        filtered.append(safe_m)

    if not filtered:
        if missing_ok:
            return json.dumps(
                {"ok": True, "deleted": False, "matches": [], "count": 0},
                ensure_ascii=False,
            )
        raise FileNotFoundError(f"No paths matched: {raw_filename}")

    if dry_run:
        return json.dumps(
            {"ok": True, "dry_run": True, "matches": filtered, "count": len(filtered)},
            ensure_ascii=False,
        )

    preview_list = "\n".join(filtered)
    msg = _(
        "confirm.delete_paths_bulk",
        default=(
            "Delete {count} paths matched by glob?\n\n{paths}\n\n"
            "Enter y to proceed, or c to cancel."
        ),
    ).format(count=len(filtered), paths=preview_list)

    if not _human_confirm(msg):
        return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)

    deleted: list[str] = []
    for p in filtered:
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)
        deleted.append(p)

    return json.dumps(
        {"ok": True, "deleted": True, "matches": deleted, "count": len(deleted)},
        ensure_ascii=False,
    )
