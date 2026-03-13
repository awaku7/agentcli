# tools/file_exists.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

from .arg_util import get_path
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:file_exists"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "file_exists",
        "description": _(
            "tool.description",
            default=(
                "Checks if a file or directory exists at the specified path and returns "
                "type, size, timestamps (created/modified/accessed), and owner/group where available."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Use this tool to check whether a file or directory exists and retrieve metadata "
                "(type, size, mtime/atime/ctime, and owner/group when available)."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path of the file or directory to check for existence (supports ~).",
                    ),
                }
            },
            "required": ["path"],
        },
    },
}


def _fmt_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _resolve_owner_group(path: str, st: os.stat_result) -> Tuple[str, str]:
    # POSIX: resolve from uid/gid
    if os.name != "nt":
        owner = "unknown"
        group = "unknown"
        try:
            import pwd  # type: ignore

            owner = pwd.getpwuid(st.st_uid).pw_name
        except Exception:
            try:
                owner = str(st.st_uid)
            except Exception:
                pass

        try:
            import grp  # type: ignore

            group = grp.getgrgid(st.st_gid).gr_name
        except Exception:
            try:
                group = str(st.st_gid)
            except Exception:
                pass

        return owner, group

    # Windows: try pywin32 for owner/group SID lookup
    try:
        import win32security  # type: ignore

        sec_info = (
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.GROUP_SECURITY_INFORMATION
        )
        sd = win32security.GetFileSecurity(path, sec_info)

        owner_sid = sd.GetSecurityDescriptorOwner()
        group_sid = sd.GetSecurityDescriptorGroup()

        owner_name, owner_domain, _ = win32security.LookupAccountSid(None, owner_sid)
        group_name, group_domain, _ = win32security.LookupAccountSid(None, group_sid)

        owner = f"{owner_domain}\\{owner_name}" if owner_domain else owner_name
        group = f"{group_domain}\\{group_name}" if group_domain else group_name
        return owner, group
    except Exception:
        # Fallback when pywin32 is unavailable or ACL lookup fails
        return "unknown", "unknown"


def run_tool(args: Dict[str, Any]) -> str:
    expanded = get_path(args, "path", "")
    if not expanded:
        return _("err.path_empty", default="[file_exists error] path is empty")

    try:
        if not os.path.exists(expanded):
            return f"[file_exists]\npath={expanded}\nexists=False"

        is_dir = os.path.isdir(expanded)
        st = os.stat(expanded)

        mtime = _fmt_ts(st.st_mtime)
        atime = _fmt_ts(st.st_atime)
        ctime = _fmt_ts(st.st_ctime)

        birthtime_val: Optional[float] = getattr(st, "st_birthtime", None)
        created_time_best_effort = (
            _fmt_ts(birthtime_val) if birthtime_val is not None else ctime
        )
        created_time_basis = (
            "birthtime"
            if birthtime_val is not None
            else ("ctime" if os.name == "nt" else "ctime(metadata-change-time)")
        )

        owner, group = _resolve_owner_group(expanded, st)
        size_str = "n/a (directory)" if is_dir else f"{st.st_size} bytes"

        return (
            "[file_exists]\n"
            f"path={expanded}\n"
            "exists=True\n"
            f"is_dir={is_dir}\n"
            f"size={size_str}\n"
            f"created_time={created_time_best_effort}\n"
            f"created_time_basis={created_time_basis}\n"
            f"mtime={mtime}\n"
            f"atime={atime}\n"
            f"ctime={ctime}\n"
            f"owner={owner}\n"
            f"group={group}"
        )
    except Exception as e:
        return f"[file_exists error] {type(e).__name__}: {e}"
