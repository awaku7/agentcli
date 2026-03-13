"""Safe wrappers and utilities for local file operations.

This module provides safety checks (user confirmation) for operations that can be risky,
including creating files, deleting files/directories, and renaming/moving paths.

Policy (B: Medium):
- Always ask for user confirmation when an obviously risky operation is detected:
  - outside workdir
  - absolute paths
  - path traversal (..)
- Otherwise, proceed as usual.

Confirmation UI:
- Prefer the same mechanism as human_ask (shared queue consumed by stdin_loop).
- If another human_ask is active, wait for a while and then start confirmation.
- If callbacks are unavailable, fall back to input().

Cancel:
- 'c' or 'cancel' means cancel.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_allowed_paths: set[str] = set()


# --- Internal Helpers ---


def _resolve_path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


def _workdir_root() -> str:
    return str(Path(os.getcwd()).resolve())


def _is_under(root: str, target: str) -> bool:
    try:
        Path(target).relative_to(Path(root))
        return True
    except Exception:
        return False


def _is_trigger_path(p: str) -> bool:
    """Internal trigger check."""
    return is_path_dangerous(p)


def _human_confirm(message: str) -> bool:
    cb = get_callbacks()
    if (
        cb.human_ask_lock is None
        or cb.human_ask_active_ref is None
        or cb.human_ask_set_active is None
        or cb.human_ask_queue_ref is None
        or cb.human_ask_set_queue is None
        or cb.human_ask_lines_ref is None
        or cb.human_ask_set_multiline_active is None
    ):
        try:
            resp = input(message + "\n[y/c/N]: ")
        except Exception:
            return False
        r = resp.strip().lower()
        return r == "y"

    import queue as _queue

    local_q: "_queue.Queue[str]" = _queue.Queue()
    wait_timeout_sec = 30.0
    poll_interval_sec = 0.1
    start = time.time()

    while True:
        with cb.human_ask_lock:
            busy = cb.human_ask_active_ref()
            if not busy:
                cb.human_ask_set_active(True)
                cb.human_ask_set_queue(local_q)
                lines = cb.human_ask_lines_ref()
                try:
                    lines.clear()
                except Exception:
                    pass
                cb.human_ask_set_multiline_active(False)
                break
        if time.time() - start > wait_timeout_sec:
            return False
        time.sleep(poll_interval_sec)

    try:
        print(
            "\n" + _("ui.confirm.title", default="=== Human confirmation request ==="),
            flush=True,
        )
        print(message, flush=True)
        print(_("ui.confirm.footer", default="=== /confirm ===\n"), flush=True)
        print(
            _(
                "ui.confirm.howto",
                default="How to reply: y=proceed / c=cancel / other=deny\n",
            ),
            flush=True,
        )
        user_reply = local_q.get()

    finally:
        with cb.human_ask_lock:
            cb.human_ask_set_active(False)
            cb.human_ask_set_queue(None)
            cb.human_ask_set_multiline_active(False)

    ur = (user_reply or "").strip().lower()
    return ur == "y"


def _ask_user_confirm(path: str, operation: str) -> bool:
    msg = _(
        "confirm.risky_op",
        default=(
            "This operation might be dangerous, so confirmation is required.\n"
            "operation: {operation}\n"
            "path: {path}\n"
            "Reply with y to proceed, or c to cancel."
        ),
    ).format(operation=operation, path=path)
    return _human_confirm(msg)


def _ask_user_confirm_rename(src: str, dst: str, details: str) -> bool:
    msg = _(
        "confirm.rename",
        default=(
            "rename/move will move real files (it may overwrite or delete existing files).\n"
            "src: {src}\n"
            "dst: {dst}\n"
            "details: {details}\n\n"
            "Reply with y to proceed, or c to cancel."
        ),
    ).format(src=src, dst=dst, details=details)
    return _human_confirm(msg)


def _ensure_parent_dir_exists(path: str) -> None:
    parent = Path(path).parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


# --- Public Utilities ---


def is_path_dangerous(p: str) -> bool:
    """Determine if a path is dangerous (e.g. outside workdir or contains '..')."""
    if not p:
        return True
    try:
        path_obj = Path(p)
    except Exception:
        return True
    if ".." in str(p).replace("\\", "/"):
        return True
    if path_obj.is_absolute():
        return True
    resolved = _resolve_path(p)
    if not _is_under(_workdir_root(), resolved):
        return True
    return False


def ensure_within_workdir(p: str) -> str:
    """Resolve p and ensure it is within the workdir. Returns the absolute path."""
    if not p:
        raise ValueError(_("err.path_empty", default="path is empty"))
    resolved = _resolve_path(p)
    root = _workdir_root()
    if not _is_under(root, resolved):
        raise PermissionError(
            _(
                "err.outside_workdir",
                default="path is outside workdir: root={root} path={path}",
            ).format(root=root, path=resolved)
        )
    return resolved


def make_backup_before_overwrite(filename: str) -> str:
    """Create a backup (.org/.orgN) of filename and return its path."""
    if not os.path.exists(filename):
        raise FileNotFoundError(
            _("err.file_not_found", default="file not found: {filename}").format(
                filename=filename
            )
        )

    base = filename + ".org"
    if not os.path.exists(base):
        backup_path = base
    else:
        i = 1
        while True:
            cand = f"{base}{i}"
            if not os.path.exists(cand):
                backup_path = cand
                break
            i += 1

    Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
    with open(filename, "rb") as rf, open(backup_path, "wb") as wf:
        wf.write(rf.read())
    return backup_path


# --- Public Safe Operations ---


def safe_create_file(
    filename: str, content: str, encoding: str = "utf-8", overwrite: bool = False
) -> None:
    resolved = _resolve_path(filename)
    if _is_trigger_path(filename) and resolved not in _allowed_paths:
        ok = _ask_user_confirm(filename, "create")
        if not ok:
            raise PermissionError(
                _(
                    "err.create_cancel",
                    default="Creation cancelled because the user did not allow it: {filename}",
                ).format(filename=filename)
            )
        _allowed_paths.add(resolved)

    p = Path(filename)
    if p.exists() and not overwrite:
        raise FileExistsError(
            _(
                "err.exists_overwrite_false",
                default="File already exists (overwrite=False): {filename}",
            ).format(filename=filename)
        )
    _ensure_parent_dir_exists(filename)
    with open(filename, "w", encoding=encoding) as f:
        f.write(content)


def safe_delete_file(filename: str, missing_ok: bool = False) -> None:
    resolved = _resolve_path(filename)
    if _is_trigger_path(filename) and resolved not in _allowed_paths:
        ok = _ask_user_confirm(filename, "delete")
        if not ok:
            raise PermissionError(
                _(
                    "err.delete_cancel",
                    default="Deletion cancelled because the user did not allow it: {filename}",
                ).format(filename=filename)
            )
        _allowed_paths.add(resolved)
    try:
        os.remove(filename)
    except FileNotFoundError:
        if missing_ok:
            return
        raise


def safe_delete_path(path: str, missing_ok: bool = False) -> None:
    """Delete a path safely."""
    resolved = _resolve_path(path)
    if _is_trigger_path(path) and resolved not in _allowed_paths:
        ok = _ask_user_confirm(path, "delete")
        if not ok:
            raise PermissionError(
                _(
                    "err.delete_path_cancel",
                    default="Deletion cancelled because the user did not allow it: {path}",
                ).format(path=path)
            )
        _allowed_paths.add(resolved)

    p = Path(path)
    if not p.exists():
        if missing_ok:
            return
        raise FileNotFoundError(
            _("err.path_not_found", default="Path does not exist: {path}").format(
                path=path
            )
        )

    if p.is_dir():
        ok = _ask_user_confirm(path, "delete_dir")
        if not ok:
            raise PermissionError(
                _(
                    "err.delete_dir_cancel",
                    default="Directory deletion cancelled because the user did not allow it: {path}",
                ).format(path=path)
            )
        shutil.rmtree(path)
        return
    os.remove(path)


def safe_rename_path(
    src: str,
    dst: str,
    overwrite: bool = False,
    mkdirs: bool = False,
) -> None:
    """Safely rename/move a file or directory with confirmations."""
    if not src or not dst:
        raise ValueError(_("err.src_dst_required", default="src and dst are required"))
    src_p = Path(src)
    if not src_p.exists():
        raise FileNotFoundError(
            _("err.src_not_found", default="src does not exist: {src}").format(src=src)
        )

    src_resolved = _resolve_path(src)
    dst_resolved = _resolve_path(dst)
    need_confirm = False
    reasons: list[str] = []

    if _is_trigger_path(src) and src_resolved not in _allowed_paths:
        need_confirm = True
        reasons.append(
            _("reason.src_trigger", default="src matches risky path conditions")
        )
    if _is_trigger_path(dst) and dst_resolved not in _allowed_paths:
        need_confirm = True
        reasons.append(
            _("reason.dst_trigger", default="dst matches risky path conditions")
        )

    dst_exists = Path(dst).exists()
    if dst_exists and overwrite:
        need_confirm = True
        reasons.append(
            _(
                "reason.overwrite_delete",
                default="overwrite=True will delete existing dst and replace it",
            )
        )
    elif dst_exists and not overwrite:
        raise FileExistsError(
            _(
                "err.dst_exists_overwrite_false",
                default="dst already exists (overwrite=False): {dst}",
            ).format(dst=dst)
        )

    if need_confirm:
        detail = ", ".join(reasons) if reasons else "(no detail)"
        ok = _ask_user_confirm_rename(src, dst, detail)
        if not ok:
            raise PermissionError(
                _(
                    "err.rename_cancel",
                    default="rename/move cancelled because the user did not allow it: {src} -> {dst}",
                ).format(src=src, dst=dst)
            )
        _allowed_paths.add(src_resolved)
        _allowed_paths.add(dst_resolved)

    if mkdirs:
        _ensure_parent_dir_exists(dst)

    if dst_exists and overwrite:
        d = Path(dst)
        if d.is_dir():
            shutil.rmtree(dst)
        else:
            os.remove(dst)
    os.replace(src, dst)


def clear_session_allowlist() -> None:
    _allowed_paths.clear()
