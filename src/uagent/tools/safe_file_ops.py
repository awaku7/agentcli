"""Safe wrappers for local file operations.

This module provides safety checks (user confirmation) for operations that can be risky,
including creating files, deleting files/directories, renaming/moving paths, and generating
a prompt file from a target file.

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

import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_allowed_paths: set[str] = set()


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
    """Trigger conditions (B: Medium).

    - Path contains ".."
    - Absolute path
    - Not under workdir (cwd)
    """

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


def _human_confirm(message: str) -> bool:
    cb = get_callbacks()
    # If callbacks are not available, fallback.
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

    # Wait until no other human_ask is active.
    # This avoids rejecting confirmations during nested workflows.
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
    """Delete a path safely.

    - File: os.remove
    - Directory: shutil.rmtree

    Safety policy:
    - If it matches trigger path conditions (absolute path / contains .. / outside workdir), ask for confirmation.
    - Directory deletion is risky, so always ask for confirmation.
    """

    resolved = _resolve_path(path)

    # First, confirmation based on trigger path detection.
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

    # Not exists
    if not p.exists():
        if missing_ok:
            return
        raise FileNotFoundError(
            _(
                "err.path_not_found",
                default="Path does not exist: {path}",
            ).format(path=path)
        )

    # Directory: always confirm
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

    # File
    os.remove(path)


def safe_rename_path(
    src: str,
    dst: str,
    overwrite: bool = False,
    mkdirs: bool = False,
) -> None:
    """Safely rename/move a file or directory with confirmations.

    - src/dst support both files and directories
    - overwrite=True: delete existing dst and replace (destructive)
    - mkdirs=True: create dst parent directory

    Confirmations:
    - Confirm if either src/dst is a trigger path
    - Confirm if overwrite=True (because it involves deletion)
    """

    if not src or not dst:
        raise ValueError(
            _(
                "err.src_dst_required",
                default="src and dst are required",
            )
        )

    src_p = Path(src)
    if not src_p.exists():
        raise FileNotFoundError(
            _(
                "err.src_not_found",
                default="src does not exist: {src}",
            ).format(src=src)
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

    if mkdirs:
        parent = Path(dst).parent
        if parent and not parent.exists():
            # mkdirs is generally safe, but if dst is trigger, it will be confirmed above.
            pass

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

    # For overwrite=True, delete dst first.
    if dst_exists and overwrite:
        d = Path(dst)
        if d.is_dir():
            shutil.rmtree(dst)
        else:
            os.remove(dst)

    # rename/move
    os.replace(src, dst)


def safe_generate_prompt(path: str, template: Optional[str] = None) -> str:
    if not Path(path).exists():
        raise FileNotFoundError(
            _(
                "err.prompt_target_not_found",
                default="Target file for prompt generation was not found: {path}",
            ).format(path=path)
        )

    resolved = _resolve_path(path)

    if _is_trigger_path(path) and resolved not in _allowed_paths:
        ok = _ask_user_confirm(path, "generate_prompt (read)")
        if not ok:
            raise PermissionError(
                _(
                    "err.prompt_cancel",
                    default="Prompt generation cancelled because the user did not allow it: {path}",
                ).format(path=path)
            )

        _allowed_paths.add(resolved)

    excerpt_lines: list[str] = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for _i in range(20):
            line = f.readline()
            if not line:
                break
            excerpt_lines.append(line)

    excerpt = "".join(excerpt_lines)

    timestamp = int(time.time())

    digest = hashlib.sha1((resolved + str(timestamp)).encode("utf-8")).hexdigest()[:10]

    out_dir = Path("files")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"generated_prompt_{digest}.txt"

    if template:
        content = template.format(
            path=path,
            lines=excerpt.count("\n")
            + (1 if excerpt and not excerpt.endswith("\n") else 0),
            size=Path(path).stat().st_size,
            mtime=Path(path).stat().st_mtime,
            excerpt=excerpt,
            timestamp=timestamp,
        )

    else:
        content = f"# Generated prompt for {path}\n# excerpt:\n{excerpt}\n"

    with open(out_path, "w", encoding="utf-8") as outf:
        outf.write(content)

    return str(out_path)


def clear_session_allowlist() -> None:
    _allowed_paths.clear()
