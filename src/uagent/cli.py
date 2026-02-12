import getpass
import importlib
import json
import os
import sys
import threading
import time
import atexit
from typing import Any, Dict, List

from . import tools
from .tools import long_memory as personal_long_memory
from .tools import shared_memory

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


# OpenAI / Azure OpenAI
try:
    from openai import OpenAI
except ImportError:
    # 古い openai パッケージ向けフォールバック（OpenAI クラスが無い場合）

    OpenAI = None  # type: ignore[assignment]

# Google Gemini (google-genai)
try:
    from google import genai
    from google.genai import types as gemini_types, errors as gemini_errors
except Exception:  # google-genai 未インストール時など
    genai = None  # type: ignore[assignment]
    gemini_types = None  # type: ignore[assignment]
    gemini_errors = None  # type: ignore[assignment]

try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline  # type: ignore
    except ImportError:
        readline = None  # type: ignore

from . import util_providers as providers
from . import uagent_llm as llm_util
from . import util_tools as tools_util
from .welcome import print_welcome
from . import runtime_init as _runtime_init

from .checks import check_git_installation

from .util_tools import (
    extract_image_paths,
    image_file_to_data_url,
    parse_startup_args as _parse_startup_args,
    build_long_memory_system_message,
    build_initial_messages,
    handle_command,
    init_tools_callbacks as _init_tools_callbacks,
)

# scheck_core をインポート
core = importlib.import_module(".core", package="uagent")

# callbacks 注入
_init_tools_callbacks(core)


# Readline history setup
_HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".scheck_history")

if readline:
    try:
        if os.path.exists(_HISTORY_FILE):
            readline.read_history_file(_HISTORY_FILE)
    except Exception:
        pass

    def _save_history():
        try:
            readline.set_history_length(1000)
            readline.write_history_file(_HISTORY_FILE)
        except Exception:
            pass

    atexit.register(_save_history)


_startup_args, _startup_unknown = _parse_startup_args()
_cli_workdir = _startup_args.get("workdir")
_env_workdir = os.environ.get("UAGENT_WORKDIR")

UAGENT_NON_INTERACTIVE = bool(_startup_args.get("non_interactive"))


# NOTE(Mode A): workdir initialization (mkdir/chdir + startup info) is performed inside main()
# under startup stdout/stderr capture, so importing this module does not change CWD.

# 初期ファイル引数は unknown の最初の要素があればそれを使う（従来の sys.argv[1] 相当）
INITIAL_FILE_ARG = _startup_unknown[0] if _startup_unknown else None


# ------------------------------
# Readline TAB completion (interactive TTY only)
# - Only for :cd and :ls arguments
# - Other inputs keep current behavior

def _uagent_has_glob_meta(s: str) -> bool:
    return any(ch in s for ch in ("*", "?", "["))


def _uagent_split_cmd_arg(buf: str) -> tuple[str, str, int]:
    # Split ':cmd arg...' into (cmd, arg, arg_start_index_in_buf)
    # Notes:
    # - intentionally simple; no quoting support
    if not buf.startswith(":"):
        return "", "", len(buf)

    s = buf[1:]
    m = re.match(r"^(\S+)(\s+)?(.*)$", s)
    if not m:
        return "", "", len(buf)

    cmd = (m.group(1) or "").strip()
    ws = m.group(2) or ""
    rest = m.group(3) or ""

    if not ws:
        return cmd, "", len(buf)

    arg_start = 1 + len(cmd) + len(ws)
    return cmd, rest, arg_start


def _uagent_path_candidates(prefix: str) -> list[str]:
    # Return completion candidates for a filesystem path prefix.
    # - expands ~ and envvars in the directory part for scanning
    # - returns candidates in the form that replaces the current token

    expanded = os.path.expandvars(os.path.expanduser(prefix))

    last_sep = max(expanded.rfind("/"), expanded.rfind("\\"))

    if last_sep >= 0:
        scan_dir = expanded[: last_sep + 1]
        base = expanded[last_sep + 1 :]
        out_prefix_raw = prefix[: last_sep + 1]
    else:
        scan_dir = ""
        base = expanded
        out_prefix_raw = ""

    scan_dir_fs = scan_dir or "."

    try:
        names = os.listdir(scan_dir_fs)
    except Exception:
        return []

    cands: list[str] = []
    for name in names:
        if not name.lower().startswith(base.lower()):
            continue

        full = os.path.join(scan_dir_fs, name)
        suffix = os.sep if os.path.isdir(full) else ""

        if last_sep >= 0 and last_sep < len(prefix):
            typed_sep = prefix[last_sep]
        else:
            typed_sep = os.sep

        if suffix:
            suffix = typed_sep

        cands.append(out_prefix_raw + name + suffix)

    cands.sort(key=lambda x: x.lower())
    return cands


def _uagent_rl_completer(text_part: str, state: int):
    # readline completer for ':cd' / ':ls' (first arg only)
    try:
        if not readline:
            return None

        buf = readline.get_line_buffer() or ""
        cmd, arg, _arg_start = _uagent_split_cmd_arg(buf)

        if cmd not in ("cd", "ls"):
            return None

        # Only complete the first argument; if spaces already present in arg, stop.
        if " " in arg or "\t" in arg:
            return None

        # For :ls, if arg already contains glob meta, do not complete (avoid odd mixes)
        if cmd == "ls" and _uagent_has_glob_meta(arg):
            return None

        cands = _uagent_path_candidates(arg)
        if state < len(cands):
            return cands[state]
        return None
    except Exception:
        return None


def _uagent_setup_readline_completion() -> None:
    # Enable TAB completion when running interactively
    if not readline:
        return
    if not sys.stdin.isatty():
        return

    try:
        readline.parse_and_bind("tab: complete")

        # Do not treat ':' as delimiter, otherwise ':cd' gets broken into tokens.
        if hasattr(readline, "set_completer_delims"):
            delims = readline.get_completer_delims()
            if ":" in delims:
                readline.set_completer_delims(delims.replace(":", ""))

        readline.set_completer(_uagent_rl_completer)
    except Exception:
        pass



def _flush_stdin_input_buffer() -> None:
    """Best-effort flush of *pending* user keystrokes before a prompt.

    Purpose: prevent "typeahead" (keys pressed while the app is busy) from being
    consumed by the next human_ask/input/getpass prompt.

    Strategy:
    - Windows: drain console keyboard buffer via msvcrt.kbhit/getwch.
    - POSIX: drain readable bytes from stdin (non-blocking) when stdin is a TTY.

    Notes:
    - This is best-effort and silently ignores failures.
    - We intentionally use this only when replying to human_ask (see stdin_loop)
      to reduce the chance of discarding intended normal prompt input.
    """

    # Windows
    if os.name == "nt":
        try:
            import msvcrt  # type: ignore

            while msvcrt.kbhit():
                try:
                    msvcrt.getwch()
                except Exception:
                    try:
                        msvcrt.getch()
                    except Exception:
                        break
        except Exception:
            pass
        return

    # POSIX
    try:
        import os as _os
        import select

        if not sys.stdin.isatty():
            return

        fd = sys.stdin.fileno()
        while True:
            r, _, _ = select.select([fd], [], [], 0)
            if not r:
                break
            try:
                _os.read(fd, 4096)
            except Exception:
                break
    except Exception:
        pass


def _getpass_fallback(prompt: str) -> str:
    """getpass.getpass がエコーバックを抑制できない環境（isatty=Falseなど）向けのフォールバック"""
    if os.name == "nt":
        import msvcrt

        # ステータス表示(stderr)との同期を確保するため、プロンプトも stderr を優先する。
        # これにより、stdout のバッファリングや順序不整合による表示漏れを防ぐ。
        out = None
        try:
            if sys.stderr.isatty():
                out = sys.stderr
            elif sys.stdout.isatty():
                out = sys.stdout
            else:
                out = open("CON", "w", encoding="utf-8", errors="replace")
        except Exception:
            out = sys.stderr

        try:
            if out:
                out.write(prompt)
                out.flush()
            else:
                print(prompt, end="", flush=True)

            # 先行入力をフラッシュすると、プロンプトが出る直前の入力が消えてしまうため
            # キー入力を受け付けないように感じる原因になる。
            # ここではフラッシュしない。
            pass

            pw = []
            while True:
                # getwch() を使用して Unicode 文字を直接取得する (エコーなし)
                char = msvcrt.getwch()
                if char in ("\r", "\n"):
                    if out:
                        out.write("\n")
                        out.flush()
                    return "".join(pw)
                if char == "\x03":  # Ctrl+C
                    raise KeyboardInterrupt
                if char == "\x08":  # Backspace
                    if pw:
                        pw.pop()
                elif char == "\x00" or char == "\xe0":
                    # 特殊キー（矢印キー等）の先行バイトを読み飛ばす
                    msvcrt.getwch()
                else:
                    pw.append(char)
        except Exception:
            # 最終的なフォールバック
            if out:
                out.write("\n[WARN] getch() fallback to input()\n")
                out.flush()
            print(prompt, end="", flush=True)
            return input()
    else:
        print(prompt, end="", flush=True)
        return getpass.getpass("")


