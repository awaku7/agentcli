from __future__ import annotations

import ctypes
import os
import sys
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_dll_path = os.path.join(_CURRENT_DIR, "drm_tool_core.dll")
_lib = None

if os.path.exists(_dll_path):
    try:
        _lib = ctypes.CDLL(_dll_path)
        _lib.drm_free_string.argtypes = [ctypes.c_void_p]
        _lib.drm_free_string.restype = None

        _lib.drm_pack_skp.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int64,
            ctypes.c_int64,
        ]
        _lib.drm_pack_skp.restype = ctypes.c_void_p

        _lib.drm_mount_skp.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        _lib.drm_mount_skp.restype = ctypes.c_void_p

        _lib.drm_vfs_read_file.argtypes = [ctypes.c_char_p]
        _lib.drm_vfs_read_file.restype = ctypes.c_void_p

        _lib.drm_vfs_list_dir.argtypes = []
        _lib.drm_vfs_list_dir.restype = ctypes.c_void_p

        _lib.drm_vfs_exists.argtypes = [ctypes.c_char_p]
        _lib.drm_vfs_exists.restype = ctypes.c_int32
    except Exception as e:
        sys.stderr.write(f"[drm_tool] Failed to load native library: {e}\n")


def _get_str_and_free(ptr_val: int | None) -> str:
    if not ptr_val:
        return ""
    try:
        res = ctypes.string_at(ptr_val).decode("utf-8", errors="replace")
    finally:
        if _lib:
            _lib.drm_free_string(ctypes.c_void_p(ptr_val))
    return res


def run_drm_tool(
    action: str = "read",
    in_dir: str = "",
    out_file: str = "",
    skp_file: str = "",
    file: str = "",
    email: str = "",
    password: str = "",
    path: str = "",
    start_at: str = "0",
    expires_at: str = "4102444800",
    **kwargs: Any,
) -> str:
    if not _lib:
        return "[drm_tool] Native library drm_tool_core.dll is not loaded."

    session_token = os.environ.get("UAGENT_SESSION_SECRET", "")
    target_file = skp_file or file or out_file

    if action == "pack":
        try:
            s_at = int(start_at)
            e_at = int(expires_at)
        except ValueError:
            s_at, e_at = 0, 4102444800
        ptr = _lib.drm_pack_skp(
            in_dir.encode("utf-8"),
            target_file.encode("utf-8"),
            email.encode("utf-8"),
            password.encode("utf-8"),
            ctypes.c_int64(s_at),
            ctypes.c_int64(e_at),
        )
        return _get_str_and_free(ptr)

    elif action == "mount":
        ptr = _lib.drm_mount_skp(
            target_file.encode("utf-8"),
            password.encode("utf-8"),
            session_token.encode("utf-8"),
        )
        return _get_str_and_free(ptr)

    elif action == "read":
        ptr = _lib.drm_vfs_read_file(path.encode("utf-8"))
        return _get_str_and_free(ptr)

    elif action == "list":
        ptr = _lib.drm_vfs_list_dir()
        return _get_str_and_free(ptr)

    elif action == "exists":
        res = _lib.drm_vfs_exists(path.encode("utf-8"))
        return "True" if res == 1 else "False"

    return f"Error: Unknown action '{action}'"


# Standard Tool Runner Alias
run_tool = run_drm_tool

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "drm_tool",
        "description": _(
            "tool.description",
            default="暗号化されたSKILLパッケージ(.skp)をインメモリRead-Only VFSとして安全にマウント・読み取り参照するツール",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["drm_tool", "skp", "vfs", "skill_drm", "decrypt"],
        ),
        "x_search_terms_en": ["drm_tool", "skp", "vfs", "skill_drm", "decrypt"],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["pack", "mount", "read", "list", "exists"],
                    "description": _(
                        "param.action",
                        default="操作種別 (pack: 暗号化パック作成, mount: VFSマウント, read: VFS内ファイル安全読み込み, list: ファイル一覧, exists: 存在確認)",
                    ),
                },
                "in_dir": {
                    "type": "string",
                    "description": _("param.in_dir", default="パック対象のローカルスキルディレクトリ"),
                },
                "out_file": {
                    "type": "string",
                    "description": _("param.out_file", default="パック出力先の .skp ファイルパス"),
                },
                "file": {
                    "type": "string",
                    "description": _("param.file", default=".skp パッケージファイルのパス"),
                },
                "email": {
                    "type": "string",
                    "description": _("param.email", default="発行者メールアドレス"),
                },
                "password": {
                    "type": "string",
                    "description": _("param.password", default="復号パスワード"),
                },
                "path": {
                    "type": "string",
                    "description": _("param.path", default="VFS内の仮想ファイル/ディレクトリパス"),
                },
            },
            "required": ["action"],
        },
    },
}
