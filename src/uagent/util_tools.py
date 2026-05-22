from __future__ import annotations

import argparse
import base64
import glob
import json
import mimetypes
import os
import re
import subprocess
import shutil
import shlex
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .env_utils import env_get
from .i18n import _, detect_lang, set_thread_lang
from .uagent_env_keys import _is_placeholder_uagent_key, get_known_uagent_env_keys

set_thread_lang(detect_lang())

from . import tools
from .tools import long_memory as personal_long_memory
from .tools import shared_memory

from .tools.context import ToolCallbacks, get_callbacks

# Default translation function used when core.tr is not provided.
# Kept as a separate name for backward-compatibility.
tr = _
tr_ = _


@dataclass
class CommandResult:
    continue_running: bool = True
    run_llm: bool = False
    prompt: str | None = None

    def __bool__(self) -> bool:
        return self.continue_running


def init_tools_callbacks(core: Any) -> None:
    """tools 側へ、ホスト側の依存（core の関数・状態）を注入する。"""

    cb = ToolCallbacks(
        set_status=getattr(core, "set_status", None),
        debug=getattr(core, "debug", None),
        log=getattr(core, "log", None),
        error=getattr(core, "error", None),
        exception=getattr(core, "exception", None),
        rewrite_current_log_from_messages=getattr(
            core, "rewrite_current_log_from_messages", None
        ),
        get_env=getattr(core, "get_env", None),
        get_env_url=getattr(core, "get_env_url", None),
        truncate_output=(
            (
                lambda label, text, limit=200000: core.truncate_output(
                    label, text, limit=limit
                )
            )
            if hasattr(core, "truncate_output")
            else None
        ),
        human_ask_lock=getattr(core, "human_ask_lock", None),
        human_ask_active_ref=(lambda: getattr(core, "human_ask_active", False)),
        human_ask_set_active=(
            (lambda v: setattr(core, "human_ask_active", bool(v)))
            if hasattr(core, "human_ask_active")
            else None
        ),
        human_ask_queue_ref=(lambda: getattr(core, "human_ask_queue", None)),
        human_ask_set_queue=(
            (lambda q: setattr(core, "human_ask_queue", q))
            if hasattr(core, "human_ask_queue")
            else None
        ),
        human_ask_lines_ref=(lambda: getattr(core, "human_ask_lines", [])),
        human_ask_multiline_active_ref=(
            lambda: getattr(core, "human_ask_multiline_active", False)
        ),
        human_ask_set_multiline_active=(
            (lambda v: setattr(core, "human_ask_multiline_active", bool(v)))
            if hasattr(core, "human_ask_multiline_active")
            else None
        ),
        human_ask_set_password=(
            (lambda v: setattr(core, "human_ask_is_password", bool(v)))
            if hasattr(core, "human_ask_is_password")
            else None
        ),
        multi_input_sentinel=getattr(core, "MULTI_INPUT_SENTINEL", '"""end'),
        event_queue=getattr(core, "event_queue", None),
        cmd_encoding=getattr(core, "CMD_ENCODING", "utf-8"),
        cmd_exec_timeout_ms=getattr(core, "CMD_EXEC_TIMEOUT_MS", 60_000),
        python_exec_timeout_ms=getattr(core, "PYTHON_EXEC_TIMEOUT_MS", 60_000),
        url_fetch_timeout_ms=getattr(core, "URL_FETCH_TIMEOUT_MS", 60_000),
        url_fetch_max_bytes=getattr(core, "URL_FETCH_MAX_BYTES", 1_000_000),
        read_file_max_bytes=getattr(core, "READ_FILE_MAX_BYTES", 1_000_000),
        is_gui=False,
    )

    tools.init_callbacks(cb)


_IMAGE_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:\\\\|\\\\\\\\|\./|\.\\\\)?[^\s\"']+\.(?:png|jpg|jpeg|gif|webp))",
    re.IGNORECASE,
)


def extract_image_paths(text: str) -> list[str]:
    """テキストから画像ファイルっぽいパスを抽出（ゆるめ）。"""
    if not text:
        return []

    # JSONっぽい出力に備えて先に余計な記号を軽く剥がす
    cleaned = text.replace("\r", "")

    paths: list[str] = []
    for m in _IMAGE_PATH_RE.finditer(cleaned):
        p = m.group("path")
        if not p:
            continue

        # 末尾に句読点などが付くケースの除去（例: "/a.png,")
        p = p.rstrip(',.;:)]}>"')
        p = p.lstrip('"')

        # 重複排除（順序維持）
        if p not in paths:
            paths.append(p)

    return paths


def open_image_with_default_app(path: str) -> bool:
    """Windows の既定アプリでファイルを開く。成功/失敗を返す。"""
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        abspath = os.path.abspath(expanded)

        if not os.path.exists(abspath):
            return False

        # Windows は os.startfile が最も直接的。
        if os.name == "nt" and hasattr(os, "startfile"):
            os.startfile(abspath)  # type: ignore[attr-defined]
            return True

        # フォールバック。
        subprocess.Popen(
            ["xdg-open", abspath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    """Convert a local image file to a data URL (base64).

    Safety:
    - Enforces max_bytes to avoid huge payloads.
    - Requires that the file exists and is a file.

    Returns:
      data:<mime>;base64,<payload>
    """

    p = Path(str(path))
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(tr("image file not found: %(path)s") % {"path": path})

    size = p.stat().st_size
    if size > int(max_bytes):
        raise ValueError(
            tr("image file too large: %(size)d bytes (limit=%(max)d)")
            % {"size": size, "max": max_bytes}
        )

    mt, _ = mimetypes.guess_type(str(p))
    mime_type = mt or "application/octet-stream"

    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def try_open_images_from_text(text: str) -> None:
    """Deprecated no-op: assistant-text image auto-open was removed."""
    return


def parse_startup_args() -> tuple[dict[str, Any], list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--workdir",
        "-C",
        dest="workdir",
        help=_(
            "Specify working directory. If not set, uses UAGENT_WORKDIR env var or the current directory."
        ),
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=_(
            "Non-interactive mode. Do not start the stdin loop; exit after processing the startup file (if any)."
        ),
    )
    args, unknown = parser.parse_known_args()
    return vars(args), unknown


def iter_backup_files(root_dir: str) -> list[str]:
    """Find backup files under root_dir.

    Backup pattern:
    - *.org
    - *.org<digits>

    Returns list of file paths.
    """
    root = Path(root_dir)
    results: list[str] = []
    if not root.exists():
        return results

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".org"):
            results.append(str(p))
            continue
        m = re.match(r"^.+\.org\d+$", name)
        if m:
            results.append(str(p))

    return results


# ==============================
# Reasoning / Verbosity modes
# ==============================

_REASONING_LEVELS = ["off", "auto", "minimal", "low", "medium", "high", "xhigh"]
_VERBOSITY_LEVELS = ["off", "low", "medium", "high"]


def get_reasoning_mode() -> str:
    v = (env_get("UAGENT_REASONING") or "").strip().lower()
    return v if v in _REASONING_LEVELS and v != "off" else "off"


def get_verbosity_mode() -> str:
    v = (env_get("UAGENT_VERBOSITY") or "").strip().lower()
    return v if v in _VERBOSITY_LEVELS and v != "off" else "off"


def _normalize_off_arg(a: str) -> str | None:
    if a in ("0", "off", "none", "no", "false", "disable", "disabled"):
        return "off"
    return None


def _normalize_reasoning_level_arg(arg: str) -> str | None:
    a = (arg or "").strip().lower()
    if not a:
        return None

    off = _normalize_off_arg(a)
    if off is not None:
        return off

    if a in ("auto", "a"):
        return "auto"
    if a in ("minimal", "min"):
        return "minimal"
    if a in ("1", "low"):
        return "low"
    if a in ("2", "mid", "middle", "medium"):
        return "medium"
    if a in ("3", "high"):
        return "high"
    if a in ("xhigh", "xh", "x-high"):
        return "xhigh"

    return None


def _normalize_verbosity_level_arg(arg: str) -> str | None:
    a = (arg or "").strip().lower()
    if not a:
        return None

    off = _normalize_off_arg(a)
    if off is not None:
        return off

    if a in ("1", "low"):
        return "low"
    if a in ("2", "mid", "middle", "medium"):
        return "medium"
    if a in ("3", "high"):
        return "high"

    return None


def _cycle_level(cur: str, levels: list[str]) -> str:
    c = (cur or "off").strip().lower()
    if c not in levels:
        c = "off"
    idx = levels.index(c)
    return levels[(idx + 1) % len(levels)]


def set_reasoning_mode(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv not in _REASONING_LEVELS:
        lv = "off"
    if lv == "off":
        os.environ.pop("UAGENT_REASONING", None)
    else:
        os.environ["UAGENT_REASONING"] = lv
    return get_reasoning_mode()


def set_verbosity_mode(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv not in _VERBOSITY_LEVELS:
        lv = "off"
    if lv == "off":
        os.environ.pop("UAGENT_VERBOSITY", None)
    else:
        os.environ["UAGENT_VERBOSITY"] = lv
    return get_verbosity_mode()


def apply_reasoning_arg(arg: str) -> str:
    cur = get_reasoning_mode()
    lv = _normalize_reasoning_level_arg(arg)
    if lv is None and (arg or "").strip():
        # invalid (non-empty)
        raise ValueError(tr("invalid reasoning"))

    # If no arg is given, keep current mode (do not cycle).
    if lv is None:
        return cur

    return set_reasoning_mode(lv)


def apply_verbosity_arg(arg: str) -> str:
    cur = get_verbosity_mode()

    # If no arg is given, keep current mode (do not change).
    if not (arg or "").strip():
        return cur

    lv = _normalize_verbosity_level_arg(arg)
    if lv is None:
        raise ValueError(tr("invalid verbosity"))
    return set_verbosity_mode(lv)


def _handle_cmd_reasoning(arg: str, *, tr: Any) -> bool:
    try:
        new_mode = apply_reasoning_arg(arg)
    except Exception:
        print(
            ":r [0|1|2|3|auto|minimal|xhigh]  (0=off, 1=low, 2=medium, 3=high; auto/minimal/xhigh)"
        )
        return True

    print("[mode] reasoning=%(mode)s" % {"mode": new_mode})
    return True


def _handle_cmd_verbosity(arg: str, *, tr: Any) -> bool:
    try:
        new_mode = apply_verbosity_arg(arg)
    except Exception:
        print(":v [0|1|2|3]  (0=off, 1=low, 2=medium, 3=high; no arg=keep)")
        return True

    print("[mode] verbosity=%(mode)s" % {"mode": new_mode})
    return True


def _handle_cmd_cd(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    a = (arg or "").strip()
    if not a:
        print(":cd <path>")
        return True

    try:
        prev = os.getcwd()
        expanded = os.path.expandvars(os.path.expanduser(a))
        target = os.path.abspath(expanded)

        if not os.path.isdir(target):
            print(
                "[cd] Directory does not exist: %(src)s -> %(dst)s"
                % {"src": a, "dst": target}
            )
            return True

        os.chdir(target)
        now = os.getcwd()

        # Record cwd change into message history + log.
        try:
            msg = {
                "role": "system",
                "content": _format_cwd_system_content(
                    event="cd",
                    path=now,
                    extra={"prev": prev, "src": a, "resolved": target},
                ),
            }
            _insert_cwd_system_message(messages_ref, msg)
            core.log_message(msg)
        except Exception:
            pass

        print("[cd] workdir = %(path)s" % {"path": now})
    except Exception as e:
        print("[cd error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})

    return True


def _handle_cmd_ls(arg: str, *, tr: Any) -> bool:
    target = (arg or "").strip() or "."

    try:
        expanded = os.path.expandvars(os.path.expanduser(target))
        has_glob = any(ch in expanded for ch in ("*", "?", "["))

        if has_glob:
            matches = glob.glob(expanded, recursive=True)
            if not matches:
                print(
                    "[ls] No matching paths: %(src)s -> %(expanded)s"
                    % {"src": target, "expanded": expanded}
                )
                return True

            items = []
            for p in matches:
                try:
                    p_exp = os.path.expandvars(os.path.expanduser(p))
                    p_abs = os.path.abspath(p_exp)
                    is_dir = os.path.isdir(p_abs)
                    size = os.path.getsize(p_abs) if os.path.isfile(p_abs) else 0
                except Exception:
                    p_abs = os.path.abspath(p)
                    is_dir = os.path.isdir(p_abs)
                    size = 0

                base = os.path.basename(p_abs.rstrip(os.sep)) or p_abs
                items.append(
                    (0 if is_dir else 1, base.lower(), base, p_abs, is_dir, size)
                )

            items.sort(key=lambda x: (x[0], x[1]))

            print("[ls] %(path)s" % {"path": expanded})
            for _, _, name, p_abs, is_dir, size in items:
                if is_dir:
                    print("  [D] %(name)s -> %(path)s" % {"name": name, "path": p_abs})
                else:
                    print(
                        "  [F] %(name)s (%(size)d bytes) -> %(path)s"
                        % {"name": name, "size": size, "path": p_abs}
                    )
            return True

        target_abs = os.path.abspath(expanded)
        if not os.path.isdir(target_abs):
            print(
                "[ls] Directory does not exist: %(src)s -> %(dst)s"
                % {"src": target, "dst": target_abs}
            )
            return True

        entries = []
        for name in os.listdir(target_abs):
            p = os.path.join(target_abs, name)
            try:
                st = os.stat(p)
                is_dir = os.path.isdir(p)
                size = st.st_size
            except Exception:
                is_dir = os.path.isdir(p)
                size = 0

            entries.append((0 if is_dir else 1, name.lower(), name, is_dir, size))

        entries.sort(key=lambda x: (x[0], x[1]))

        print("[ls] %(path)s" % {"path": target_abs})
        for _, _, name, is_dir, size in entries:
            if is_dir:
                print("  [D] %(name)s" % {"name": name})
            else:
                print("  [F] %(name)s (%(size)d bytes)" % {"name": name, "size": size})
    except Exception as e:
        print("[ls error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})

    return True


def _handle_cmd_logs(arg: str, *, core: Any, tr: Any) -> bool:
    show_all = False
    limit = 10

    a = (arg or "").strip()
    if a:
        low = a.lower()
        if low in ("--all", "-a", "all"):
            show_all = True
        else:
            try:
                limit = int(a)
            except Exception:
                print(
                    tr(
                        tr(
                            "[logs] Invalid argument: %(arg)r (specify all / --all / -a / number)"
                        )
                    )
                    % {"arg": a}
                )
                return True

    core.list_logs(limit=limit, show_all=show_all)
    return True


def _handle_cmd_tools(*, tr: Any) -> bool:
    try:
        tool_specs = tools.get_tool_specs() or []
        if not tool_specs:
            print("[tools] No tools loaded.")
            return True

        print("[tools] Loaded %(n)d tools" % {"n": len(tool_specs)})
        for spec in tool_specs:
            fn = (spec or {}).get("function") or {}
            name = fn.get("name") or "(unknown)"
            desc = (fn.get("description") or "").strip()
            if desc:
                print("- %(name)s: %(desc)s" % {"name": name, "desc": desc})
            else:
                print("- %(name)s" % {"name": name})
    except Exception as e:
        print(
            "[tools error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e}
        )

    return True


def _normalize_cp_mv_args(raw: str) -> tuple[list[str], bool, bool]:
    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        raise ValueError(tr("failed to parse arguments: %(err)s") % {"err": e}) from e

    if not items:
        raise ValueError(tr("missing arguments"))

    overwrite = False
    mkdirs = False
    paths: list[str] = []
    for item in items:
        low = item.lower()
        if low in ("-f", "--overwrite", "--force"):
            overwrite = True
            continue
        if low in ("-p", "--mkdirs", "--parents"):
            mkdirs = True
            continue
        paths.append(item)

    if len(paths) < 2:
        raise ValueError(tr("src and dst are required"))

    return paths, overwrite, mkdirs


def _resolve_copy_move_target(src: Path, dst_raw: str) -> Path:
    dst_expanded = os.path.expandvars(os.path.expanduser(dst_raw))
    dst = Path(dst_expanded)
    if dst.exists() and dst.is_dir():
        return dst / src.name
    if dst_raw.endswith((os.sep, "/", os.altsep or "")):
        return dst / src.name
    return dst


def _remove_existing_path(target: Path) -> None:
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink()


def _handle_cmd_cp(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(":cp <src> <dst> [-f|--overwrite] [-p|--mkdirs]")
        return True

    try:
        items, overwrite, mkdirs = _normalize_cp_mv_args(raw)
    except Exception as e:
        print("[cp error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True

    src_raw, dst_raw = items[0], items[1]
    try:
        from .tools.safe_file_ops_extras import ensure_within_workdir

        src = Path(ensure_within_workdir(src_raw))
        target = _resolve_copy_move_target(src, dst_raw)
        if target == src:
            print(
                "[cp] Source and destination are the same: %(path)s"
                % {"path": str(src)}
            )
            return True

        if src.is_dir():
            if target.exists():
                if not overwrite:
                    print(
                        "[cp] Destination already exists: %(path)s"
                        % {"path": str(target)}
                    )
                    return True
                _remove_existing_path(target)
            if mkdirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, target)
        else:
            if target.exists():
                if not overwrite:
                    print(
                        "[cp] Destination already exists: %(path)s"
                        % {"path": str(target)}
                    )
                    return True
                _remove_existing_path(target)
            if mkdirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            elif not target.parent.exists():
                print(
                    "[cp] Destination parent does not exist: %(path)s"
                    % {"path": str(target.parent)}
                )
                return True
            shutil.copy2(src, target)

        print("[cp] Copied: %(src)s -> %(dst)s" % {"src": str(src), "dst": str(target)})
        return True
    except Exception as e:
        print("[cp error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True


def _handle_cmd_mv(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(":mv <src> <dst> [-f|--overwrite] [-p|--mkdirs]")
        return True

    try:
        items, overwrite, mkdirs = _normalize_cp_mv_args(raw)
    except Exception as e:
        print("[mv error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True

    src_raw, dst_raw = items[0], items[1]
    try:
        from .tools.safe_file_ops_extras import ensure_within_workdir

        src = Path(ensure_within_workdir(src_raw))
        target = _resolve_copy_move_target(src, dst_raw)
        if target == src:
            print(
                "[mv] Source and destination are the same: %(path)s"
                % {"path": str(src)}
            )
            return True

        if target.exists():
            if not overwrite:
                print(
                    "[mv] Destination already exists: %(path)s" % {"path": str(target)}
                )
                return True
            _remove_existing_path(target)

        if mkdirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            print(
                "[mv] Destination parent does not exist: %(path)s"
                % {"path": str(target.parent)}
            )
            return True

        os.replace(src, target)
        print("[mv] Moved: %(src)s -> %(dst)s" % {"src": str(src), "dst": str(target)})
        return True
    except Exception as e:
        print("[mv error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True


def _handle_cmd_head(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(":head <path> [n]")
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print("[head error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True

    if not items:
        print(":head <path> [n]")
        return True

    lines = 20
    path_tokens: list[str] = []
    i = 0
    while i < len(items):
        tok = items[i]
        low = tok.lower()
        if low in ("-n", "--lines"):
            i += 1
            if i >= len(items):
                print(":head <path> [n]")
                return True
            try:
                lines = int(items[i])
            except Exception:
                print("[head] Invalid line count: %(n)r" % {"n": items[i]})
                return True
        elif not tok.startswith("-") and not path_tokens:
            path_tokens.append(tok)
        elif not tok.startswith("-") and path_tokens:
            try:
                lines = int(tok)
            except Exception:
                path_tokens.append(tok)
        else:
            path_tokens.append(tok)
        i += 1

    if not path_tokens:
        print(":head <path> [n]")
        return True

    path = " ".join(path_tokens)
    try:
        from .tools.read_file_tool import run_tool as read_file_tool

        content = read_file_tool({"filename": path, "head_lines": lines})
        if content.startswith("{"):
            try:
                res = json.loads(content)
            except Exception:
                res = None
            if isinstance(res, dict) and not res.get("ok", False):
                print(str(res.get("error") or res.get("stderr") or "[head] Failed."))
                return True
            if isinstance(res, dict):
                content = str(res.get("content") or "")
        if content:
            print(content, end="" if content.endswith("\n") else "\n")
        else:
            print("[head] Empty.")
        return True
    except Exception as e:
        print("[head error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True


def _handle_cmd_tail(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(":tail <path> [n]")
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print("[tail error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True

    if not items:
        print(":tail <path> [n]")
        return True

    lines = 20
    path_tokens: list[str] = []
    i = 0
    while i < len(items):
        tok = items[i]
        low = tok.lower()
        if low in ("-n", "--lines"):
            i += 1
            if i >= len(items):
                print(":tail <path> [n]")
                return True
            try:
                lines = int(items[i])
            except Exception:
                print("[tail] Invalid line count: %(n)r" % {"n": items[i]})
                return True
        elif not tok.startswith("-") and not path_tokens:
            path_tokens.append(tok)
        elif not tok.startswith("-") and path_tokens:
            try:
                lines = int(tok)
            except Exception:
                path_tokens.append(tok)
        else:
            path_tokens.append(tok)
        i += 1

    if not path_tokens:
        print(":tail <path> [n]")
        return True

    path = " ".join(path_tokens)
    try:
        from .tools.read_file_tool import run_tool as read_file_tool

        content = read_file_tool({"filename": path, "tail_lines": lines})
        if content.startswith("{"):
            try:
                res = json.loads(content)
            except Exception:
                res = None
            if isinstance(res, dict) and not res.get("ok", False):
                print(str(res.get("error") or res.get("stderr") or "[tail] Failed."))
                return True
            if isinstance(res, dict):
                content = str(res.get("content") or "")
        if content:
            print(content, end="" if content.endswith("\n") else "\n")
        else:
            print("[tail] Empty.")
        return True
    except Exception as e:
        print("[tail error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True


def _cwd_marker_prefix() -> str:
    # Used to detect/parse workdir markers in message history.
    return "[CWD] "


def _format_cwd_system_content(
    *,
    event: str,
    path: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {"event": str(event), "path": str(path)}
    if isinstance(extra, dict):
        payload.update(extra)
    return _cwd_marker_prefix() + json.dumps(payload, ensure_ascii=False)


def _insert_cwd_system_message(
    messages_ref: list[dict[str, Any]], msg: dict[str, Any]
) -> None:
    # Insert at the end of the leading system-message block.
    idx = 0
    while idx < len(messages_ref) and messages_ref[idx].get("role") == "system":
        idx += 1
    messages_ref.insert(idx, msg)


def _extract_last_cwd_from_messages(messages: list[dict[str, Any]]) -> str | None:
    prefix = _cwd_marker_prefix()
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "system":
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        if not content.startswith(prefix):
            continue
        tail = content[len(prefix) :].strip()
        try:
            obj = json.loads(tail)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        p = obj.get("path")
        if isinstance(p, str) and p.strip():
            return p
    return None


def _skills_marker_prefix() -> str:
    # Used to detect/remove skill injections in message history.
    return "[SKILL] "


def _format_skill_system_content(
    *,
    skill: dict[str, Any],
    doc: dict[str, Any],
    include_finish_skill: bool = False,
) -> str:
    name = str((skill or {}).get("name") or "(unknown)").strip()
    path = str((skill or {}).get("path") or "").strip()
    skill_md = str((skill or {}).get("skill_md") or "").strip()

    fm = (doc or {}).get("frontmatter")
    body = (doc or {}).get("body_markdown")
    if not isinstance(fm, dict):
        fm = {}
    if not isinstance(body, str):
        body = ""

    header_parts: list[str] = [f"{_skills_marker_prefix()}name={name}"]
    if path:
        header_parts.append(f"path={path}")
    if skill_md:
        header_parts.append(f"skill_md={skill_md}")

    allowed_tools = fm.get("allowed-tools")
    if allowed_tools is None:
        allowed_tools = (skill or {}).get("allowed_tools")
    if allowed_tools is not None:
        header_parts.append(f"allowed-tools={allowed_tools}")

    header = " ".join(header_parts)
    body_text = body.strip()
    exec_instructions = "\n\n" + _(
        "[Skill execution]\n"
        "This skill is intended to be run. Read the skill body carefully and follow the instructions.\n"
        "If the skill contains tasks, continue until they are complete.\n"
        "Use tools as needed.\n"
    )
    if include_finish_skill:
        exec_instructions += _(
            "When finished, always call `finish_skill` if available.\n"
        )
    if body_text:
        return header + "\n\n" + body_text + exec_instructions + "\n"
    return header + exec_instructions + "\n"


def _has_any_user_message(messages_ref: list[dict[str, Any]]) -> bool:
    for m in messages_ref or []:
        if isinstance(m, dict) and m.get("role") == "user":
            return True
    return False


def _trim_messages_after_last_user(messages_ref: list[dict[str, Any]]) -> bool:
    for idx in range(len(messages_ref) - 1, -1, -1):
        m = messages_ref[idx]
        if isinstance(m, dict) and m.get("role") == "user":
            del messages_ref[idx + 1 :]
            return True
    return False


def _clear_skill_messages(messages_ref: list[dict[str, Any]]) -> int:
    prefix = _skills_marker_prefix()
    before = len(messages_ref)
    messages_ref[:] = [
        m
        for m in messages_ref
        if not (
            isinstance(m, dict)
            and m.get("role") == "system"
            and isinstance(m.get("content"), str)
            and m.get("content").startswith(prefix)
        )
    ]
    return before - len(messages_ref)


def _handle_cmd_skills(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult:
    a = (arg or "").strip()
    if a.lower() in ("clear", "off", "unset", "reset"):
        removed = _clear_skill_messages(messages_ref)
        if removed <= 0:
            print("[skills] No active skill messages to clear.")
            return CommandResult()
        _persist_messages_with_warn(messages_ref, core=core, label="skills")
        print("[skills] Cleared %(n)d skill message(s)." % {"n": removed})
        return CommandResult()

    if a.lower() in ("active", "status", "show", "list"):
        prefix = _skills_marker_prefix()
        active = []
        for m in messages_ref or []:
            if not isinstance(m, dict):
                continue
            if m.get("role") != "system":
                continue
            content = m.get("content")
            if not isinstance(content, str):
                continue
            if not content.startswith(prefix):
                continue
            # Show header only (first line)
            line = content.splitlines()[0].strip()
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
            active.append(line)

        if not active:
            print("[skills] No active skills.")
            return CommandResult()

        print("[skills] Active skills: %(n)d" % {"n": len(active)})
        for i, line in enumerate(active, start=1):
            print("[%(i)d] %(line)s" % {"i": i, "line": line})
        return CommandResult()

    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask
        from uagent.tools.skills_list_tool import run_tool as skills_list_tool
        from uagent.tools.skills_load_tool import run_tool as skills_load_tool

        try:
            from uagent.tools import tools as loaded_tools
        except Exception:
            loaded_tools = None

        res_json = skills_list_tool(
            {
                "root_dir": "",
                "recursive": True,
                "include_invalid": True,
                "strict": False,
            }
        )
        items = json.loads(res_json)
        if not isinstance(items, list):
            items = []

        if not items:
            print("[skills] No skills found.")
            return CommandResult()

        selected_idx: int | None = None
        a_norm = unicodedata.normalize("NFKC", a).strip()
        # Check if arg is a number for direct selection
        if a_norm.isdigit():
            n = int(a_norm)
            if 1 <= n <= len(items):
                selected_idx = n - 1
            else:
                print("[skills] Out of range: %(n)d" % {"n": n})
                return CommandResult()

        # If not direct selection, show list and ask
        if selected_idx is None:
            print("[skills] Found %(n)d skills" % {"n": len(items)})
            for i, it in enumerate(items, start=1):
                if not isinstance(it, dict):
                    continue
                name = it.get("name") or "(unknown)"
                desc = it.get("description") or ""
                ok = bool(it.get("ok"))
                ok_mark = "OK" if ok else "WARN"
                print(
                    "[%(i)d] (%(ok)s) %(name)s: %(desc)s"
                    % {"i": i, "ok": ok_mark, "name": name, "desc": desc}
                )

            sel_msg = _(
                "Select a skill number to run. Enter c to cancel.\n"
                "Tip: :skills clear  (remove applied skills)\n"
                "Enter number:"
            )

            while selected_idx is None:
                sel_json = human_ask({"message": sel_msg})
                sel = json.loads(sel_json)
                user_reply = unicodedata.normalize(
                    "NFKC", (sel.get("user_reply") or "")
                ).strip()
                low = user_reply.lower()
                if low in ("c", "cancel"):
                    print("[skills] Cancelled.")
                    return CommandResult()
                if not user_reply.isdigit():
                    print("[skills] Please enter a number or c.")
                    continue
                n = int(user_reply)
                if n < 1 or n > len(items):
                    print("[skills] Out of range: %(n)d" % {"n": n})
                    continue
                selected_idx = n - 1

        skill = items[selected_idx]
        if not isinstance(skill, dict):
            print("[skills] Invalid selection.")
            return CommandResult()

        name = skill.get("name") or "(unknown)"
        skill_dir = skill.get("path")
        if not isinstance(skill_dir, str) or not skill_dir.strip():
            print("[skills] Selected skill has no path.")
            return CommandResult()

        confirm_msg = _(
            "Run this skill as a system-level instruction and keep it active in this session?\n\n"
            "Name: %(name)s\n"
            "Path: %(path)s\n\n"
            "Proceed? Enter y to run, or c to cancel."
        ) % {"name": name, "path": os.path.abspath(skill_dir)}

        conf_json = human_ask({"message": confirm_msg})
        conf = json.loads(conf_json)
        conf_reply = (conf.get("user_reply") or "").strip().lower()
        if conf_reply not in ("y", "yes"):
            print("[skills] Cancelled.")
            return CommandResult()

        doc_json = skills_load_tool({"skill_dir": skill_dir})
        doc = json.loads(doc_json)
        if not isinstance(doc, dict):
            raise ValueError("skills_load returned non-dict")

        try:
            tool_specs = (
                loaded_tools.get_tool_specs() if loaded_tools is not None else []
            )
        except Exception:
            tool_specs = []
        has_finish_skill = any(
            isinstance(spec, dict)
            and isinstance(spec.get("function"), dict)
            and spec["function"].get("name") == "finish_skill"
            for spec in (tool_specs or [])
        )
        content = _format_skill_system_content(
            skill=skill,
            doc=doc,
            include_finish_skill=has_finish_skill,
        )

        skill_system_msg = {"role": "system", "content": content}
        _insert_cwd_system_message(messages_ref, skill_system_msg)

        _persist_messages_with_warn(messages_ref, core=core, label="skills")
        print("[skills] Applied: %(name)s" % {"name": name})
        return CommandResult(run_llm=True)

    except Exception as e:
        print(
            "[skills error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e}
        )

    return CommandResult()


def _parse_clean_threshold(arg: str, *, tr: Any) -> int | None:
    threshold = 10
    a = (arg or "").strip()
    if not a:
        return threshold

    try:
        return int(a)
    except Exception:
        print(
            tr(
                "[clean] Invalid argument: %(arg)r (specify number=threshold; default is %(default)d)"
            )
            % {"arg": a, "default": threshold}
        )
        return None


def _collect_clean_targets(
    *,
    core: Any,
    threshold: int,
    tr: Any,
) -> tuple[bool, list[str], dict[str, int]]:
    try:
        log_files = core.find_log_files(exclude_current=False)
    except Exception as e:
        print(
            "[clean error] Failed to get log list: %(etype)s: %(err)s"
            % {"etype": type(e).__name__, "err": e}
        )
        return False, [], {}

    targets: list[str] = []
    counts: dict[str, int] = {}

    for p in log_files:
        try:
            msgs = core.load_conversation_from_log(p)
            non_system_count = max(0, len(msgs) - 1)
            counts[p] = non_system_count
            if non_system_count <= threshold:
                targets.append(p)
        except Exception as e:
            print(
                "[clean warn] Skipped (parse failed): %(path)s (%(etype)s: %(err)s)"
                % {"path": p, "etype": type(e).__name__, "err": e}
            )

    return True, targets, counts


def _confirm_clean_delete(
    *, core: Any, threshold: int, targets: list[str], tr: Any
) -> bool:
    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask

        cmd = ":clean"
        body_tpl = _(
            "will delete conversation log files (scheck_log_*.jsonl) from disk.\n"
            "Log dir: %(dir)s\n"
            "Rule: total user/assistant/tool messages excluding system <= %(threshold)d\n"
            "Targets: %(n)d\n\n"
            "Proceed? Enter y to run, or c to cancel."
        )
        body = (tr(body_tpl) if callable(tr) else body_tpl) % {
            "dir": getattr(core, "BASE_LOG_DIR", "(unknown)"),
            "threshold": threshold,
            "n": len(targets),
        }
        res_json = human_ask({"message": f"{cmd} {body}"})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        if user_reply not in ("y", "yes"):
            print("[clean] Cancelled.")
            return False
        return True
    except Exception as e:
        print(
            "[clean error] Confirmation failed: %(etype)s: %(err)s"
            % {"etype": type(e).__name__, "err": e}
        )
        return False


def _delete_clean_targets(targets: list[str], *, tr: Any) -> tuple[int, int]:
    deleted = 0
    failed = 0
    for p in targets:
        try:
            os.remove(p)
            deleted += 1
        except Exception as e:
            failed += 1
            print(
                "[clean warn] Delete failed: %(path)s (%(etype)s: %(err)s)"
                % {"path": p, "etype": type(e).__name__, "err": e}
            )

    return deleted, failed


def _handle_cmd_clean(arg: str, *, core: Any, tr: Any) -> bool:
    threshold = _parse_clean_threshold(arg, tr=tr)
    if threshold is None:
        return True

    ok, targets, counts = _collect_clean_targets(core=core, threshold=threshold, tr=tr)
    if not ok:
        return True

    if not targets:
        print(
            "[clean] No logs to delete (threshold=%(threshold)d).\nLog dir: %(dir)s"
            % {
                "threshold": threshold,
                "dir": getattr(core, "BASE_LOG_DIR", "(unknown)"),
            }
        )
        return True

    print(
        "[clean] Logs to delete (<= %(threshold)d msgs): %(n)d"
        % {"threshold": threshold, "n": len(targets)}
    )
    for p in targets:
        c = counts.get(p, -1)
        print(tr(" - (%(count)d msgs) %(path)s") % {"count": c, "path": p})

    if not _confirm_clean_delete(
        core=core, threshold=threshold, targets=targets, tr=tr
    ):
        return True

    deleted, failed = _delete_clean_targets(targets, tr=tr)
    print(
        "[clean] Done: deleted=%(deleted)d, failed=%(failed)d"
        % {"deleted": deleted, "failed": failed}
    )
    return True


def _inject_user_history_to_readline(messages: list[dict[str, Any]]) -> None:
    try:
        import readline

        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                readline.add_history(content.replace("\n", " "))
    except Exception:
        return


def _prepend_loaded_log_to_current(
    *,
    core: Any,
    source_log_path: str,
    tr: Any,
) -> None:
    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask

        cur_log = getattr(core, "LOG_FILE", None)
        if not isinstance(cur_log, str) or not cur_log:
            return

        cmd = ":load"
        body_tpl = _(
            "will overwrite the current session log file and prepend the loaded log (no backup).\n\n"
            "Current log: %(cur_log)s\n"
            "Source log: %(src_log)s\n\n"
            "Proceed? Enter y to run, or c to cancel."
        )
        body = (tr(body_tpl) if callable(tr) else body_tpl) % {
            "cur_log": cur_log,
            "src_log": source_log_path,
        }
        res_json2 = human_ask({"message": f"{cmd} {body}"})
        res2 = json.loads(res_json2)
        user_reply2 = (res2.get("user_reply") or "").strip().lower()
        if user_reply2 not in ("y", "yes"):
            print("[load] Prepend to current log was cancelled.")
            return

        loaded_lines: list[str] = []
        try:
            with open(source_log_path, encoding="utf-8") as f:
                loaded_lines = f.read().splitlines(True)
        except Exception as e:
            print(
                "[load warn] Failed to read source log: %(etype)s: %(err)s"
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            loaded_lines = []

        cur_lines: list[str] = []
        try:
            if os.path.exists(cur_log):
                with open(cur_log, encoding="utf-8") as f:
                    cur_lines = f.read().splitlines(True)
        except Exception as e:
            print(
                "[load warn] Failed to read current log: %(etype)s: %(err)s"
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            cur_lines = []

        marker = {
            "role": "system",
            "content": f"[LOG] :load prepend source={os.path.abspath(source_log_path)}",
        }
        marker_line = json.dumps(marker, ensure_ascii=False) + "\n"

        try:
            os.makedirs(os.path.dirname(cur_log) or ".", exist_ok=True)
            with open(cur_log, "w", encoding="utf-8") as f:
                f.write(marker_line)
                for ln in loaded_lines:
                    f.write(ln)
                for ln in cur_lines:
                    f.write(ln)
            print("[load] Prepended to current log: %(path)s" % {"path": cur_log})
        except Exception as e:
            print(
                "[load warn] Failed to rewrite current log: %(etype)s: %(err)s"
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            return
    except Exception as e:
        print(
            "[load error] Failed: %(etype)s: %(err)s"
            % {"etype": type(e).__name__, "err": e}
        )
        return


def _handle_cmd_rm(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(":rm <path|glob> [path|glob]")
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print("[rm error] Failed to parse arguments: %(err)s" % {"err": e})
        return True

    if not items:
        print(":rm <path|glob> [path|glob]")
        return True

    try:
        from uagent.tools.delete_file_tool import run_tool as delete_file_tool
        from uagent.tools.human_ask_tool import run_tool as human_ask

        preview_json = delete_file_tool(
            {
                "filename": items,
                "missing_ok": True,
                "dry_run": True,
                "allow_dir": True,
            }
        )
        preview = json.loads(preview_json)
        if not isinstance(preview, dict):
            print("[rm] Unexpected delete_file preview response.")
            return True

        if not preview.get("ok", False):
            print("[rm] Preview failed.")
            stderr = preview.get("stderr")
            if stderr:
                print(str(stderr))
            return True

        missing = [str(p) for p in (preview.get("missing") or []) if str(p).strip()]
        matches = [str(p) for p in (preview.get("matches") or []) if str(p).strip()]

        if not matches:
            print("[rm] No matching paths.")
            if missing:
                print("[rm] Missing:")
                for p in missing:
                    print(p)
            return True

        print("[rm] Candidates:")
        for p in matches:
            print(p)
        if missing:
            print("[rm] Missing:")
            for p in missing:
                print(p)

        confirm_msg = _(
            "Delete {count} path(s)?\n\n{paths}\n\nEnter y to proceed, or c to cancel."
        ).format(count=len(matches), paths="\n".join(matches))
        res_json = human_ask({"message": confirm_msg})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        cancelled = bool(res.get("cancelled", False))
        if cancelled or user_reply not in ("y", "yes"):
            print("[rm] Cancelled.")
            return True

        delete_json = delete_file_tool(
            {
                "filename": items,
                "missing_ok": True,
                "dry_run": False,
                "allow_dir": True,
                "confirmed": True,
            }
        )
        delete = json.loads(delete_json)
        if not isinstance(delete, dict):
            print("[rm] Unexpected delete_file response.")
            return True

        if delete.get("ok", False) and delete.get("deleted"):
            print(
                "[rm] Deleted %(count)d path(s)."
                % {"count": int(delete.get("count") or 0)}
            )
        else:
            print("[rm] Failed.")
            stderr = delete.get("stderr")
            if stderr:
                print(str(stderr))
        return True
    except Exception as e:
        print("[rm error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True


def _handle_cmd_load(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    if not arg:
        print(":load <index|path>")
        return True

    files = core.find_log_files(exclude_current=True)
    if arg.isdigit():
        idx = int(arg)
        if idx < 0 or idx >= len(files):
            print(tr("Specified index %(idx)d is out of range.") % {"idx": idx})
            return True
        target_path = files[idx]
    else:
        target_path = arg

    try:
        new_messages = core.load_conversation_from_log(target_path)
    except FileNotFoundError:
        print(tr("Log file not found: %(path)s") % {"path": target_path})
        return True
    except Exception as e:
        print("[load error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True

    new_messages = insert_tools_system_message(new_messages, core=core)
    messages_ref.clear()
    messages_ref.extend(new_messages)

    # Auto-restore cwd from the loaded log (no confirmation).
    try:
        target_cwd = _extract_last_cwd_from_messages(new_messages)
        if (
            isinstance(target_cwd, str)
            and target_cwd.strip()
            and os.path.isdir(target_cwd)
        ):
            prev = os.getcwd()
            os.chdir(target_cwd)
            now = os.getcwd()

            # Record the cwd change triggered by :load.
            try:
                msg = {
                    "role": "system",
                    "content": _format_cwd_system_content(
                        event="load",
                        path=now,
                        extra={"prev": prev, "log": os.path.abspath(target_path)},
                    ),
                }
                _insert_cwd_system_message(messages_ref, msg)
                core.log_message(msg)
            except Exception:
                pass

            print("[load] workdir = %(path)s" % {"path": now})
    except Exception as e:
        print(
            "[load warn] Failed to chdir from loaded log: %(etype)s: %(err)s"
            % {"etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )

    _inject_user_history_to_readline(new_messages)

    print("Loaded log: %(path)s" % {"path": target_path})
    print("Conversation message count: %(n)d" % {"n": len(messages_ref)})

    _prepend_loaded_log_to_current(core=core, source_log_path=target_path, tr=tr)
    return True


def _persist_messages_with_warn(
    messages: list[dict[str, Any]], *, core: Any, label: str
) -> None:
    try:
        cb = get_callbacks()
        rewrite_current_log = getattr(cb, "rewrite_current_log_from_messages", None)
        if rewrite_current_log is not None:
            rewrite_current_log(messages)
        else:
            core.rewrite_current_log_from_messages(messages)
    except Exception as e:
        print(
            "[%(label)s warn] Failed to rewrite current log: %(etype)s: %(err)s"
            % {"label": label, "etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )


def _handle_cmd_shrink(
    arg: str, messages_ref: list[dict[str, Any]], *, core: Any
) -> bool:
    keep_last = 40
    if arg:
        try:
            keep_last = int(arg)
        except Exception:
            print(
                _(
                    _(
                        "[shrink error] Failed to parse as int: %(arg)r -> keep last %(keep)d"
                    )
                )
                % {"arg": arg, "keep": keep_last}
            )

    new_messages = core.shrink_messages(messages_ref, keep_last=keep_last)
    messages_ref.clear()
    messages_ref.extend(new_messages)
    _persist_messages_with_warn(messages_ref, core=core, label="shrink")
    return True


def _handle_cmd_shrink_llm(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
) -> bool:
    keep_last = 20
    if arg:
        try:
            keep_last = int(arg)
        except Exception:
            print(
                _(
                    "[shrink_llm error] Failed to parse as int: %(arg)r -> keep last %(keep)d"
                )
                % {"arg": arg, "keep": keep_last}
            )

    new_messages = core.compress_history_with_llm(
        client=client,
        depname=depname,
        messages=messages_ref,
        keep_last=keep_last,
    )
    messages_ref.clear()
    messages_ref.extend(new_messages)
    _persist_messages_with_warn(messages_ref, core=core, label="shrink_llm")
    return True


def _handle_cmd_mem_list(*, tr: Any) -> bool:
    records = personal_long_memory.load_long_memory_records()
    if not records:
        print("No long-term memory entries.")
        return True

    print("Long-term memory entries:")
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            import time as _time

            dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        else:
            dt = "(no-ts)"
        note = str(rec.get("note", ""))
        print("[%(idx)s] %(dt)s  %(note)s" % {"idx": idx, "dt": dt, "note": note})
    return True


def _handle_cmd_mem_del(arg: str, *, tr: Any) -> bool:
    if not arg:
        print(":mem-del <index>")
        return True

    try:
        idx = int(arg)
    except Exception:
        print("[mem-del error] Failed to parse index as int: %(arg)r" % {"arg": arg})
        return True

    if personal_long_memory.delete_long_memory_entry(idx):
        print("Deleted long-term memory entry [%(idx)d]." % {"idx": idx})
    else:
        print("[mem-del] Failed to delete index=%(idx)d." % {"idx": idx})
    return True


def _handle_cmd_shared_mem_list(*, tr: Any) -> bool:
    if not shared_memory.is_enabled():
        print(
            _(
                "Shared long-term memory is not enabled (UAGENT_SHARED_MEMORY_FILE is not set)."
            )
        )
        return True

    records = shared_memory.load_shared_memory_records()
    if not records:
        print("No shared long-term memory entries.")
        return True

    import time as _time

    print("Shared long-term memory entries:")
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        else:
            dt = "(no-ts)"
        note = str(rec.get("note", ""))
        print("[%(idx)s] %(dt)s  %(note)s" % {"idx": idx, "dt": dt, "note": note})

    return True


def _handle_cmd_profile_show(*, tr: Any) -> bool:
    from .profile_manager import load_profile
    profile = load_profile()
    if not profile.get("environment") and not profile.get("preferences") and not profile.get("constraints"):
        print(tr("No user profile data found."))
        return True

    print(tr("User Profile:"))
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return True


def _handle_cmd_profile_clear(*, tr: Any) -> bool:
    from .profile_manager import get_profile_file_path
    path = get_profile_file_path()
    if os.path.exists(path):
        try:
            os.remove(path)
            print(tr("User profile cleared successfully."))
        except Exception as e:
            print(f"[profile-clear error] {type(e).__name__}: {e}")
    else:
        print(tr("No user profile file found to clear."))
    return True


def _handle_cmd_shared_mem_del(arg: str, *, tr: Any) -> bool:
    if not arg:
        print(":shared-mem-del <index>")
        return True

    if not shared_memory.is_enabled():
        print(
            _(
                "Shared long-term memory is not enabled (UAGENT_SHARED_MEMORY_FILE is not set)."
            )
        )
        return True

    try:
        idx = int(arg)
    except Exception:
        print(
            "[shared-mem-del error] Failed to parse index as int: %(arg)r"
            % {"arg": arg}
        )
        return True

    records = shared_memory.load_shared_memory_records()
    if idx < 0 or idx >= len(records):
        print("[shared-mem-del] Failed to delete index=%(idx)d." % {"idx": idx})
        return True

    try:
        records.pop(idx)
        path = shared_memory.get_shared_memory_file()
        if not path:
            print("[shared-mem-del] Failed to delete index=%(idx)d." % {"idx": idx})
            return True

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(
            "[shared-mem-del error] %(etype)s: %(err)s"
            % {"etype": type(e).__name__, "err": e}
        )
        return True

    print("Deleted shared long-term memory entry [%(idx)d]." % {"idx": idx})
    return True


def format_help(*, core: Any) -> str:
    """Format help text for interactive :help.

    Keep this as the single source of truth for command help.
    """

    tr = getattr(core, "tr", tr_)
    sentinel = getattr(core, "MULTI_INPUT_SENTINEL", '"""end')

    lines = [
        "Available commands:",
        "  :help                 " + tr("Show this help"),
        '  (in multiline input) """retry  ' + tr("Restart input from the beginning"),
        "  :logs / :list         " + tr("Show log file list"),
        "  :cd <path>            "
        + tr(
            "Change workdir without confirmation (e.g. :cd .. / :cd ~ / :cd C:\\path / :cd /)"
        ),
        "  :ls [path]            "
        + tr("List directory entries (e.g. :ls / :ls .. / :ls ~ / :ls C:\\path)"),
        "  :tools                " + tr("List loaded tools"),
        "  :env show [KEY]       "
        + "Show UAGENT_* env vars; KEY names are masked; :env show UAGENT_*",
        "  :env set/unset/save   " + tr("Manage UAGENT_* env vars and save .env.sec"),
        "  :skills [cmd]         "
        + tr("Manage/apply skills (e.g. :skills / :skills active / :skills clear)"),
        "  :load <idx|path>      "
        + tr("Load a past log (overwrites current conversation history)"),
        tr(
            "                       Note: after running, you will be asked for confirmation; choosing 'y' prepends the loaded log into the current session log file (overwrite, no backup)."
        ),
        "  :clean [N]            "
        + tr(
            "Delete conversation logs (scheck_log_*.jsonl) where the count of user/assistant/tool messages (excluding system) is <= N (default=10)"
        ),
        "  :shrink [N]           "
        + tr(
            "Shrink conversation history (keep last N non-system messages; default=40)"
        ),
        "  :shrink_llm [N]       "
        + tr(
            "Shrink history via LLM summarization (summarize older history into 1 system message; keep last N raw; default=20)"
        ),
        "  :mem-list             " + tr("List long-term memory notes"),
        "  :mem-del <index>      "
        + tr("Delete a long-term memory note by index (see :mem-list)"),
        "  :profile              " + tr("Show the learned user profile (environment, preferences, constraints)"),
        "  :profile-clear        " + tr("Clear the learned user profile data"),
        "  :cp <src> <dst>       "
        + tr("Copy file or directory (supports -f/--overwrite and -p/--mkdirs)"),
        "  :mv <src> <dst>       "
        + tr("Move file or directory (supports -f/--overwrite and -p/--mkdirs)"),
        "  :head <path> [n]      "
        + tr("Show the first n lines of a file (default=20)"),
        "  :tail <path> [n]      " + tr("Show the last n lines of a file (default=20)"),
        "  :rm <path|glob>       "
        + tr("Delete file(s)/directory(ies) with preview + confirm"),
        "  :r [0|1|2|3|auto|minimal|xhigh]  "
        + tr("Set reasoning mode (0=off, 1=low, 2=medium, 3=high; auto/minimal/xhigh)"),
        "  :v [0|1|2|3]          "
        + tr("Set verbosity mode (0=off, 1=low, 2=medium, 3=high; no arg=keep)"),
        "  :exit / :quit         " + tr("Exit"),
        "",
        "Hints:",
        tr("  - Enter a line that is just 'f' to enter multiline input mode."),
        tr(
            "  - To end multiline input mode, enter a line that is exactly %(sentinel)s."
        )
        % {"sentinel": sentinel},
    ]

    # Normalize indentation for command lines (translations may add extra leading whitespace).
    norm_lines = []
    for ln in lines:
        s = str(ln)
        stripped = s.lstrip()
        if stripped.startswith(":"):
            s = "  " + stripped
        norm_lines.append(s)

    return "\n".join(norm_lines)


def _uagent_env_names(prefix: str = "UAGENT_") -> list[str]:
    keys = set(get_known_uagent_env_keys(prefix))
    keys.update(
        k
        for k in os.environ
        if k.startswith(prefix) and not _is_placeholder_uagent_key(k)
    )
    return sorted(keys, key=str.lower)


def _uagent_format_env_value(name: str, value: str) -> str:
    if "KEY" in name.upper():
        return "***"
    return value


def _handle_cmd_env(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        for key in _uagent_env_names():
            print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print("[env error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e})
        return True

    if not items:
        for key in _uagent_env_names():
            print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    sub = items[0].lower()
    if sub in ("show", "list"):
        if len(items) == 1:
            for key in _uagent_env_names():
                print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
            return True

        query = items[1]
        keys = [k for k in _uagent_env_names() if k.lower() == query.lower()]
        if not keys:
            keys = [
                k for k in _uagent_env_names() if k.lower().startswith(query.lower())
            ]
        if not keys:
            print("[env] Not found: %(key)s" % {"key": query})
            return True
        if len(keys) > 1:
            print("[env] Ambiguous: %(key)s" % {"key": query})
            for key in keys:
                print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
            return True
        key = keys[0]
        print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    if sub == "set":
        if len(items) < 3:
            print(":env set KEY VALUE")
            return True
        key = items[1]
        value = " ".join(items[2:])
        os.environ[key] = value
        print("[env] Set %(key)s" % {"key": key})
        return True

    if sub == "unset":
        if len(items) < 2:
            print(":env unset KEY")
            return True
        key = items[1]
        os.environ.pop(key, None)
        print("[env] Unset %(key)s" % {"key": key})
        return True

    if sub == "save":
        try:
            from .runtime_env import save_uagent_envsec

            sec_path = save_uagent_envsec()
            print("[env] Saved .env.sec: %(path)s" % {"path": str(sec_path)})
        except Exception as e:
            print(
                "[env error] %(etype)s: %(err)s" % {"etype": type(e).__name__, "err": e}
            )
        return True

    print(":env show [KEY] / :env set KEY VALUE / :env unset KEY / :env save")
    return True


def handle_command(
    line: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
) -> bool | CommandResult:
    """コマンド行(:help, :logs, :load ...)を処理する

    戻り値: False を返すとメインループ終了(:exit / :quit)。
    CommandResult(run_llm=True) を返すと、コマンド処理後に LLM を実行する。
    """
    tr = getattr(core, "tr", tr_)

    line = line.lstrip(":").strip()
    if not line:
        return True

    parts = line.split(maxsplit=1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("help", "h", "?"):
        core.print_help()
        return True

    if cmd in ("r", "reasoning"):
        return _handle_cmd_reasoning(arg, tr=tr)

    if cmd in ("v", "verbosity"):
        return _handle_cmd_verbosity(arg, tr=tr)

    if cmd == "cd":
        return _handle_cmd_cd(arg, messages_ref, core=core, tr=tr)

    if cmd == "ls":
        return _handle_cmd_ls(arg, tr=tr)

    if cmd in ("logs", "list"):
        return _handle_cmd_logs(arg, core=core, tr=tr)

    if cmd == "tools":
        return _handle_cmd_tools(tr=tr)

    if cmd == "env":
        return _handle_cmd_env(arg, tr=tr)

    if cmd == "skills":
        return _handle_cmd_skills(arg, messages_ref, client, depname, core=core, tr=tr)

    if cmd == "clean":
        return _handle_cmd_clean(arg, core=core, tr=tr)

    if cmd == "load":
        return _handle_cmd_load(arg, messages_ref, core=core, tr=tr)

    if cmd == "shrink":
        return _handle_cmd_shrink(arg, messages_ref, core=core)

    if cmd == "shrink_llm":
        return _handle_cmd_shrink_llm(arg, messages_ref, client, depname, core=core)

    if cmd == "mem-list":
        return _handle_cmd_mem_list(tr=tr)

    if cmd == "mem-del":
        return _handle_cmd_mem_del(arg, tr=tr)

    if cmd in ("profile", "profile-show"):
        return _handle_cmd_profile_show(tr=tr)

    if cmd == "profile-clear":
        return _handle_cmd_profile_clear(tr=tr)

    if cmd == "cp":
        return _handle_cmd_cp(arg, tr=tr)

    if cmd == "mv":
        return _handle_cmd_mv(arg, tr=tr)

    if cmd == "head":
        return _handle_cmd_head(arg, tr=tr)

    if cmd == "tail":
        return _handle_cmd_tail(arg, tr=tr)

    if cmd == "rm":
        return _handle_cmd_rm(arg, tr=tr)

    if cmd in ("exit", "quit"):
        print(tr("Exiting."))
        return False

    print(tr("Unknown command: :%(cmd)s") % {"cmd": cmd})
    return True


def load_agents_md() -> str:
    """起動ディレクトリに AGENTS.md があれば内容を返す。"""
    agents_path = os.path.join(os.getcwd(), "AGENTS.md")
    if not os.path.isfile(agents_path):
        return ""

    if getattr(load_agents_md, "_loaded", False):
        return ""

    try:
        from tools.read_file_tool import run_tool as read_file

        content = read_file({"filename": agents_path})
        obj = json.loads(content)
        if obj.get("ok"):
            setattr(load_agents_md, "_loaded", True)
            return str(obj.get("content", ""))
        return ""
    except Exception:
        return ""


def _use_gpt54_lightweight_tools_prompt() -> bool:
    # Keep this in sync with provider/model resolution used by CLI/runtime.
    # Use canonical *_DEPNAME envs only.
    depname = (
        (
            env_get("UAGENT_AZURE_DEPNAME")
            or env_get("UAGENT_OPENAI_DEPNAME")
            or env_get("UAGENT_OPENROUTER_DEPNAME")
            or ""
        )
        .strip()
        .lower()
    )
    use_responses_api = (env_get("UAGENT_RESPONSES", "") or "").strip().lower() in (
        "1",
        "true",
    )

    if not use_responses_api:
        return False
    model = (depname or "").strip().lower()
    marker = "gpt-5."
    idx = model.find(marker)
    if idx < 0:
        return False
    tail = model[idx + len(marker) :]
    digits = []
    for ch in tail:
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if not digits:
        return False
    try:
        minor = int("".join(digits))
    except Exception:
        return False
    return minor >= 4


def build_lightweight_tools_system_prompt() -> str:
    return "\n".join(
        [
            "[Available Tools]",
            "A large set of tools may be available in this environment.",
            "Do not assume that every tool definition is already loaded in the current request.",
            "When tool use is needed, first reason about the category of tool required and use only the minimum relevant tool surface.",
            "If tool details are unavailable, avoid inventing parameters or functions.",
        ]
    )


def _use_tools_system_prompt() -> bool:
    use_tool = (env_get("UAGENT_USE_TOOL") or "").strip().lower()
    if use_tool in ("0", "false", "no", "off"):
        return False
    v = (env_get("UAGENT_SEND_TOOLS_PROMPT") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def build_initial_messages(*, core: Any) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    system_msg = {"role": "system", "content": core.SYSTEM_PROMPT}
    messages.append(system_msg)
    core.log_message(system_msg)

    if _use_tools_system_prompt():
        if _use_gpt54_lightweight_tools_prompt():
            tools_prompt = build_lightweight_tools_system_prompt()
        else:
            tool_specs = tools.get_tool_specs()
            tools_prompt = core.build_tools_system_prompt(tool_specs)
        tools_system_msg = {"role": "system", "content": tools_prompt}

        messages.append(tools_system_msg)
        core.log_message(tools_system_msg)

    # Record startup cwd into the message history + log.
    try:
        cwd = os.getcwd()
        cwd_msg = {
            "role": "system",
            "content": _format_cwd_system_content(event="startup", path=cwd),
        }
        _insert_cwd_system_message(messages, cwd_msg)
        core.log_message(cwd_msg)
    except Exception:
        pass

    return messages


def insert_tools_system_message(
    messages: list[dict[str, Any]],
    *,
    core: Any,
) -> list[dict[str, Any]]:
    if not _use_tools_system_prompt():
        return messages

    if _use_gpt54_lightweight_tools_prompt():
        tools_prompt = build_lightweight_tools_system_prompt()
    else:
        tool_specs = tools.get_tool_specs()
        tools_prompt = core.build_tools_system_prompt(tool_specs)
    tools_system_msg = {"role": "system", "content": tools_prompt}

    if messages and messages[0].get("role") == "system":
        new_messages = [messages[0], tools_system_msg] + messages[1:]
    else:
        new_messages = [tools_system_msg] + messages

    core.log_message(tools_system_msg)
    return new_messages


def build_long_memory_system_message(long_mem_raw: Any) -> dict[str, Any]:
    if not long_mem_raw:
        return {}

    max_chars = 4000

    header = _(
        "The bullet points listed below are excerpts from this user's long-term memory (persistent memos). "
        "Use them as background information about the user. "
        "However, always prioritize newly provided information in the conversation, and if it contradicts older information, adopt the latest information.\n\n"
    )

    body_lines: list[str] = []

    try:
        if isinstance(long_mem_raw, list):
            for rec in long_mem_raw:
                if isinstance(rec, dict):
                    text = (
                        rec.get("summary")
                        or rec.get("text")
                        or rec.get("content")
                        or rec.get("memory")
                        or json.dumps(rec, ensure_ascii=False)
                    )
                else:
                    text = str(rec)

                text = str(text).replace("\r\n", " ").replace("\n", " ").strip()
                if not text:
                    continue

                body_lines.append(f"- {text}")
                candidate = header + "\n".join(body_lines)
                if len(candidate) > max_chars:
                    body_lines.append("...(truncated: long-term memory is too long)...")
                    break
        else:
            text = str(long_mem_raw).strip()
            if text:
                body_lines.append(text)
    except Exception:
        fallback = header + json.dumps(long_mem_raw, ensure_ascii=False)
        content = fallback[:max_chars]
    else:
        content = header + "\n".join(body_lines)
        if len(content) > max_chars:
            content = (
                content[:max_chars]
                + "\n...(truncated: long-term memory is too long)..."
            )

    return {"role": "system", "content": content}


def append_result_to_outfile(text: str) -> None:
    """UAGENT_OUTFILE が指定されていれば、アシスタント最終出力を追記する。"""
    out_path = env_get("UAGENT_OUTFILE")
    if not out_path:
        return

    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
    except Exception:
        return
