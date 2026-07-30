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
        log_message=getattr(core, "log_message", None),
        prompt_history_append=getattr(core, "prompt_history_append", None),
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
        is_auto_pilot_active=(
            (lambda: getattr(core, "auto_pilot_active", False))
            if hasattr(core, "auto_pilot_active")
            else None
        ),
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
    r"(?P<path>(?:[A-Za-z]:\\|\\\\|\.\/|\.\\)?(?:\"[^\"]+\"|'[^']+'|[^\s\"']+\.(?:png|jpg|jpeg|gif|webp)))",
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

    mt, mime_subtype = mimetypes.guess_type(str(p))
    mime_type = mt or "application/octet-stream"

    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def provider_allows_chat_vision(
    provider: str,
    *,
    use_responses_api: bool | None = None,
    model_id: str | None = None,
) -> bool:
    """Return True if main-chat image auto-attach is allowed for this provider.

    CHAT_VISION_PROVIDERS (openai/azure/openrouter/grok/claude/gemini/vertexai)
    already convert multimodal content at the provider layer and do not require
    UAGENT_RESPONSES.  Other RESPONSES_PROVIDERS still need Responses enabled.

    When ``model_id`` is given (or resolvable from env) and llmcapa knows the
    model, vision/image-input support is required in addition to provider gating.
    Unknown models keep the provider-level allow decision.
    """
    from .providers.provider_caps import CHAT_VISION_PROVIDERS, RESPONSES_PROVIDERS
    from .llmcapa_util import supports_vision, current_model

    prov = (provider or "").strip().lower()
    if use_responses_api is None:
        use_responses_api = (env_get("UAGENT_RESPONSES") or "").strip().lower() in (
            "1",
            "true",
        )

    if prov in CHAT_VISION_PROVIDERS:
        provider_ok = True
    else:
        provider_ok = bool(use_responses_api) and prov in RESPONSES_PROVIDERS
    if not provider_ok:
        return False

    mid = (model_id or "").strip() or current_model(prov)
    if not mid:
        return True
    vision = supports_vision(mid, prov, default=None)
    if vision is None:
        return True
    return bool(vision)


def build_multimodal_user_message(
    text: str,
    image_paths: list[str],
    *,
    provider: str,
    use_responses_api: bool | None = None,
    max_bytes: int = 10_000_000,
) -> dict[str, Any]:
    """Build a user message with embedded local images for the given provider.

    Formats by provider path:
    - gemini/vertexai: content stays a string; images go in attachments
    - Responses API: input_image parts (image_url as string data URL)
    - Chat Completions / Claude / Grok: image_url parts (image_url as {url})
    """
    from .providers.provider_caps import RESPONSES_PROVIDERS

    prov = (provider or "").strip().lower()
    if use_responses_api is None:
        use_responses_api = (env_get("UAGENT_RESPONSES") or "").strip().lower() in (
            "1",
            "true",
        )

    text_s = text if isinstance(text, str) else ("" if text is None else str(text))
    paths = [p for p in (image_paths or []) if isinstance(p, str) and p.strip()]

    # Gemini / Vertex AI: provider layer only reads message["attachments"].
    if prov in ("gemini", "vertexai"):
        attachments: list[dict[str, Any]] = []
        warn_bits: list[str] = []
        for path in paths:
            try:
                data_url = image_file_to_data_url(path, max_bytes=max_bytes)
                attachments.append(
                    {
                        "type": "image",
                        "data_url": data_url,
                        "path": path,
                        "saved_path": path,
                    }
                )
            except Exception as e:
                warn_bits.append(
                    "[WARN] "
                    + (
                        tr("Failed to attach image: %(path)s (%(etype)s: %(err)s)")
                        % {
                            "path": path,
                            "etype": type(e).__name__,
                            "err": e,
                        }
                    )
                )
        content = text_s
        if warn_bits:
            sep = "\n\n"
            nl = "\n"
            content = (content.rstrip() + sep if content else "") + nl.join(warn_bits)
        msg: dict[str, Any] = {"role": "user", "content": content}
        if attachments:
            msg["attachments"] = attachments
        return msg

    use_responses_parts = bool(use_responses_api) and prov in RESPONSES_PROVIDERS
    parts: list[dict[str, Any]] = [{"type": "text", "text": text_s}]
    for path in paths:
        try:
            data_url = image_file_to_data_url(path, max_bytes=max_bytes)
            if use_responses_parts:
                # Responses API expects input_image with image_url as a string.
                parts.append({"type": "input_image", "image_url": data_url})
            else:
                # Chat Completions / Claude / Grok multimodal shape.
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        except Exception as e:
            parts.append(
                {
                    "type": "text",
                    "text": "[WARN] "
                    + (
                        tr("Failed to attach image: %(path)s (%(etype)s: %(err)s)")
                        % {
                            "path": path,
                            "etype": type(e).__name__,
                            "err": e,
                        }
                    ),
                }
            )
    return {"role": "user", "content": parts}


def try_open_images_from_text(text: str) -> None:
    """Deprecated no-op: assistant-text image auto-open was removed."""
    return


def parse_startup_args() -> tuple[dict[str, Any], list[str]]:
    # ``uag realtime`` is a startup mode, rather than a normal initial file.
    # Remove it before argparse so existing positional-file behavior is unchanged.
    realtime = False
    argv = list(sys.argv[1:])
    if argv and argv[0].lower() == "realtime":
        realtime = True
        argv.pop(0)
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
    parser.add_argument(
        "--tool-genre-mask",
        type=int,
        default=None,
        help=_(
            "Tool genre bitmask (1=basic,2=comm,4=office,8=devel,16=iot,32=exec,64=external,128=media,256=file,512=index,1023=all). Skips the interactive genre prompt when specified."
        ),
    )
    parser.add_argument(
        "--use-tool",
        dest="use_tool",
        action="store_true",
        default=None,
        help=_("Enable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--no-use-tool",
        dest="use_tool",
        action="store_false",
        default=None,
        help=_("Disable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--inject-message",
        "-M",
        dest="inject_message",
        default=None,
        help=_(
            "Inject a message into the LLM at startup and exit after completion. Implies --non-interactive."
        ),
    )
    parser.add_argument(
        "--enable-tool",
        dest="enable_tools",
        action="append",
        default=None,
        help=_(
            "Enable a specific tool by name at startup. Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--plugin-dir",
        dest="plugin_dirs",
        action="append",
        default=None,
        help=_("Load a plugin from a directory (can be specified multiple times)."),
    )
    args, unknown = parser.parse_known_args(argv)
    parsed = vars(args)
    parsed["realtime"] = realtime
    return parsed, unknown


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

_REASONING_LEVELS = ["off", "auto", "minimal", "low", "medium", "high", "xhigh", "max"]
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
    if a in ("4", "xhigh", "xh", "x-high"):
        return "xhigh"
    if a in ("5", "max", "m"):
        return "max"

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


_REASONING_HISTORY: list[str] = ["medium"]
# 表示専用 on/off フラグ。
# `:r` (引数なしトグル) はこのフラグだけを切り替え、API への reasoning 要求には影響しない。
# `:r off` / `:r medium` など値指定は set_reasoning_mode() 経由でこのフラグも同時更新する。
_DISPLAY_REASONING: bool = True


def get_display_reasoning() -> bool:
    """Return whether reasoning content should be displayed to the user."""
    return _DISPLAY_REASONING


def apply_reasoning_arg(arg: str) -> str:
    global _REASONING_HISTORY, _DISPLAY_REASONING
    lv = _normalize_reasoning_level_arg(arg)
    if lv is None and (arg or "").strip():
        # invalid (non-empty)
        raise ValueError(tr("invalid reasoning"))

    # No arg given: toggle display only (do not touch env var / API reasoning)
    if lv is None:
        _DISPLAY_REASONING = not _DISPLAY_REASONING
        status = "on" if _DISPLAY_REASONING else "off"
        print(_("[display] reasoning display=%(mode)s") % {"mode": status})
        return get_reasoning_mode()

    # Value given: set both env var and display flag
    _DISPLAY_REASONING = lv != "off"
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
            _(
                ":r [0|1|2|3|auto|minimal|xhigh]  (0=off, 1=low, 2=medium, 3=high; auto/minimal/xhigh)"
            )
        )
        return True

    print(_("[mode] reasoning=%(mode)s") % {"mode": new_mode})
    return True


def _handle_cmd_verbosity(arg: str, *, tr: Any) -> bool:
    try:
        new_mode = apply_verbosity_arg(arg)
    except Exception:
        print(_(":v [0|1|2|3]  (0=off, 1=low, 2=medium, 3=high; no arg=keep)"))
        return True

    print(_("[mode] verbosity=%(mode)s") % {"mode": new_mode})
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
        print(_(":cd <path>"))
        return True

    try:
        prev = os.getcwd()
        expanded = os.path.expandvars(os.path.expanduser(a))
        target = os.path.abspath(expanded)

        if not os.path.isdir(target):
            print(
                _("[cd] Directory does not exist: %(src)s -> %(dst)s")
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

        print(_("[cd] workdir = %(path)s") % {"path": now})
    except Exception as e:
        print(
            _("[cd error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )

    return True


def _handle_cmd_reload(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    """Reload project instruction files (CLAUDE.md / AGENTS.md) for current workdir.

    Only loads files that haven't been loaded before in this session.
    Skips the interactive prompt; new files are auto-loaded.
    """
    try:
        from .runtime.runtime_instructions import reload_instruction_files

        instructions = reload_instruction_files(workdir=os.getcwd())
        if not instructions:
            print(tr("[reload] No new instruction files found."))
            return True

        for instr in instructions:
            msg = {"role": "system", "content": instr}
            messages_ref.append(msg)
            core.log_message(msg)

        print(
            tr("[reload] Loaded %(count)d new instruction file(s).")
            % {"count": len(instructions)}
        )
    except Exception as e:
        print(
            tr("[reload error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )

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
                    tr("[ls] No matching paths: %(src)s -> %(expanded)s")
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

            print(tr("[ls] %(path)s") % {"path": expanded})
            for _ord, _key, name, p_abs, is_dir, size in items:
                if is_dir:
                    print(
                        tr("  [D] %(name)s -> %(path)s") % {"name": name, "path": p_abs}
                    )
                else:
                    print(
                        tr("  [F] %(name)s (%(size)d bytes) -> %(path)s")
                        % {"name": name, "size": size, "path": p_abs}
                    )
            return True

        target_abs = os.path.abspath(expanded)
        if not os.path.isdir(target_abs):
            print(
                tr("[ls] Directory does not exist: %(src)s -> %(dst)s")
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

        print(tr("[ls] %(path)s") % {"path": target_abs})
        for _ord, _key, name, is_dir, size in entries:
            if is_dir:
                print(tr("  [D] %(name)s") % {"name": name})
            else:
                print(
                    tr("  [F] %(name)s (%(size)d bytes)") % {"name": name, "size": size}
                )
    except Exception as e:
        print(
            tr("[ls error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )

    return True


def _handle_cmd_logs(arg: str, *, core: Any, tr: Any) -> bool:
    show_all = False
    limit = 10
    export_pdf_index = None

    a = (arg or "").strip()
    if a:
        parts = a.split()
        cmd = parts[0].lower()

        if cmd == "pdf":
            if len(parts) >= 2:
                try:
                    export_pdf_index = int(parts[1])
                except ValueError:
                    print(_("[logs] Invalid PDF index: '%(idx)s'") % {"idx": parts[1]})
                    return True
            else:
                print(_("[logs] Usage: :logs pdf <index> [output_path]"))
                return True
        elif cmd in ("--all", "-a", "all"):
            show_all = True
        else:
            try:
                limit = int(cmd)
            except Exception:
                print(
                    tr(
                        "[logs] Invalid argument: %(arg)r (specify all / --all / -a / number / pdf <index>)"
                    )
                    % {"arg": a}
                )
                return True

    if export_pdf_index is not None:
        files = core.find_log_files(exclude_current=True)
        if not files:
            print(_("[logs] No log files found."))
            return True
        if export_pdf_index < 0 or export_pdf_index >= len(files):
            print(
                _("[logs] Index %(idx)s is out of range (0-%(max)s).")
                % {"idx": export_pdf_index, "max": len(files) - 1}
            )
            return True

        log_path = files[export_pdf_index]
        # If output path is provided as third argument, use it; else default to cwd
        if len(parts) >= 3:
            output_path = parts[2]
        else:
            # Strip "scheck_log_" prefix from filename for the default PDF name
            basename = os.path.basename(log_path)
            if basename.startswith("scheck_log_"):
                basename = basename[len("scheck_log_") :]
            output_path = os.path.join(os.getcwd(), basename + ".pdf")

        # Call the pdf_export tool
        from uagent.tools.pdf_export_tool import run_tool as pdf_export_run

        result = pdf_export_run({"log_path": log_path, "output_path": output_path})
        print(result)
        return True

    core.list_logs(limit=limit, show_all=show_all)
    return True


def _handle_cmd_tools(*, tr: Any) -> bool:
    try:
        tool_specs = tools.get_tool_specs() or []
        if not tool_specs:
            print(_("[tools] No tools loaded."))
            return True

        print(_("[tools] Loaded %(n)d tools") % {"n": len(tool_specs)})
        for spec in tool_specs:
            fn = (spec or {}).get("function") or {}
            name = fn.get("name") or "(unknown)"
            desc = (fn.get("description") or "").strip()
            if desc:
                print(_("- %(name)s: %(desc)s") % {"name": name, "desc": desc})
            else:
                print(_("- %(name)s") % {"name": name})
    except Exception as e:
        print(
            _("[tools error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )

    return True


def _strip_outer_quotes(s: str) -> str:
    """Strip matching outer quotes (single/double) from a string."""
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[0] == s[-1]:
        return s[1:-1]
    return s


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
        clean = _strip_outer_quotes(item)
        low = clean.lower()
        if low in ("-f", "--overwrite", "--force"):
            overwrite = True
            continue
        if low in ("-p", "--mkdirs", "--parents"):
            mkdirs = True
            continue
        paths.append(clean)

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
        print(tr(":cp <src> <dst> [-f|--overwrite] [-p|--mkdirs]"))
        return True

    try:
        items, overwrite, mkdirs = _normalize_cp_mv_args(raw)
    except Exception as e:
        print(
            tr("[cp error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    src_raw, dst_raw = items[0], items[1]
    try:
        src = Path(src_raw).expanduser().resolve()
        target = _resolve_copy_move_target(src, dst_raw)
        if target == src:
            print(
                tr("[cp] Source and destination are the same: %(path)s")
                % {"path": str(src)}
            )
            return True

        if not src.exists():
            print(tr("[cp] Source does not exist: %(path)s") % {"path": str(src)})
            return True

        if src.is_dir():
            if target.exists():
                if not overwrite:
                    print(
                        tr("[cp] Destination already exists: %(path)s")
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
                        tr("[cp] Destination already exists: %(path)s")
                        % {"path": str(target)}
                    )
                    return True
                _remove_existing_path(target)
            if mkdirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            elif not target.parent.exists():
                print(
                    tr("[cp] Destination parent does not exist: %(path)s")
                    % {"path": str(target.parent)}
                )
                return True
            shutil.copy2(src, target)

        print(
            tr("[cp] Copied: %(src)s -> %(dst)s")
            % {"src": str(src), "dst": str(target)}
        )
        return True
    except Exception as e:
        print(
            tr("[cp error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_mv(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(tr(":mv <src> <dst> [-f|--overwrite] [-p|--mkdirs]"))
        return True

    try:
        items, overwrite, mkdirs = _normalize_cp_mv_args(raw)
    except Exception as e:
        print(
            tr("[mv error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    src_raw, dst_raw = items[0], items[1]
    try:
        src = Path(src_raw).expanduser().resolve()
        target = _resolve_copy_move_target(src, dst_raw)
        if target == src:
            print(
                tr("[mv] Source and destination are the same: %(path)s")
                % {"path": str(src)}
            )
            return True

        if not src.exists():
            print(tr("[mv] Source does not exist: %(path)s") % {"path": str(src)})
            return True

        if target.exists():
            if not overwrite:
                print(
                    tr("[mv] Destination already exists: %(path)s")
                    % {"path": str(target)}
                )
                return True
            _remove_existing_path(target)

        if mkdirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            print(
                tr("[mv] Destination parent does not exist: %(path)s")
                % {"path": str(target.parent)}
            )
            return True

        os.replace(src, target)
        print(
            tr("[mv] Moved: %(src)s -> %(dst)s") % {"src": str(src), "dst": str(target)}
        )
        return True
    except Exception as e:
        print(
            tr("[mv error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_head(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(_(":head <path> [n]"))
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(
            _("[head error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    if not items:
        print(_(":head <path> [n]"))
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
                print(_(":head <path> [n]"))
                return True
            try:
                lines = int(items[i])
            except Exception:
                print(_("[head] Invalid line count: %(n)r") % {"n": items[i]})
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
        print(_(":head <path> [n]"))
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
            print(_("[head] Empty."))
        return True
    except Exception as e:
        print(
            _("[head error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_tail(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(_(":tail <path> [n]"))
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(
            _("[tail error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    if not items:
        print(_(":tail <path> [n]"))
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
                print(_(":tail <path> [n]"))
                return True
            try:
                lines = int(items[i])
            except Exception:
                print(_("[tail] Invalid line count: %(n)r") % {"n": items[i]})
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
        print(_(":tail <path> [n]"))
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
            print(_("[tail] Empty."))
        return True
    except Exception as e:
        print(
            _("[tail error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
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
    # Try dynamic subcommands (e.g., install, uninstall)
    res = tools.handle_dynamic_command(
        "skills",
        arg,
        messages_ref=messages_ref,
        client=client,
        depname=depname,
        core=core,
        tr=tr,
    )
    if res is not None:
        return res

    a = (arg or "").strip()
    if a.lower() in ("clear", "off", "unset", "reset"):
        removed = _clear_skill_messages(messages_ref)
        if removed <= 0:
            print(_("[skills] No active skill messages to clear."))
            return CommandResult()
        _persist_messages_with_warn(messages_ref, core=core, label="skills")
        print(_("[skills] Cleared %(n)d skill message(s).") % {"n": removed})
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
            print(_("[skills] No active skills."))
            return CommandResult()

        print(_("[skills] Active skills: %(n)d") % {"n": len(active)})
        for i, line in enumerate(active, start=1):
            print(_("[%(i)d] %(line)s") % {"i": i, "line": line})
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

        # Filter by keyword if provided (e.g. :skills list forecast, :skills find forecast)
        search_keyword = ""
        a_lower = a.strip().lower()
        for prefix in ("list ", "find ", "search ", "grep "):
            if a_lower.startswith(prefix):
                search_keyword = a_lower[len(prefix) :].strip()
                break
        if search_keyword:
            filtered = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                name = (it.get("name") or "").lower()
                desc = (it.get("description") or "").lower()
                if search_keyword in name or search_keyword in desc:
                    filtered.append(it)
            if filtered:
                items = filtered
            else:
                print(
                    _("[skills] No skills matching '%(kw)s'.") % {"kw": search_keyword}
                )
                return CommandResult()

        if not items:
            print(_("[skills] No skills found."))
            return CommandResult()

        selected_idx: int | None = None
        a_norm = unicodedata.normalize("NFKC", a).strip()
        # Check if arg is a number for direct selection
        if a_norm.isdigit():
            n = int(a_norm)
            if 1 <= n <= len(items):
                selected_idx = n - 1
            else:
                print(_("[skills] Out of range: %(n)d") % {"n": n})
                return CommandResult()

        # If not direct selection, show list and ask
        if selected_idx is None:
            print(_("[skills] Found %(n)d skills") % {"n": len(items)})
            for i, it in enumerate(items, start=1):
                if not isinstance(it, dict):
                    continue
                name = it.get("name") or "(unknown)"
                desc = it.get("description") or ""
                ok = bool(it.get("ok"))
                ok_mark = "OK" if ok else "WARN"
                print(
                    _("[%(i)d] (%(ok)s) %(name)s: %(desc)s")
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
                    print(_("[skills] Cancelled."))
                    return CommandResult()
                if not user_reply.isdigit():
                    print(_("[skills] Please enter a number or c."))
                    continue
                n = int(user_reply)
                if n < 1 or n > len(items):
                    print(_("[skills] Out of range: %(n)d") % {"n": n})
                    continue
                selected_idx = n - 1

        skill = items[selected_idx]
        if not isinstance(skill, dict):
            print(_("[skills] Invalid selection."))
            return CommandResult()

        name = skill.get("name") or "(unknown)"
        skill_dir = skill.get("path")
        if not isinstance(skill_dir, str) or not skill_dir.strip():
            print(_("[skills] Selected skill has no path."))
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
            print(_("[skills] Cancelled."))
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
        print(_("[skills] Applied: %(name)s") % {"name": name})
        return CommandResult(run_llm=True)

    except Exception as e:
        print(
            _("[skills error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )

    return CommandResult()


def _default_clean_threshold() -> int:
    """Default max user-turn count for short-log cleanup.

    Override with UAGENT_CLEAN_THRESHOLD (positive int). Falls back to 5.
    """
    raw = (env_get("UAGENT_CLEAN_THRESHOLD", "") or "").strip()
    if raw:
        try:
            n = int(raw)
            if n >= 0:
                return n
        except Exception:
            pass
    return 5


def _count_user_turns(messages: list[Any] | None) -> int:
    """Count user turns (role == user). Commands/system/tool rows are ignored."""
    n = 0
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") == "user":
            n += 1
    return n


def _parse_clean_threshold(arg: str, *, tr: Any) -> int | None:
    threshold = _default_clean_threshold()
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
            _("[clean error] Failed to get log list: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return False, [], {}

    targets: list[str] = []
    counts: dict[str, int] = {}

    for p in log_files:
        try:
            msgs = core.load_conversation_from_log(p)
            user_turns = _count_user_turns(msgs)
            counts[p] = user_turns
            if user_turns <= threshold:
                targets.append(p)
        except Exception as e:
            print(
                _("[clean warn] Skipped (parse failed): %(path)s (%(etype)s: %(err)s)")
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
            "Rule: user turns (role=user) <= %(threshold)d\n"
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
            print(_("[clean] Cancelled."))
            return False
        return True
    except Exception as e:
        print(
            _("[clean error] Confirmation failed: %(etype)s: %(err)s")
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
                _("[clean warn] Delete failed: %(path)s (%(etype)s: %(err)s)")
                % {"path": p, "etype": type(e).__name__, "err": e}
            )

    return deleted, failed


def _maybe_discard_short_session_log(
    *,
    core: Any,
    messages_ref: list[dict[str, Any]],
    tr: Any,
) -> None:
    """On exit, drop the current session log if it has few user turns.

    Silent no-op when the log is missing or above threshold. No confirmation
    (exit path); threshold matches :clean default / UAGENT_CLEAN_THRESHOLD.
    """
    threshold = _default_clean_threshold()
    user_turns = _count_user_turns(messages_ref)
    if user_turns > threshold:
        return

    log_path = getattr(core, "LOG_FILE", None)
    if not isinstance(log_path, str) or not log_path:
        return
    if not os.path.exists(log_path):
        return

    try:
        os.remove(log_path)
        print(
            tr(
                "[clean] Discarded short session log (user turns=%(n)d <= %(threshold)d): %(path)s"
            )
            % {"n": user_turns, "threshold": threshold, "path": log_path}
        )
    except Exception as e:
        print(
            _(
                "[clean warn] Failed to discard session log: %(path)s (%(etype)s: %(err)s)"
            )
            % {"path": log_path, "etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )


def _sweep_short_session_logs(
    *,
    core: Any,
    tr: Any,
    exclude_current: bool = True,
    quiet: bool = False,
) -> tuple[int, int]:
    """Delete leftover short session logs without confirmation.

    Intended for startup (crashed/killed sessions) and other maintenance paths.
    Current session is excluded by default so a fresh log is never removed.
    Returns (deleted, failed).
    """
    threshold = _default_clean_threshold()
    try:
        log_files = core.find_log_files(exclude_current=exclude_current)
    except Exception as e:
        if not quiet:
            print(
                _(
                    "[clean warn] Startup sweep skipped (list failed): %(etype)s: %(err)s"
                )
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
        return 0, 0

    targets: list[str] = []
    for path in log_files:
        try:
            msgs = core.load_conversation_from_log(path)
            if _count_user_turns(msgs) <= threshold:
                targets.append(path)
        except Exception as e:
            if not quiet:
                print(
                    _(
                        "[clean warn] Startup sweep skipped (parse failed): %(path)s (%(etype)s: %(err)s)"
                    )
                    % {"path": path, "etype": type(e).__name__, "err": e}
                )

    if not targets:
        return 0, 0

    deleted, failed = _delete_clean_targets(targets, tr=tr)
    if not quiet and (deleted or failed):
        print(
            tr(
                "[clean] Startup sweep: deleted=%(deleted)d, failed=%(failed)d "
                "(threshold=%(threshold)d user turns)."
            )
            % {"deleted": deleted, "failed": failed, "threshold": threshold}
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
            _(
                "[clean] No logs to delete (threshold=%(threshold)d user turns).\nLog dir: %(dir)s"
            )
            % {
                "threshold": threshold,
                "dir": getattr(core, "BASE_LOG_DIR", "(unknown)"),
            }
        )
        return True

    print(
        _("[clean] Logs to delete (<= %(threshold)d user turns): %(n)d")
        % {"threshold": threshold, "n": len(targets)}
    )
    for p in targets:
        c = counts.get(p, -1)
        print(tr(" - (%(count)d user turns) %(path)s") % {"count": c, "path": p})

    if not _confirm_clean_delete(
        core=core, threshold=threshold, targets=targets, tr=tr
    ):
        return True

    deleted, failed = _delete_clean_targets(targets, tr=tr)
    print(
        _("[clean] Done: deleted=%(deleted)d, failed=%(failed)d")
        % {"deleted": deleted, "failed": failed}
    )
    return True


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
            print(_("[load] Prepend to current log was cancelled."))
            return

        loaded_lines: list[str] = []
        try:
            with open(source_log_path, encoding="utf-8") as f:
                loaded_lines = f.read().splitlines(True)
        except Exception as e:
            print(
                _("[load warn] Failed to read source log: %(etype)s: %(err)s")
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
                _("[load warn] Failed to read current log: %(etype)s: %(err)s")
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
            print(_("[load] Prepended to current log: %(path)s") % {"path": cur_log})
        except Exception as e:
            print(
                _("[load warn] Failed to rewrite current log: %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            return
    except Exception as e:
        print(
            _("[load error] Failed: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return


def _handle_cmd_rm(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(_(":rm <path|glob> [path|glob]"))
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(_("[rm error] Failed to parse arguments: %(err)s") % {"err": e})
        return True

    if not items:
        print(_(":rm <path|glob> [path|glob]"))
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
            print(_("[rm] Unexpected delete_file preview response."))
            return True

        if not preview.get("ok", False):
            print(_("[rm] Preview failed."))
            stderr = preview.get("stderr")
            if stderr:
                print(str(stderr))
            return True

        missing = [str(p) for p in (preview.get("missing") or []) if str(p).strip()]
        matches = [str(p) for p in (preview.get("matches") or []) if str(p).strip()]

        if not matches:
            print(_("[rm] No matching paths."))
            if missing:
                print(_("[rm] Missing:"))
                for p in missing:
                    print(p)
            return True

        print(_("[rm] Candidates:"))
        for p in matches:
            print(p)
        if missing:
            print(_("[rm] Missing:"))
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
            print(_("[rm] Cancelled."))
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
            print(_("[rm] Unexpected delete_file response."))
            return True

        if delete.get("ok", False) and delete.get("deleted"):
            print(
                _("[rm] Deleted %(count)d path(s).")
                % {"count": int(delete.get("count") or 0)}
            )
        else:
            print(_("[rm] Failed."))
            stderr = delete.get("stderr")
            if stderr:
                print(str(stderr))
        return True
    except Exception as e:
        print(
            _("[rm error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_load(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    if not arg:
        print(_(":load <index|path>"))
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
        print(
            _("[load error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    new_messages = insert_tools_system_message(new_messages, core=core)
    messages_ref.clear()
    messages_ref.extend(new_messages)

    try:
        cb = get_callbacks()
        append_history = getattr(cb, "prompt_history_append", None)
        if callable(append_history):
            for msg in new_messages:
                if msg.get("role") != "user":
                    continue
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    append_history(content)
    except Exception:
        pass

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

            print(_("[load] workdir = %(path)s") % {"path": now})
    except Exception as e:
        print(
            _("[load warn] Failed to chdir from loaded log: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )

    print(_("Loaded log: %(path)s") % {"path": target_path})
    print(_("Conversation message count: %(n)d") % {"n": len(messages_ref)})

    # Clear responses_state to avoid stale previous_response_id after :load.
    try:
        if hasattr(core, "responses_state"):
            core.responses_state.clear()
        if hasattr(core, "_save_responses_state"):
            core._save_responses_state()
    except Exception:
        pass

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
            _("[%(label)s warn] Failed to rewrite current log: %(etype)s: %(err)s")
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

    _use_responses = (env_get("UAGENT_RESPONSES", "") or "").strip().lower() in (
        "1",
        "true",
    )
    # Mirror the main-flow guard: only providers in RESPONSES_PROVIDERS
    # can actually use the Responses API.  Gemini/Claude/DeepSeek etc.
    # are routed to their own branches inside compress_history_with_llm
    # regardless, so we just need to prevent a 404 on unsupported providers.
    if _use_responses:
        from .providers.provider_caps import RESPONSES_PROVIDERS

        _provider = (env_get("UAGENT_PROVIDER", "") or "").strip().lower()
        if _provider not in RESPONSES_PROVIDERS:
            _use_responses = False

    try:
        new_messages = core.compress_history_with_llm(
            client=client,
            depname=depname,
            messages=messages_ref,
            keep_last=keep_last,
            use_responses_api=_use_responses,
        )
    except Exception as e:
        print(
            _("[shrink_llm error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return True
    messages_ref.clear()
    messages_ref.extend(new_messages)
    _persist_messages_with_warn(messages_ref, core=core, label="shrink_llm")
    return True


def _handle_cmd_tokens(
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    depname: str = "",
) -> bool:
    try:
        from .llm_message_helpers import _count_messages_tokens

        total_tokens = _count_messages_tokens(messages_ref, depname or None)
    except Exception as e:
        print(
            _("[tokens error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return True

    print(_("Current token count (approx): %(n)s") % {"n": total_tokens})
    return True


def _handle_cmd_mem_list(*, tr: Any) -> bool:
    records = personal_long_memory.load_long_memory_records()
    if not records:
        print(_("No long-term memory entries."))
        return True

    print(_("Long-term memory entries:"))
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            import time as _time

            dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        else:
            dt = "(no-ts)"
        note = str(rec.get("note", ""))
        print(_("[%(idx)s] %(dt)s  %(note)s") % {"idx": idx, "dt": dt, "note": note})
    return True


def _handle_cmd_mem_del(arg: str, *, tr: Any) -> bool:
    if not arg:
        print(_(":mem-del <index>"))
        return True

    try:
        idx = int(arg)
    except Exception:
        print(_("[mem-del error] Failed to parse index as int: %(arg)r") % {"arg": arg})
        return True

    if personal_long_memory.delete_long_memory_entry(idx):
        print(_("Deleted long-term memory entry [%(idx)d].") % {"idx": idx})
    else:
        print(_("[mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
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
        print(_("No shared long-term memory entries."))
        return True

    import time as _time

    print(_("Shared long-term memory entries:"))
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        else:
            dt = "(no-ts)"
        note = str(rec.get("note", ""))
        print(_("[%(idx)s] %(dt)s  %(note)s") % {"idx": idx, "dt": dt, "note": note})

    return True


def _handle_cmd_profile_show(arg: str = "", *, core: Any, tr: Any) -> bool:
    from .profile_manager import load_profile, profile_from_logs
    from .runtime.runtime_memory import _format_profile

    arg = (arg or "").strip().lower()
    if arg.startswith("fromlog"):
        # Parse optional max_log_files from ":profile fromlog 50"
        parts = arg.split()
        max_log_files: int | None = None
        if len(parts) > 1:
            try:
                max_log_files = max(1, int(parts[1]))
            except (ValueError, TypeError):
                pass
        if max_log_files is not None:
            print(
                tr("Analyzing the most recent %d log files to generate user profile...")
                % max_log_files
            )
        else:
            print(tr("Analyzing past logs to generate user profile..."))
        try:
            profile = profile_from_logs(core, max_log_files=max_log_files)
            if not profile:
                print(tr("No past logs found or failed to generate profile."))
                return True
            print(tr("User profile generated successfully from past logs!"))
        except Exception as e:
            print(
                _("[profile fromlog error] %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e}
            )
            return True
    else:
        profile = load_profile()

    if (
        not profile.get("environment")
        and not profile.get("preferences")
        and not profile.get("constraints")
    ):
        print(tr("No user profile data found."))
        return True

    print(tr("User Profile:"))
    print(_format_profile(profile))
    return True


def _handle_cmd_profile_clear(*, tr: Any) -> bool:
    from .profile_manager import get_profile_file_path

    path = get_profile_file_path()
    if os.path.exists(path):
        try:
            os.remove(path)
            print(tr("User profile cleared successfully."))
        except Exception as e:
            print(
                _("[profile-clear error] %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e}
            )
    else:
        print(tr("No user profile file found to clear."))
    return True


def _handle_cmd_shared_mem_del(arg: str, *, tr: Any) -> bool:
    if not arg:
        print(_(":shared-mem-del <index>"))
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
            _("[shared-mem-del error] Failed to parse index as int: %(arg)r")
            % {"arg": arg}
        )
        return True

    records = shared_memory.load_shared_memory_records()
    if idx < 0 or idx >= len(records):
        print(_("[shared-mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
        return True

    try:
        records.pop(idx)
        path = shared_memory.get_shared_memory_file()
        if not path:
            print(_("[shared-mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
            return True

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(
            _("[shared-mem-del error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return True

    print(_("Deleted shared long-term memory entry [%(idx)d].") % {"idx": idx})
    return True


def format_help(*, core: Any, topic: str | None = None) -> str:
    """Format help text for interactive :help.

    - No topic: short overview (A)
    - topic set: detailed help for that command (B), including dynamic CMD_SPEC
    """

    tr = getattr(core, "tr", tr_)
    topic_s = (topic or "").strip()
    if topic_s:
        return format_help_detail(topic_s, core=core)

    # --- Overview (short) ---
    static_lines = [
        tr("Available commands:"),
        "  :help [cmd]           " + tr("Show this help, or details for a command"),
        "  :h / :?               " + tr("Alias for :help"),
        "  :cd <path>            " + tr("Change workdir"),
        "  :ls [path]            " + tr("List directory"),
        "  :logs                 " + tr("List conversation logs"),
        "  :load <idx|path>      " + tr("Load a past log into this session"),
        "  :cont                 " + tr("Continue from latest log (:load 0)"),
        "  :clean [N]            " + tr("Delete short logs (default N=5 user turns)"),
        "  :shrink [N]           " + tr("Shrink history (keep last N)"),
        "  :shrink_llm [N]       " + tr("LLM-summarize older history"),
        "  :tokens               " + tr("Show approx. conversation tokens"),
        "  :env ...              " + tr("Show/set/unset/save UAGENT_* env"),
        "  :skills ...           " + tr("List/apply/install skills"),
        "  :tools ...            " + tr("List/load/on/off tools and genres"),
        "  :plugin ...           " + tr("Manage plugins"),
        "  :tool create ...      " + tr("Scaffold a new tool module"),
        "  :auto <goal>|off      " + tr("Auto-pilot loop / stop"),
        "  :model                " + tr("Show model configuration"),
        "  :r / :v               " + tr("Reasoning / verbosity"),
        "  :mem-list / :mem-del  " + tr("Long-term memory"),
        "  :profile ...          " + tr("User profile show/generate/clear"),
        "  :cp / :mv / :rm       " + tr("Copy, move, delete paths"),
        "  :head / :tail         " + tr("Show file head/tail"),
        "  :reload               " + tr("Reload runtime pieces"),
        "  :exit / :quit         " + tr("Exit"),
    ]

    dyn_block: list[str] = []
    try:
        dyn_help = tools.get_dynamic_commands_help() if tools else []
    except Exception:
        dyn_help = []
    if dyn_help:
        dyn_block.append("")
        dyn_block.append(tr("Dynamic commands (from tools CMD_SPEC):"))
        for line in dyn_help:
            s = str(line).rstrip()
            if not s:
                continue
            stripped = s.lstrip()
            dyn_block.append("  " + stripped if stripped.startswith(":") else s)

    lines = (
        static_lines
        + dyn_block
        + [
            "",
            tr("Hints:"),
            "  "
            + tr("Type :help <command> for details (e.g. :help tools, :help skills)."),
            "  " + tr("Enter a line that is just 'f' to enter multiline input mode."),
            '  """retry  ' + tr("(in multiline) restart input from the beginning"),
        ]
    )

    norm_lines = []
    for ln in lines:
        s = str(ln)
        stripped = s.lstrip()
        if stripped.startswith(":"):
            s = "  " + stripped
        norm_lines.append(s)

    return "\n".join(norm_lines)


def _static_help_catalog(*, tr: Any) -> dict[str, dict[str, Any]]:
    """Detailed help for built-in (non-CMD_SPEC) commands."""

    def e(
        summary: str,
        usage: str = "",
        detail: str = "",
        aliases: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "summary": summary,
            "usage": usage,
            "detail": detail,
            "aliases": aliases or [],
        }

    cat: dict[str, dict[str, Any]] = {
        "help": e(
            tr("Show command help"),
            usage=tr(":help [command [subcommand]]"),
            detail=tr(
                "Without args: short list of all commands.\n"
                "With a command: detailed usage (static + dynamic CMD_SPEC).\n"
                "Examples: :help tools | :help skills install | :help plugin"
            ),
            aliases=["h", "?"],
        ),
        "cd": e(
            tr("Change workdir without confirmation"),
            usage=tr(":cd <path>"),
            detail=tr("Examples: :cd .. | :cd ~ | :cd C:\\path | :cd /"),
        ),
        "ls": e(
            tr("List directory entries"),
            usage=tr(":ls [path]"),
            detail=tr("Examples: :ls | :ls .. | :ls ~ | :ls C:\\path"),
        ),
        "logs": e(tr("Show conversation log file list"), usage=tr(":logs")),
        "load": e(
            tr("Load a past log (overwrites current conversation history)"),
            usage=tr(":load <idx|path>"),
            detail=tr(
                "idx is from :logs. After load you may be asked to prepend into the current session log."
            ),
        ),
        "cont": e(
            tr("Load the newest log (:load 0)"),
            usage=tr(":cont"),
        ),
        "clean": e(
            tr("Delete short conversation logs"),
            usage=tr(":clean [N]"),
            detail=tr(
                "Deletes scheck_log_*.jsonl where user-turn count (role=user) <= N "
                "(default 5, or UAGENT_CLEAN_THRESHOLD). "
                "On :exit/:quit/Ctrl-C, the current session log is discarded under the same rule. "
                "A silent startup sweep also removes leftover short logs from prior sessions."
            ),
        ),
        "shrink": e(
            tr("Shrink conversation history"),
            usage=tr(":shrink [N]"),
            detail=tr("Keep last N non-system messages (default 40)."),
        ),
        "shrink_llm": e(
            tr("Shrink history via LLM summarization"),
            usage=tr(":shrink_llm [N]"),
            detail=tr(
                "Summarize older history into one system message; keep last N raw (default 20)."
            ),
        ),
        "tokens": e(
            tr("Show approximate token count of the conversation"),
            usage=tr(":tokens"),
        ),
        "env": e(
            tr("Manage UAGENT_* environment variables"),
            usage=tr(":env show [KEY] | :env set KEY=VAL | :env unset KEY | :env save"),
            detail=tr(
                "Sensitive KEY names are masked on show. save writes encrypted .env.sec when configured."
            ),
        ),
        "skills": e(
            tr("Manage and apply Agent Skills"),
            usage=tr(":skills [list|active|clear|install|uninstall|apm|mp_search] ..."),
            detail=tr(
                "Built-in: list/active/clear (see runtime skills handlers).\n"
                ":skills list <keyword>  Filter skills by keyword (name/description).\n"
                ":skills find <keyword>  Same as list with filter.\n"
                "Dynamic subcommands come from tool CMD_SPEC (install, uninstall, apm, mp_search).\n"
                "Use :help skills install for a subcommand."
            ),
        ),
        "tools": e(
            tr("Control tool sending, genres, and loaded tools"),
            usage=tr(":tools [list|load|on|off|reload|output] ..."),
            detail=tr(
                ":tools on|off           Enable/disable sending tools to the LLM\n"
                ":tools on|off <genre>   Enable/disable a tool genre (and sync global on)\n"
                ":tools list [query]     List loaded tools\n"
                ":tools load <name>      Load one tool by name\n"
                ":tools reload           Reload tool modules from disk\n"
                ":tools output           Toggle showing tool results in UI"
            ),
        ),
        "tool": e(
            tr("Tool authoring helpers"),
            usage=tr(":tool create <name> [--lang python|rust] [--description '...']"),
            detail=tr("Scaffolds src/uagent/tools/<name>_tool.py (+ json)."),
        ),
        "plugin": e(
            tr("Install and manage plugins"),
            usage=tr(
                ":plugin <list|install|remove|enable|disable|reload|info|init|validate|marketplace> ..."
            ),
            detail=tr("See :help plugin <subcommand> for each action."),
        ),
        "auto": e(
            tr("Auto-pilot: repeatedly pursue a goal until done or stopped"),
            usage=tr(":auto <goal> [--max-rounds N] | :auto off"),
            detail=tr("Press x in CLI to request immediate exit from auto-pilot."),
        ),
        "model": e(
            tr("Show detailed model configuration"),
            usage=tr(":model"),
            detail=tr("Chat, image, audio, translation, embedding as configured."),
        ),
        "r": e(
            tr("Set reasoning effort"),
            usage=tr(":r [0|1|2|3|auto|minimal|low|medium|high|xhigh]"),
            detail=tr("0=off, 1=low, 2=medium, 3=high. Provider support varies."),
            aliases=["reasoning"],
        ),
        "v": e(
            tr("Set verbosity"),
            usage=tr(":v [0|1|2|3]"),
            detail=tr("0=off .. 3=high. No arg keeps current."),
            aliases=["verbosity"],
        ),
        "mem-list": e(tr("List long-term memory notes"), usage=tr(":mem-list")),
        "mem-del": e(
            tr("Delete a long-term memory note by index"),
            usage=tr(":mem-del <index>"),
            detail=tr("Index from :mem-list."),
        ),
        "profile": e(
            tr("Show or generate the learned user profile"),
            usage=tr(":profile | :profile fromlog [N]"),
            detail=tr("fromlog N uses the most recent N log files."),
            aliases=["profile-show"],
        ),
        "profile-fromlog": e(
            tr("Generate user profile from past logs"),
            usage=tr(":profile-fromlog [N]"),
            detail=tr("Default N=100; 0=all."),
        ),
        "profile-clear": e(
            tr("Clear learned user profile data"), usage=tr(":profile-clear")
        ),
        "cp": e(
            tr("Copy file or directory"),
            usage=tr(":cp <src> <dst> [-f|--overwrite] [-p|--mkdirs]"),
        ),
        "mv": e(
            tr("Move file or directory"),
            usage=tr(":mv <src> <dst> [-f|--overwrite] [-p|--mkdirs]"),
        ),
        "rm": e(
            tr("Delete file(s)/directory(ies) with preview + confirm"),
            usage=tr(":rm <path|glob>"),
        ),
        "head": e(
            tr("Show the first n lines of a file"),
            usage=tr(":head <path> [n]"),
            detail=tr("Default n=20."),
        ),
        "tail": e(
            tr("Show the last n lines of a file"),
            usage=tr(":tail <path> [n]"),
            detail=tr("Default n=20."),
        ),
        "reload": e(
            tr("Reload runtime configuration / modules"),
            usage=tr(":reload [target]"),
        ),
        "exit": e(
            tr("Exit the interactive session"), usage=tr(":exit"), aliases=["quit"]
        ),
        "quit": e(
            tr("Exit the interactive session"), usage=tr(":quit"), aliases=["exit"]
        ),
    }
    # alias index
    out = dict(cat)
    for key, info in list(cat.items()):
        for al in info.get("aliases") or []:
            out.setdefault(al, info)
    return out


def format_help_detail(topic: str, *, core: Any) -> str:
    """Detailed help for one command / subcommand."""

    tr = getattr(core, "tr", tr_)
    raw = (topic or "").strip().lstrip(":")
    if not raw:
        return format_help(core=core)

    parts = raw.split()
    cmd = parts[0].lower()
    sub = parts[1].lower() if len(parts) > 1 else ""

    blocks: list[str] = []

    # 1) Static catalog
    catalog = _static_help_catalog(tr=tr)
    info = catalog.get(cmd)
    if info:
        blocks.append(f":{cmd}")
        if info.get("summary"):
            blocks.append(f"  {info['summary']}")
        if info.get("usage"):
            blocks.append(f"  Usage: {info['usage']}")
        if info.get("aliases"):
            als = ", ".join(f":{a}" for a in info["aliases"] if a != cmd)
            if als:
                blocks.append(f"  Aliases: {als}")
        if info.get("detail") and not sub:
            blocks.append("")
            for dl in str(info["detail"]).splitlines():
                blocks.append(f"  {dl}" if dl.strip() else "")

    # 2) Dynamic CMD_SPEC detail
    dyn_text = None
    try:
        getter = getattr(tools, "get_dynamic_command_detail", None)
        if callable(getter):
            dyn_text = getter(cmd, sub or None)
    except Exception as e:
        dyn_text = f"(dynamic help error: {type(e).__name__}: {e})"

    if dyn_text:
        if blocks:
            blocks.append("")
            blocks.append(tr("Dynamic / plugin subcommands:"))
        blocks.append(dyn_text)
    elif not info:
        # unknown
        suggestions: list[str] = []
        for name in sorted(catalog.keys()):
            if name.startswith(cmd) or cmd in name:
                suggestions.append(name)
        try:
            for name in tools.list_dynamic_command_names():
                if name.startswith(cmd) or cmd in name:
                    suggestions.append(name)
        except Exception:
            pass
        msg = tr("Unknown command: :%(cmd)s") % {"cmd": cmd}
        if suggestions:
            msg += (
                "\n"
                + tr("Did you mean: ")
                + ", ".join(f":{s}" for s in suggestions[:12])
            )
        msg += "\n" + tr("Try :help for the full list.")
        return msg

    # If user asked a static-only sub that dynamic didn't cover, note it.
    if sub and info and not dyn_text:
        blocks.append("")
        blocks.append(tr("No dynamic subcommand help for '%(sub)s'.") % {"sub": sub})

    blocks.append("")
    blocks.append(tr("Tip: :help for overview, :help <cmd> <sub> for one subcommand."))
    return "\n".join(blocks).rstrip() + "\n"


def _uagent_env_names(prefix: str = "UAGENT_") -> list[str]:
    keys = set(get_known_uagent_env_keys(prefix))
    keys.update(
        k
        for k in os.environ
        if k.startswith(prefix) and not _is_placeholder_uagent_key(k)
    )
    return sorted(keys, key=str.lower)


def _uagent_format_env_value(name: str, value: str) -> str:
    _upper = name.upper()
    if any(kw in _upper for kw in ("KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL")):
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
        print(
            _("[env error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
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
            print(_("[env] Not found: %(key)s") % {"key": query})
            return True
        if len(keys) > 1:
            print(_("[env] Ambiguous: %(key)s") % {"key": query})
            for key in keys:
                print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
            return True
        key = keys[0]
        print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    if sub == "set":
        if len(items) < 3:
            print(_(":env set KEY VALUE"))
            return True
        key = items[1]
        value = " ".join(items[2:])
        os.environ[key] = value
        print(_("[env] Set %(key)s") % {"key": key})
        return True

    if sub == "unset":
        if len(items) < 2:
            print(_(":env unset KEY"))
            return True
        key = items[1]
        os.environ.pop(key, None)
        print(_("[env] Unset %(key)s") % {"key": key})
        return True

    if sub == "save":
        try:
            from .runtime.runtime_env import save_uagent_envsec

            sec_path = save_uagent_envsec()
            print(_("[env] Saved .env.sec: %(path)s") % {"path": str(sec_path)})
        except Exception as e:
            print(
                _("[env error] %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e}
            )
        return True

    print(_(":env show [KEY] / :env set KEY VALUE / :env unset KEY / :env save"))
    return True


# ============================================================
# Auto-Pilot
# ============================================================


def _get_followup_prompt(goal: str, feedback: str = "") -> str:
    """Generate continuation prompt for the main query (i18n)."""
    prompt = _("Continue. Goal: %(goal)s") % {"goal": goal}
    if feedback:
        prompt += "\n\n" + _("Reviewer notes: %(feedback)s") % {"feedback": feedback}
    return prompt


def _build_judgment_messages(
    messages: list[dict[str, Any]],
    goal: str,
) -> list[dict[str, Any]]:
    """Build messages for the reviewer judgment query.

    The system prompt is kept in English (LLM-oriented).
    Only the final user message uses gettext so it can be localized
    when displayed to the user, but functionally the LLM reads English.
    """
    system_prompt = (
        "You are a reviewer. Evaluate the conversation below and "
        "determine whether the goal '%(goal)s' has been achieved.\n"
        "Achieved    \u2192 COMPLETE\n"
        "More needed \u2192 CONTINUE\n"
        "Reply with COMPLETE or CONTINUE.\n"
        "If CONTINUE, briefly state what is still missing.\n"
        "Format: CONTINUE: <reason>"
    ) % {"goal": goal}

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    # Recent conversation history (max 6 messages = 3 turns)
    history: list[dict[str, Any]] = []
    for m in reversed(messages):
        if m.get("role") in ("user", "assistant"):
            content = m.get("content", "")
            if isinstance(content, str) and content.strip():
                history.append({"role": m["role"], "content": content[:500]})
                if len(history) >= 6:
                    break

    for h in reversed(history):
        msgs.append(h)

    msgs.append({"role": "user", "content": "COMPLETE or CONTINUE?"})
    return msgs


def _ask_reviewer_judgment(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    *,
    make_client_fn: Any,
) -> tuple[str, str]:
    """Ask the LLM as a reviewer whether the goal is achieved.

    Uses run_llm_rounds() in judgment_mode=True so that the same code path
    (Responses API included) is used for the judgment query.
    Returns ("COMPLETE"|"CONTINUE", feedback_text).
    """
    from . import uagent_llm as llm_util

    judgment_msgs = _build_judgment_messages(messages, core.auto_pilot_goal)

    core.set_status(True, "AUTO:judge")

    import warnings

    try:
        result_text = llm_util.run_llm_rounds(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
            core=core,
            make_client_fn=make_client_fn,
            append_result_to_outfile_fn=append_result_to_outfile,
            try_open_images_from_text_fn=try_open_images_from_text,
            judgment_mode=True,
            judgment_messages=judgment_msgs,
        )
    except Exception as e:
        warnings.warn(
            _("[AUTO] Judgment call failed: %(etype)s: %(error)s")
            % {"etype": type(e).__name__, "error": e}
        )
        raw = "CONTINUE"
    else:
        raw = (result_text or "").strip()

    upper = raw.upper()
    if "COMPLETE" in upper:
        judgment = "COMPLETE"
        feedback = ""
    else:
        judgment = "CONTINUE"
        # Extract feedback after "CONTINUE:" or the whole text minus "CONTINUE"
        feedback = raw
        for prefix in ("CONTINUE:", "continue:", "CONTINUE", "continue"):
            if prefix in raw:
                parts = raw.split(prefix, 1)
                if len(parts) > 1:
                    feedback = parts[1].strip().lstrip(":")
                    break
        feedback = feedback.strip().strip(" -\n").strip("\"'")

    print(_("\n[AUTO:judge] %(judgment)s") % {"judgment": judgment})
    if feedback:
        print(_("  feedback: %(feedback)s") % {"feedback": feedback})
    return judgment, feedback


def _run_auto_pilot_loop(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
) -> None:
    """Auto-pilot main loop.

    Step B (judgment) is performed FIRST to check the initial goal execution
    done by the caller. If COMPLETE, the loop exits immediately -- no extra round.
    Only if CONTINUE does Step A (followup refinement) run.

    1 round = 2 LLM calls:
      Step B: Reviewer judgment (evaluates previous work / initial goal)
      Step A: Main query (continuation of review/analysis if not yet done)
    """
    # Lazy import to avoid circular imports at module level
    from . import uagent_llm as llm_util

    # Allow separate LLM for reviewer (created once before the loop)
    _judge_provider = provider
    _judge_client = client
    _judge_depname = depname
    _judge_override = env_get("UAGENT_AP_PROVIDER", "").strip()
    if _judge_override:
        _saved = {}
        try:
            _prefix = "UAGENT_AP_"
            _std_prefix = "UAGENT_"
            for _key, _val in os.environ.items():
                if _key.startswith(_prefix):
                    _std_key = _std_prefix + _key[len(_prefix) :]
                    _saved[_std_key] = os.environ.get(_std_key, "")
                    os.environ[_std_key] = _val
            _judge_provider, _judge_client, _judge_depname = make_client_fn(core)
        except Exception:
            pass
        finally:
            for _std_key, _orig_val in _saved.items():
                if _orig_val:
                    os.environ[_std_key] = _orig_val
                else:
                    os.environ.pop(_std_key, None)

    feedback = ""
    while True:
        # 1. x key exit check
        with core.auto_pilot_exit_lock:
            if core.auto_pilot_exit_requested:
                core.auto_pilot_exit_requested = False
                core.auto_pilot_active = False
                print(_("[AUTO] Exited by user (x key)."))
                return

        # === Step B first: Reviewer judgment ===
        # On the first iteration this judges the initial goal execution.
        # On subsequent iterations this judges the followup from Step A.
        judgment, feedback = _ask_reviewer_judgment(
            _judge_provider,
            _judge_client,
            _judge_depname,
            messages,
            core,
            make_client_fn=make_client_fn,
        )

        if judgment == "COMPLETE":
            core.auto_pilot_active = False
            print(_("[AUTO] Review/analysis completed."))
            return

        # 2. Max rounds check (after judgment to count actual followup rounds)
        core.auto_pilot_round += 1
        if core.auto_pilot_round > core.auto_pilot_max_rounds:
            core.auto_pilot_active = False
            print(
                _("[AUTO] Max rounds (%(max)d) reached. Stopping.")
                % {"max": core.auto_pilot_max_rounds}
            )
            return

        # === Step A: Main query (refinement followup) ===
        next_prompt = _get_followup_prompt(core.auto_pilot_goal, feedback)

        core.set_status(True, "AUTO")
        print(
            _("[AUTO] Round %(round)d/%(max)d")
            % {"round": core.auto_pilot_round, "max": core.auto_pilot_max_rounds}
        )

        user_msg = {"role": "user", "content": next_prompt}
        messages.append(user_msg)
        core.log_message(user_msg)

        # Reset interrupt flag for each round
        with core.interrupt_lock:
            core.interrupt_requested = False

        llm_util.run_llm_rounds(
            provider,
            client,
            depname,
            messages,
            core=core,
            make_client_fn=make_client_fn,
            append_result_to_outfile_fn=append_result_to_outfile_fn,
            try_open_images_from_text_fn=try_open_images_from_text_fn,
        )

        core.set_status(True, "AUTO")
        # Loop back to Step B (judgment) at the top


def _handle_cmd_auto(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult | bool:
    """Handle the :auto command.

    Usage:
      :auto <goal> [--max-rounds N]
      :auto off
    """
    a = (arg or "").strip()

    if a.lower() == "off":
        core.auto_pilot_active = False
        core.auto_pilot_exit_requested = False
        print(_("[AUTO] Auto-pilot turned off."))
        return CommandResult()

    if not a:
        print(tr("Usage: :auto <goal> [--max-rounds N]"))
        print(tr("       :auto off"))
        return CommandResult()

    # Parse goal and options
    goal_parts: list[str] = []
    max_rounds = 10
    tokens = shlex.split(a)
    i = 0
    while i < len(tokens):
        if tokens[i] == "--max-rounds" and i + 1 < len(tokens):
            try:
                max_rounds = int(tokens[i + 1])
            except ValueError:
                print(
                    tr("Invalid value for --max-rounds: %(val)s")
                    % {"val": tokens[i + 1]}
                )
                return CommandResult()
            i += 2
        else:
            goal_parts.append(tokens[i])
            i += 1

    goal = " ".join(goal_parts)
    if not goal:
        print(tr("Goal cannot be empty."))
        return CommandResult()

    # Set auto-pilot state
    core.auto_pilot_goal = goal
    core.auto_pilot_max_rounds = max_rounds
    core.auto_pilot_round = 0
    core.auto_pilot_exit_requested = False
    core.auto_pilot_active = True

    print(_("[AUTO] Started. Goal: %(goal)s") % {"goal": goal})
    print(_("[AUTO] Max rounds: %(max)d") % {"max": max_rounds})

    # Return CommandResult with run_llm=True to trigger the first LLM call
    return CommandResult(run_llm=True, prompt=goal)


def _get_env(key: str, default: str = "") -> str:
    v = env_get(key)
    if v is None:
        return default
    return v.strip()


def _format_capa(cap) -> list[str]:
    """Format a llmcapa Capability object into detail lines."""
    lines: list[str] = []
    lines.append(_("    Display Name:  %(value)s") % {"value": cap.display_name})
    lines.append(
        _("    Context Window: %(value)s tokens") % {"value": f"{cap.context_window:,}"}
    )
    lines.append(
        _("    Max Output:    %(value)s tokens")
        % {"value": f"{cap.max_output_tokens:,}"}
    )
    lines.append(
        _("    Tokenizer:     %(value)s") % {"value": cap.tokenizer_name or "?"}
    )
    lines.append(_("    License:       %(value)s") % {"value": cap.license_type or "?"})
    lines.append(
        _("    Knowledge Cutoff: %(value)s") % {"value": cap.knowledge_cutoff or "?"}
    )
    lines.append(_("    Deprecated:    %(value)s") % {"value": cap.deprecated})
    if cap.input_modalities:
        lines.append(
            _("    Input:         %(value)s")
            % {"value": ", ".join(cap.input_modalities)}
        )
    if cap.output_modalities:
        lines.append(
            _("    Output:        %(value)s")
            % {"value": ", ".join(cap.output_modalities)}
        )
    feats = []
    if cap.supports_function_calling:
        feats.append("function_calling")
    if cap.supports_json_mode:
        feats.append("json_mode")
    if cap.supports_streaming:
        feats.append("streaming")
    if cap.supports_vision:
        feats.append("vision")
    if cap.supports_reasoning:
        feats.append("reasoning")
    if cap.supports_chat_completion:
        feats.append("chat_completion")
    if cap.supports_responses_api:
        feats.append("responses_api")
    if cap.supports_reasoning_effort:
        feats.append("reasoning_effort")
    if cap.supports_thinking_budget:
        feats.append("thinking_budget")
    if cap.supports_anthropic_api:
        feats.append("anthropic_api")
    if cap.supports_google_api:
        feats.append("google_api")
    if cap.supports_fim:
        feats.append("fim")
    if feats:
        lines.append(_("    Features:      %(value)s") % {"value": ", ".join(feats)})
    if cap.pricing:
        price = cap.pricing
        inp = price.get("input_per_1m")
        out = price.get("output_per_1m")
        cur = price.get("currency", "USD")
        if inp is not None and out is not None:
            lines.append(
                _(
                    "    Pricing:       $%(inp).2f/%(cur)sM in, "
                    "$%(outp).2f/%(cur)sM out"
                )
                % {"inp": float(inp), "outp": float(out), "cur": cur}
            )
    if cap.reasoning_effort_values:
        lines.append(
            _("    Reasoning Efforts: %(value)s")
            % {"value": ", ".join(cap.reasoning_effort_values)}
        )
    if cap.thinking_budget_values:
        lines.append(
            _("    Thinking Budgets: %(value)s")
            % {"value": ", ".join(str(v) for v in cap.thinking_budget_values)}
        )
    return lines


def _fetch_model_capa(provider: str, model: str) -> list[str]:
    """Fetch llmcapa info for a model. Returns detail lines, or empty if unavailable."""
    try:
        from .llmcapa_util import format_capability_lines, get_capability

        prov = provider if provider not in ("(none)", "") else None
        cap = get_capability(model, prov)
        if cap:
            # Prefer shared formatter (includes provider/cost); fall back to local.
            lines = format_capability_lines(cap)
            return (
                lines
                if lines
                else [f"    model_id: {cap.model_id}"] + _format_capa(cap)
            )
    except Exception:
        pass
    return []


def _model_provider_note(
    explicit_key: str, *, fallback_key: str = "UAGENT_PROVIDER"
) -> str:
    """Annotate provider line when value comes from a fallback env key."""
    if _get_env(explicit_key):
        return ""
    if fallback_key and _get_env(fallback_key):
        return _("  (fallback: %(key)s)") % {"key": fallback_key}
    return _("  (fallback)")


def _model_value_note(
    *,
    explicit_keys: list[str],
    used_fallback: bool,
    fallback_label: str,
) -> str:
    """Annotate model line when a default/fallback value is used."""
    if any(_get_env(k) for k in explicit_keys):
        return ""
    if used_fallback and fallback_label:
        return _("  (fallback: %(key)s)") % {"key": fallback_label}
    return ""


def _append_resolved_model_section(
    lines: list[str],
    *,
    label: str,
    explicit_provider_key: str,
    resolved: tuple[str, str] | None,
    model_explicit_keys: list[str] | None = None,
    model_fallback_label: str = "",
    extra_lines: list[str] | None = None,
    verbose: bool = False,
) -> None:
    """Append one capability section, including fallback-resolved results."""
    if not resolved:
        lines.append(_("  %(label)s: (not configured)") % {"label": label})
        return

    provider, model = resolved
    prov_note = _model_provider_note(explicit_provider_key)
    model_note = _model_value_note(
        explicit_keys=model_explicit_keys or [],
        used_fallback=bool(model_fallback_label),
        fallback_label=model_fallback_label,
    )
    lines.append(_("  %(label)s:") % {"label": label})
    lines.append(
        _("    Provider: %(provider)s%(note)s")
        % {"provider": provider, "note": prov_note}
    )
    lines.append(
        _("    Model:    %(model)s%(note)s") % {"model": model, "note": model_note}
    )
    if extra_lines:
        lines.extend(extra_lines)
    if verbose:
        capa_lines = _fetch_model_capa(provider, model)
        if capa_lines:
            lines.extend(capa_lines)


def _image_analysis_model_keys(provider: str) -> tuple[list[str], str]:
    p = provider.upper()
    keys = [
        f"UAGENT_{p}_IMG_ANALYSIS_DEPNAME",
        "UAGENT_IMG_ANALYSIS_DEPNAME",
    ]
    if provider in ("openai", "azure", "ollama"):
        keys.append(f"UAGENT_{p}_DEPNAME")
        return keys, f"UAGENT_{p}_DEPNAME/default"
    if provider in ("gemini", "vertexai"):
        return keys, "default gemini-1.5-flash"
    return keys, "default"


def _image_generation_model_keys(provider: str) -> tuple[list[str], str]:
    p = provider.upper()
    keys = [f"UAGENT_{p}_IMG_GENERATE_DEPNAME", "UAGENT_IMG_GENERATE_DEPNAME"]
    defaults = {
        "openai": "default gpt-image-1",
        "gemini": "default imagen-4.0-generate-001",
        "vertexai": "default imagen-4.0-generate-001",
        "zai": "default glm-image",
        "grok": "default grok-imagine-image",
    }
    return keys, defaults.get(provider, "default")


def _audio_model_keys(provider: str, mode: str) -> tuple[list[str], str]:
    m = mode.upper()
    if provider == "azure":
        return [f"UAGENT_AZURE_{m}_DEPNAME"], f"UAGENT_AZURE_{m}_DEPNAME"
    if provider in ("gemini", "vertexai"):
        return (
            [f"UAGENT_GEMINI_{m}_DEPNAME", "UAGENT_GEMINI_MODEL"],
            "UAGENT_GEMINI_MODEL/default",
        )
    if provider == "grok":
        if mode == "speech":
            return (
                ["UAGENT_GROK_SPEECH_DEPNAME", "UAGENT_GROK_TTS_MODEL"],
                "default grok-tts",
            )
        return (
            ["UAGENT_GROK_TRANSCRIBE_DEPNAME", "UAGENT_GROK_STT_MODEL"],
            "default grok-stt-batch",
        )
    default = "gpt-4o-mini-tts" if mode == "speech" else "gpt-4o-mini-transcribe"
    return [f"UAGENT_OPENAI_{m}_DEPNAME"], f"default {default}"


def _handle_cmd_model(
    arg: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult:
    """Show detailed model configuration for all capabilities.

    :model         - show basic configuration
    :model v       - verbose: also show llmcapa details for all configured models

    Optional modalities (image/audio/embedding) use the same effective resolution
    as the startup banner, including UAGENT_PROVIDER / built-in model fallbacks.
    """
    verbose = arg.strip().lower() in ("v", "ver", "verbose")
    provider = _get_env("UAGENT_PROVIDER", "(none)")
    model = _get_env(f"UAGENT_{provider.upper()}_DEPNAME")
    if not model:
        model = _get_env("UAGENT_DEPNAME", "(not set)")

    lines: list[str] = []
    lines.append(_("=== Model Configuration ==="))
    lines.append(_("  Chat (main):"))
    display_provider = _("(none)") if provider == "(none)" else provider
    display_model = _("(not set)") if model == "(not set)" else model
    lines.append(
        _("    Provider: %(provider)s%(note)s")
        % {"provider": display_provider, "note": ""}
    )
    lines.append(
        _("    Model:    %(model)s%(note)s") % {"model": display_model, "note": ""}
    )
    if provider not in ("(none)", ""):
        try:
            from .llmcapa_util import deprecated_model_warning

            warn = deprecated_model_warning(model, provider)
            if warn:
                lines.append(_("    WARN: %(warn)s") % {"warn": warn})
        except Exception:
            pass
    if verbose and provider not in ("(none)", ""):
        capa_lines = _fetch_model_capa(provider, model)
        if capa_lines:
            lines.extend(capa_lines)

    # Resolve optional modalities with the same logic as startup banner.
    try:
        from .runtime.runtime_banner import (
            _audio_model_info,
            _embedding_model_info,
            _image_analysis_model_info,
            _image_generation_model_info,
        )
    except Exception:
        _audio_model_info = None  # type: ignore[assignment]
        _embedding_model_info = None  # type: ignore[assignment]
        _image_analysis_model_info = None  # type: ignore[assignment]
        _image_generation_model_info = None  # type: ignore[assignment]

    def _safe_resolve(fn: Any) -> tuple[str, str] | None:
        if fn is None:
            return None
        try:
            return fn()
        except Exception:
            return None

    ia_resolved = _safe_resolve(_image_analysis_model_info)
    ia_keys: list[str] = []
    ia_fb = ""
    if ia_resolved:
        ia_keys, ia_fb = _image_analysis_model_keys(ia_resolved[0])
    _append_resolved_model_section(
        lines,
        label=_("Image Analysis"),
        explicit_provider_key="UAGENT_IMG_ANALYSIS_PROVIDER",
        resolved=ia_resolved,
        model_explicit_keys=ia_keys,
        model_fallback_label=ia_fb,
        verbose=verbose,
    )

    ig_resolved = _safe_resolve(_image_generation_model_info)
    ig_keys: list[str] = []
    ig_fb = ""
    if ig_resolved:
        ig_keys, ig_fb = _image_generation_model_keys(ig_resolved[0])
    _append_resolved_model_section(
        lines,
        label=_("Image Generation"),
        explicit_provider_key="UAGENT_IMG_GENERATE_PROVIDER",
        resolved=ig_resolved,
        model_explicit_keys=ig_keys,
        model_fallback_label=ig_fb,
        verbose=verbose,
    )

    speech_resolved = _safe_resolve(
        (lambda: _audio_model_info("speech")) if _audio_model_info is not None else None
    )
    speech_keys: list[str] = []
    speech_fb = ""
    if speech_resolved:
        speech_keys, speech_fb = _audio_model_keys(speech_resolved[0], "speech")
    _append_resolved_model_section(
        lines,
        label=_("Audio Speech"),
        explicit_provider_key="UAGENT_AUDIO_SPEECH_PROVIDER",
        resolved=speech_resolved,
        model_explicit_keys=speech_keys,
        model_fallback_label=speech_fb,
        verbose=verbose,
    )

    tr_resolved = _safe_resolve(
        (lambda: _audio_model_info("transcribe"))
        if _audio_model_info is not None
        else None
    )
    tr_keys: list[str] = []
    tr_fb = ""
    if tr_resolved:
        tr_keys, tr_fb = _audio_model_keys(tr_resolved[0], "transcribe")
    _append_resolved_model_section(
        lines,
        label=_("Audio Transcribe"),
        explicit_provider_key="UAGENT_AUDIO_TRANSCRIBE_PROVIDER",
        resolved=tr_resolved,
        model_explicit_keys=tr_keys,
        model_fallback_label=tr_fb,
        verbose=verbose,
    )

    # Translation (requires explicit UAGENT_TRANSLATE_PROVIDER)
    translate_provider = _get_env("UAGENT_TRANSLATE_PROVIDER")
    if translate_provider:
        translate_model = _get_env("UAGENT_TRANSLATE_DEPNAME")
        model_fb = ""
        if not translate_model:
            translate_model = _get_env(f"UAGENT_{translate_provider.upper()}_DEPNAME")
            if translate_model:
                model_fb = f"UAGENT_{translate_provider.upper()}_DEPNAME"
        if translate_model:
            translate_to = _get_env("UAGENT_TRANSLATE_TO_LLM", "?")
            translate_from = _get_env("UAGENT_TRANSLATE_FROM_LLM", "?")
            model_note = (
                _("  (fallback: %(key)s)") % {"key": model_fb} if model_fb else ""
            )
            lines.append(_("  Translation:"))
            lines.append(
                _("    Provider: %(provider)s%(note)s")
                % {"provider": translate_provider, "note": ""}
            )
            lines.append(
                _("    Model:    %(model)s%(note)s")
                % {"model": translate_model, "note": model_note}
            )
            lines.append(
                _("    From→To:  %(src)s → %(dst)s")
                % {"src": translate_from, "dst": translate_to}
            )
            if verbose:
                capa_lines = _fetch_model_capa(translate_provider, translate_model)
                if capa_lines:
                    lines.extend(capa_lines)
        else:
            lines.append(_("  Translation: (not configured)"))
    else:
        lines.append(_("  Translation: (not configured)"))

    emb_resolved = _safe_resolve(_embedding_model_info)
    emb_keys: list[str] = []
    emb_fb = ""
    if emb_resolved:
        emb_keys = [f"UAGENT_{emb_resolved[0].upper()}_EMBEDDING_DEPNAME"]
        emb_fb = emb_keys[0]
    _append_resolved_model_section(
        lines,
        label=_("Embedding"),
        explicit_provider_key="UAGENT_EMBEDDING_PROVIDER",
        resolved=emb_resolved,
        model_explicit_keys=emb_keys,
        model_fallback_label=emb_fb,
        verbose=verbose,
    )

    print("\n".join(lines))
    return CommandResult()


def handle_command(
    line: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
) -> bool | CommandResult:
    """\u30b3\u30de\u30f3\u30c9\u884c(:help, :logs, :load ...)\u3092\u51e6\u7406\u3059\u308b

    \u623b\u308a\u5024: False \u3092\u8fd4\u3059\u3068\u30e1\u30a4\u30f3\u30eb\u30fc\u30d7\u7d42\u4e86(:exit / :quit)\u3002
    CommandResult(run_llm=True) \u3092\u8fd4\u3059\u3068\u3001\u30b3\u30de\u30f3\u30c9\u51e6\u7406\u5f8c\u306b LLM \u3092\u5b9f\u884c\u3059\u308b\u3002
    """
    tr = getattr(core, "tr", tr_)

    line = line.lstrip(":").strip()
    if not line:
        return True

    parts = line.split(maxsplit=1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    # Plugin namespaced form: :plugin:subcommand [args]
    # (Claude-style /plugin:cmd mapped onto uag ":")
    if ":" in cmd:
        head, tail = cmd.split(":", 1)
        if head and tail:
            # ":genshijin:commit" -> cmd=genshijin, arg="commit ..."
            cmd = head
            arg = f"{tail} {arg}".strip() if arg else tail

    if cmd in ("help", "h", "?"):
        topic = (arg or "").strip() or None
        core.print_help(topic)
        return True

    if cmd in ("r", "reasoning"):
        return _handle_cmd_reasoning(arg, tr=tr)

    if cmd in ("v", "verbosity"):
        return _handle_cmd_verbosity(arg, tr=tr)

    if cmd == "cd":
        return _handle_cmd_cd(arg, messages_ref, core=core, tr=tr)

    if cmd == "reload":
        return _handle_cmd_reload(arg, messages_ref, core=core, tr=tr)

    if cmd == "ls":
        return _handle_cmd_ls(arg, tr=tr)

    if cmd == "logs":
        return _handle_cmd_logs(arg, core=core, tr=tr)

    if cmd == "tools":
        if arg and arg.strip():
            parts = arg.strip().split()
            sub = parts[0].lower()
            # ":tools on" / ":tools off" (no extra args) => global tool toggle.
            # ":tools on iot" / ":tools off comm" etc. => genre enable/disable + global sync.
            if sub in ("on", "off") and len(parts) == 1:
                core.tools_enabled = sub == "on"
                state = "ON" if core.tools_enabled else "OFF"
                print(
                    _("[tools] Tool sending to LLM is now %(state)s") % {"state": state}
                )
                return CommandResult()
            # ":tools on <genre>" => enable genre, also re-enable global tool sending.
            if sub == "on" and len(parts) >= 2:
                core.tools_enabled = True
            # Try dynamic subcommands (e.g., on comm, off comm, list)
            res = tools.handle_dynamic_command(
                "tools",
                arg,
                messages_ref=messages_ref,
                client=client,
                depname=depname,
                core=core,
                tr=tr,
            )
            if res is not None:
                if isinstance(res, str):
                    print(res)
                if type(res).__name__ == "CommandResult":
                    return res
                return CommandResult()
        print(_("Usage: :tools [list|on|off|output] [args...]"))
        return CommandResult()

    if cmd == "env":
        return _handle_cmd_env(arg, tr=tr)

    if cmd == "skills":
        return _handle_cmd_skills(arg, messages_ref, client, depname, core=core, tr=tr)

    if cmd == "clean":
        return _handle_cmd_clean(arg, core=core, tr=tr)

    if cmd == "cont":
        return _handle_cmd_load("0", messages_ref, core=core, tr=tr)

    if cmd == "load":
        return _handle_cmd_load(arg, messages_ref, core=core, tr=tr)

    if cmd == "shrink":
        return _handle_cmd_shrink(arg, messages_ref, core=core)

    if cmd == "shrink_llm":
        return _handle_cmd_shrink_llm(arg, messages_ref, client, depname, core=core)

    if cmd == "tokens":
        return _handle_cmd_tokens(messages_ref, core=core, depname=depname)

    if cmd == "mem-list":
        return _handle_cmd_mem_list(tr=tr)

    if cmd == "mem-del":
        return _handle_cmd_mem_del(arg, tr=tr)

    if cmd in ("profile", "profile-show"):
        return _handle_cmd_profile_show(arg, core=core, tr=tr)

    if cmd == "profile-fromlog":
        # Pass optional max_log_files as "fromlog N"
        profile_arg = "fromlog 100"
        if arg and arg.strip():
            try:
                n = int(arg.strip())
                profile_arg = f"fromlog {n}"
            except (ValueError, TypeError):
                pass
        return _handle_cmd_profile_show(profile_arg, core=core, tr=tr)

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

    if cmd == "auto":
        return _handle_cmd_auto(
            arg,
            messages_ref,
            client,
            depname,
            core=core,
            tr=tr,
        )

    if cmd == "model":
        return _handle_cmd_model(arg, core=core, tr=tr)

    # Try dynamic commands registered by tool modules
    res = tools.handle_dynamic_command(
        cmd,
        arg,
        messages_ref=messages_ref,
        client=client,
        depname=depname,
        core=core,
        tr=tr,
    )
    if res is not None:
        return res

    if cmd in ("exit", "quit"):
        _maybe_discard_short_session_log(core=core, messages_ref=messages_ref, tr=tr)
        print(tr("Exiting."))
        return False

    print(tr("Unknown command: :%(cmd)s") % {"cmd": cmd})
    return True


def load_agents_md() -> str:
    """\u8d77\u52d5\u30c7\u30a3\u30ec\u30af\u30c8\u30ea\u306b AGENTS.md \u304c\u3042\u308c\u3070\u5185\u5bb9\u3092\u8fd4\u3059\u3002"""
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


def build_initial_messages(
    *,
    core: Any,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    # Rebuild system prompt so native tool_search can drop catalog steering
    # using the current provider/model (import-time default may differ).
    try:
        refresh = getattr(core, "refresh_system_prompt", None)
        if callable(refresh):
            refresh(
                provider=provider,
                depname=depname,
                use_responses_api=use_responses_api,
            )
    except Exception:
        pass

    system_msg = {"role": "system", "content": core.SYSTEM_PROMPT}
    messages.append(system_msg)
    core.log_message(system_msg)

    # --- Load project instruction files (CLAUDE.md / AGENTS.md) ---
    try:
        from .runtime.runtime_instructions import load_project_instruction_files

        instructions = load_project_instruction_files()
        for instr in instructions:
            msg = {"role": "system", "content": instr}
            messages.append(msg)
            core.log_message(msg)
    except Exception:
        pass

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
    return messages


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
    """UAGENT_OUTFILE \u304c\u6307\u5b9a\u3055\u308c\u3066\u3044\u308c\u3070\u3001\u30a2\u30b7\u30b9\u30bf\u30f3\u30c8\u6700\u7d42\u51fa\u529b\u3092\u8ffd\u8a18\u3059\u308b\u3002"""
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
