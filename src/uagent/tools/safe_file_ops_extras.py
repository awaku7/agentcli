# tools/safe_file_ops_extras.py
"""Safe file operation utilities.

Provides a public API for common safety tasks:
- is_path_dangerous(path) -> bool
- ensure_within_workdir(path) -> str (returns absolute path)
- make_backup_before_overwrite(path) -> str (creates .org/.orgN)
"""

from __future__ import annotations

import os
from pathlib import Path

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


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


def is_path_dangerous(p: str) -> bool:
    """Determine if a path is dangerous.

    Returns True if:
    - Path contains '..'
    - Path is outside the workdir (CWD) after resolution
    """
    if not p:
        return True

    try:
        path_obj = Path(p)
    except Exception:
        return True

    if ".." in str(p).replace("\\", "/"):
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


def _next_backup_name(filename: str) -> str:
    base = filename + ".org"
    if not os.path.exists(base):
        return base

    i = 1
    while True:
        cand = f"{base}{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def make_backup_before_overwrite(filename: str) -> str:
    """Create a backup (.org/.orgN) of filename and return its path."""
    if not os.path.exists(filename):
        raise FileNotFoundError(
            _("err.file_not_found", default="file not found: {filename}").format(
                filename=filename
            )
        )

    backup_path = _next_backup_name(filename)
    Path(backup_path).parent.mkdir(parents=True, exist_ok=True)

    with open(filename, "rb") as rf, open(backup_path, "wb") as wf:
        wf.write(rf.read())

    return backup_path
