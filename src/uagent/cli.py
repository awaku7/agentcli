from __future__ import annotations

import uagent.runtime_init  # noqa: F401
import getpass
import re
import importlib
import json
import os

from .env_utils import env_get
import sys

from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

import threading
import time
import atexit
from typing import Any

from . import tools

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
from .cli_startup import run_cli_startup as _run_cli_startup
from .uagent_env_keys import _is_placeholder_uagent_key, get_known_uagent_env_keys
from .scheduler import start_background_scheduler, stop_background_scheduler


from uagent.utils.paths import get_history_file_path

from .util_tools import (
    extract_image_paths,
    image_file_to_data_url,
    parse_startup_args as _parse_startup_args,
    handle_command,
)

# scheck_core をインポート
core = importlib.import_module(".core", package="uagent")


# Readline history setup
_HISTORY_FILE = str(get_history_file_path())

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
_env_workdir = env_get("UAGENT_WORKDIR")

UAGENT_NON_INTERACTIVE = bool(_startup_args.get("non_interactive"))


# NOTE(Mode A): workdir initialization (mkdir/chdir + startup info) is performed inside main()
# under startup stdout/stderr capture, so importing this module does not change CWD.

# 初期ファイル引数は unknown の最初の要素があればそれを使う（従来の sys.argv[1] 相当）
INITIAL_FILE_ARG = _startup_unknown[0] if _startup_unknown else None


# ------------------------------
# Readline TAB completion (interactive TTY only)
# - Only for :cd, :ls, :rm, and :env arguments
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


def _uagent_env_candidates(prefix: str = "") -> list[str]:
    keys = set(get_known_uagent_env_keys())
    keys.update(
        k
        for k in os.environ
        if k.startswith("UAGENT_") and not _is_placeholder_uagent_key(k)
    )
    if prefix:
        keys = {k for k in keys if k.lower().startswith(prefix.lower())}
    return sorted(keys, key=str.lower)


def _uagent_path_candidates(prefix: str) -> list[str]:
    # Return completion candidates for a filesystem path prefix.
    # Notes:
    # - We keep the *typed* directory prefix (including original slashes) so we don't
    #   accidentally duplicate segments (e.g. 'src' -> 'src\src\...').
    # - We expand ~ and envvars only for scanning the filesystem.

    # Expand for filesystem scanning
    expanded = os.path.expandvars(os.path.expanduser(prefix))

    # Find last separator in the *typed* prefix and in the expanded prefix.
    # We use the typed one to preserve what the user typed.
    last_sep_typed = max(prefix.rfind("/"), prefix.rfind("\\"))
    last_sep_expanded = max(expanded.rfind("/"), expanded.rfind("\\"))

    if last_sep_expanded >= 0:
        scan_dir = expanded[: last_sep_expanded + 1]
        base = expanded[last_sep_expanded + 1 :]
    else:
        scan_dir = ""
        base = expanded

    # This is what we will prepend to returned candidates (exactly as typed)
    if last_sep_typed >= 0:
        out_prefix_raw = prefix[: last_sep_typed + 1]
        typed_sep = prefix[last_sep_typed]
    else:
        out_prefix_raw = ""
        typed_sep = os.sep

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
        suffix = typed_sep if os.path.isdir(full) else ""

        cands.append(out_prefix_raw + name + suffix)

    cands.sort(key=lambda x: x.lower())
    return cands


def _uagent_rl_completer(text_part: str, state: int):
    # readline completer for ':cd' / ':ls' / ':rm' / ':cp' / ':mv' / ':head' / ':env'
    #
    # Important: readline expects the returned string to replace the current
    # token fragment (text_part), not the whole argument. If we return the full
    # argument, readline may append it and cause duplicated segments.
    try:
        if not readline:
            return None

        buf = readline.get_line_buffer() or ""
        cmd, arg, _arg_start = _uagent_split_cmd_arg(buf)

        if cmd not in ("cd", "ls", "rm", "cp", "mv", "head", "tail", "env"):
            return None

        if cmd == "env":
            env_subs = ("show", "set", "unset", "save")
            parts = [p for p in re.split(r"[ 	]+", arg) if p != ""]
            ends_ws = bool(arg) and arg[-1] in (" ", "	")

            if not parts:
                cands = [s for s in env_subs if s.startswith(text_part.lower())]
            else:
                sub = parts[0].lower()
                if sub not in env_subs:
                    cands = [s for s in env_subs if s.startswith(text_part.lower())]
                elif sub == "save":
                    return None
                else:
                    if len(parts) == 1 and not ends_ws:
                        cands = [s for s in env_subs if s.startswith(text_part.lower())]
                    else:
                        prefix = parts[-1] if len(parts) >= 2 and not ends_ws else ""
                        cands = _uagent_env_candidates(prefix)

            if not cands:
                return None
            if state >= len(cands):
                return None
            return cands[state]

        prefix = arg
        if cmd in ("cp", "mv"):
            parts = [p for p in re.split(r"[ 	]+", arg) if p != ""]
            if len(parts) > 2:
                return None
            if len(parts) == 0:
                prefix = ""
            elif len(parts) == 1:
                prefix = parts[0]
            else:
                prefix = parts[1]
        else:
            # Only complete a single path argument; if spaces already present in arg, stop.
            if " " in arg or "	" in arg:
                return None

        # For :ls/:rm, if arg already contains glob meta, do not complete (avoid odd mixes)
        if cmd in ("ls", "rm") and _uagent_has_glob_meta(prefix):
            return None

        cands = _uagent_path_candidates(prefix)
        if state >= len(cands):
            return None

        return cands[state]
    except Exception:
        return None


def _uagent_setup_readline_completion() -> None:
    # Enable TAB completion when readline is available.
    # Some Windows/pyreadline environments report non-tty stdin even when
    # interactive completion still works, so do not gate on isatty().
    if not readline:
        return

    try:
        for binding in ("tab: complete", "Tab: complete", "Control-i: complete"):
            try:
                readline.parse_and_bind(binding)
            except Exception:
                pass

        # Keep readline from splitting path fragments on separators.
        if hasattr(readline, "set_completer_delims"):
            readline.set_completer_delims(" ")

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
            r, _w, _x = select.select([fd], [], [], 0)
            if not r:
                break
            try:
                _os.read(fd, 4096)
            except Exception:
                break
    except Exception:
        pass


def _getpass_fallback(prompt: str) -> str:
    """Fallback for environments where getpass.getpass cannot disable echo back (e.g. isatty=False)."""
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
            # キー入力を受け付けないように感じる原因になる。ここではフラッシュしない。
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
                out.write("\n[WARN] " + _("getch() fallback to input()") + "\n")
                out.flush()
            print(prompt, end="", flush=True)
            return input()
    else:
        print(prompt, end="", flush=True)
        return getpass.getpass("")


def stdin_loop() -> None:
    """
    標準入力を読み取り、core.event_queue にイベントを積む
    """
    user_multiline_active = False
    user_lines: list[str] = []

    while True:
        try:
            # まず回答待ち状態かどうかを確認
            with core.human_ask_lock:
                is_reply = core.human_ask_active
                is_password = is_reply and core.human_ask_is_password

            # 回答待ちでない場合のみ、BUSYチェックを行う
            # ただし BUSY 中でも既に表示済みプロンプトに対するユーザー入力は受け付ける。
            # ここで待機してしまうと、LLM/ツール実行中に表示済みだったプロンプトへ入力された
            # 1 行が読み取られないまま残り、次の入力イベントが必要になることがある。
            # Prompt is resolved *only when we are ready to actually read input*.
            # If we compute it while BUSY and then loop/sleep, it can become stale
            # (e.g. show a normal prompt while a human_ask is actually active).

            if is_password:
                # When replying to a prompt (human_ask password), flush any pending
                # typeahead to prevent unintended immediate submission.
                if is_reply:
                    _flush_stdin_input_buffer()

                if os.name == "nt":
                    line = _getpass_fallback("[PASSWORD] > ")
                elif sys.stdin.isatty() and sys.stdout.isatty():
                    line = getpass.getpass("[PASSWORD] > ")
                else:
                    line = _getpass_fallback("[PASSWORD] > ")
            else:
                # When replying to a prompt (human_ask), flush any pending typeahead
                # to prevent unintended immediate submission.
                if is_reply:
                    _flush_stdin_input_buffer()

                # NOTE: LLM/Tools 応答開始と stdin_loop が競合すると、BUSY中にも関わらず
                # プロンプトだけが表示されることがある。
                # ただし、ここで BUSY を理由に readline() 自体を止めると、既に表示済み
                # プロンプトに対して入力された 1 行が読み取られないまま残り、次の入力が
                # 必要になることがあるため、描画直前ではブロックしない。

                # Windows(pyreadline)等で色コードを含むとプロンプトが二重表示される場合があるため、
                # 色付けを行わずシンプルなプロンプトを使用する。
                # NOTE: input(prompt) のプロンプト描画が環境によって欠落することがあるため、
                # 常に「自前で描画 → input()」に統一する。
                # ステータスの色表示は core 側が stderr に出すため、この変更で色は失われない。
                try:
                    sys.stderr.flush()
                except Exception:
                    pass
                try:
                    sys.stdout.flush()
                except Exception:
                    pass

                # NOTE: 画面下部でプロンプトが見えなくなる/他出力に押し流される事があるため、
                # プロンプトは stderr(tty) を優先して描画する。
                # さらに core.print_status_line() 等の出力と競合すると押し流されるため、
                # core.print_lock で直列化する。
                out = None
                try:
                    if getattr(sys.stderr, "isatty", lambda: False)():
                        out = sys.stderr
                    else:
                        out = sys.stdout
                except Exception:
                    out = sys.stdout

                try:
                    sys.stderr.flush()
                except Exception:
                    pass
                try:
                    sys.stdout.flush()
                except Exception:
                    pass

                # 応答直後の出力競合を避けるため、短い安定化待ち
                time.sleep(0.1)

                try:
                    if not is_reply:
                        with core.human_ask_lock:
                            if core.human_ask_active:
                                continue
                        if getattr(core, "status_busy", False):
                            time.sleep(0.1)
                            continue

                    lock = getattr(core, "print_lock", None)
                    if lock is None:
                        lock = threading.RLock()

                    with lock:
                        prompt = getattr(core, "get_prompt", lambda: "User> ")()
                        if out:
                            out.write(prompt)
                            out.flush()
                        else:
                            print(prompt, end="", flush=True)
                except Exception:
                    # 最終フォールバック
                    try:
                        print(prompt, end="", flush=True)
                    except Exception:
                        pass

                # Read input without using input(), to avoid stdout/stderr prompt interleaving issues
                # (input() may implicitly write to stdout depending on environment).
                # For normal prompts, avoid an indefinite blocking readline() so that
                # a newly-started human_ask can switch the prompt promptly.
                if is_reply:
                    line = sys.stdin.readline()
                    if line == "":
                        raise EOFError
                else:
                    line = None

                    # If readline is available, prefer input("") so TAB completion works.
                    # UAGENT_SIMPLE_PROMPT defaults to 0; set 1/true/yes/on to disable.
                    use_simple_prompt = str(
                        env_get("UAGENT_SIMPLE_PROMPT", "0") or ""
                    ).lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    )
                    # We already printed the prompt ourselves.
                    if readline and sys.stdin.isatty() and not use_simple_prompt:
                        try:
                            line = input("")
                        except EOFError:
                            raise
                    elif os.name == "nt":
                        try:
                            import msvcrt  # type: ignore

                            while True:
                                with core.human_ask_lock:
                                    if core.human_ask_active:
                                        break
                                if msvcrt.kbhit():
                                    line = sys.stdin.readline()
                                    if line == "":
                                        raise EOFError
                                    break
                                time.sleep(0.1)
                        except EOFError:
                            raise
                        except Exception:
                            line = sys.stdin.readline()
                            if line == "":
                                raise EOFError
                    else:
                        try:
                            import select

                            while True:
                                with core.human_ask_lock:
                                    if core.human_ask_active:
                                        break
                                r, _w, _x = select.select([sys.stdin], [], [], 0.05)
                                if r:
                                    line = sys.stdin.readline()
                                    if line == "":
                                        raise EOFError
                                    break
                        except EOFError:
                            raise
                        except Exception:
                            line = sys.stdin.readline()
                            if line == "":
                                raise EOFError

                    if line is None:
                        continue
        except EOFError:
            break
        except KeyboardInterrupt:
            # 入力待ち中の Ctrl+C は、現在のアクティブな状態（human_askなど）を考慮してリセット
            with core.human_ask_lock:
                if core.human_ask_active:
                    print(
                        "\n[INFO] "
                        + "Input cancelled (will be sent as a reply to human_ask)."
                    )
                    # 空文字または cancel を投げてツール側を復帰させる
                    if core.human_ask_queue:
                        core.human_ask_queue.put("cancel")
                    continue

            # Ctrl+C で即座に終了シーケンスに入るように変更
            print("\n[INFO] " + "Received Ctrl+C. Starting shutdown...")
            core.event_queue.put({"kind": "command", "text": ":exit"})
            break
        except Exception as e:
            # スレッドの突然死を防ぐための広域キャッチ
            print(
                "\n[ERROR] " + "Unexpected error in stdin_loop: %(err)s" % {"err": e},
                file=sys.stderr,
            )
            time.sleep(1)
            continue

        line = line.rstrip("\n")

        # human_ask への応答処理
        handled_human_ask = False
        with core.human_ask_lock:
            if core.human_ask_active and core.human_ask_queue is not None:
                handled_human_ask = True
                is_ha_multiline = core.human_ask_multiline_active
                is_ha_password = core.human_ask_is_password

        if handled_human_ask:
            should_wait_completion = False
            if not is_ha_multiline:
                # パスワード入力時は 'f' を複数行モードへの切り替えコマンドとして扱わない
                if line == "f" and not is_ha_password:
                    with core.human_ask_lock:
                        core.human_ask_multiline_active = True
                        core.human_ask_lines.clear()
                    print(
                        _(
                            '(Multiline input mode: enter the body in multiple lines; to restart, type """retry; finish with a line containing %(sentinel)s)'
                        )
                        % {"sentinel": core.MULTI_INPUT_SENTINEL}
                    )
                else:
                    core.set_status(True, "replying")
                    with core.human_ask_lock:
                        if core.human_ask_queue:
                            core.human_ask_queue.put(line)

                    # human_ask_tool 側が finally で human_ask_active を False に戻す前に
                    # 次の input() に入ると、余計に [REPLY] > が表示されることがある。
                    # 短時間だけ完了を待ってからプロンプトへ戻す。
                    for _i in range(50):  # up to ~0.5s
                        with core.human_ask_lock:
                            if not core.human_ask_active:
                                break
                        time.sleep(0.03)
                    # NOTE: Do not print acknowledgement here. It can interleave with subsequent human_ask prompts
                    # and confuse the user when multiple human_ask calls happen back-to-back.
                    should_wait_completion = True
            else:
                # 複数行モード中でも c / cancel 単独行なら中断として扱う
                if line.strip().lower() in ("c", "cancel"):
                    core.set_status(True, "replying_cancel")
                    with core.human_ask_lock:
                        core.human_ask_lines.clear()
                        core.human_ask_multiline_active = False
                        if core.human_ask_queue:
                            core.human_ask_queue.put(line)
                    print("[REPLY] " + _("Cancelled."))
                    should_wait_completion = True
                elif line == '"""retry':
                    with core.human_ask_lock:
                        core.human_ask_lines.clear()
                    print(
                        "[REPLY] " + _("Discarded previous input. Please start over.")
                    )
                    continue
                elif line == core.MULTI_INPUT_SENTINEL:
                    core.set_status(True, "replying_multi")
                    with core.human_ask_lock:
                        reply_text = "\n".join(core.human_ask_lines)
                        core.human_ask_lines.clear()
                        core.human_ask_multiline_active = False
                        if core.human_ask_queue:
                            core.human_ask_queue.put(reply_text)
                    print("[REPLY] " + _("Received multiline reply."))
                    should_wait_completion = True
                else:
                    with core.human_ask_lock:
                        core.human_ask_lines.append(line)

            # 完了待機を行わず、メインループに戻る（status_busy が True の間は次回の入力を抑制するため）
            # ここで待機すると、複数の human_ask が連続した際にデッドロックする可能性があるため削除
            if should_wait_completion:
                pass
            continue

        if not user_multiline_active:
            if line.startswith(":"):
                core.set_status(True, "command_pending")
                core.event_queue.put({"kind": "command", "text": line})
                continue

            if line == "f":
                user_multiline_active = True
                user_lines.clear()
                print(
                    _(
                        '(Multiline input mode: enter the body in multiple lines; to restart, type """retry; finish with a line containing %(sentinel)s)'
                    )
                    % {"sentinel": core.MULTI_INPUT_SENTINEL}
                )
                continue

            if not line.strip():
                if os.name != "nt":
                    print()
                continue

            core.set_status(True, "user_pending")
            core.event_queue.put({"kind": "user", "text": line})
        else:
            if line == '"""retry':
                user_lines.clear()
                print("[INFO] " + _("Discarded previous input. Please start over."))
                continue

            if line == core.MULTI_INPUT_SENTINEL:
                text = "\n".join(user_lines)
                user_lines.clear()
                user_multiline_active = False

                if not text.strip():
                    continue

                core.set_status(True, "user_pending_multi")
                core.event_queue.put({"kind": "user", "text": text})
            else:
                user_lines.append(line)


def main() -> None:
    _uagent_setup_readline_completion()

    startup = _run_cli_startup(
        core=core,
        cli_workdir=_cli_workdir,
        env_workdir=_env_workdir,
        initial_file_arg=INITIAL_FILE_ARG,
        non_interactive=UAGENT_NON_INTERACTIVE,
    )

    provider = startup.provider
    client = startup.client
    depname = startup.depname
    messages = startup.messages

    if startup.should_exit:
        return

    start_background_scheduler(core.event_queue)

    t = threading.Thread(target=stdin_loop, daemon=True)
    t.start()

    running = True
    try:
        while running:
            ev = core.event_queue.get()
            kind = ev.get("kind")

            if kind == "command":
                line = ev.get("text", "")
                result = handle_command(line, messages, client, depname, core=core)
                if not result:
                    running = False
                    break
                core.set_status(False, "")
                if getattr(result, "run_llm", False):
                    prompt = getattr(result, "prompt", None) or "Run the loaded skill."
                    user_msg = {"role": "user", "content": prompt}
                    messages.append(user_msg)
                    core.log_message(user_msg)
                    llm_util.run_llm_rounds(
                        provider,
                        client,
                        depname,
                        messages,
                        core=core,
                        make_client_fn=providers.make_client,
                        append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                        try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                    )
                continue

            if kind == "schedule_notice":
                notice = (ev.get("text", "") or "").strip()
                if notice:
                    print("[INFO] " + notice)
                continue

            if kind in ("user", "timer"):
                text = ev.get("text", "")
                if not text:
                    continue

                # If Responses API is enabled (Azure/OpenAI) and the user message contains local image paths,
                # ask for explicit permission before embedding images as data URLs.
                use_responses_api = env_get("UAGENT_RESPONSES", "").lower() in (
                    "1",
                    "true",
                )
                prov = (env_get("UAGENT_PROVIDER") or "").lower()
                allow_multimodal = use_responses_api and prov in (
                    "azure",
                    "openai",
                    "bedrock",
                )

                user_msg: dict[str, Any]

                if allow_multimodal:
                    paths = extract_image_paths(text)
                    if paths:
                        # Build a candidate list with absolute paths and sizes (best-effort).
                        infos: list[str] = []
                        ok_paths: list[str] = []
                        for p in paths:
                            try:
                                expanded = os.path.expandvars(os.path.expanduser(p))
                                abspath = os.path.abspath(expanded)
                                if not os.path.isfile(abspath):
                                    infos.append(f"- {p} (not found)")
                                    continue
                                size = os.path.getsize(abspath)
                                infos.append(f"- {abspath} ({size} bytes)")
                                ok_paths.append(abspath)
                            except Exception as e:
                                infos.append(f"- {p} (error: {type(e).__name__}: {e})")

                        if ok_paths:
                            msg = (
                                _(
                                    "Image file paths were found in your input.\n"
                                    "Do you want to send these images to the LLM (external API) for analysis?\n\n"
                                )
                                + "\n".join(infos)
                                + "\n\n"
                                + _(
                                    "Reply with y to send, or n (or c/cancel) to skip sending."
                                )
                            )
                            try:
                                core.set_status(False, "")
                                res_json = tools.run_tool(
                                    "human_ask", {"message": msg, "is_password": False}
                                )
                                try:
                                    res = json.loads(res_json)
                                    ans = (res.get("user_reply") or "").strip().lower()
                                except Exception:
                                    ans = (res_json or "").strip().lower()
                            except Exception as e:
                                ans = "n"
                                print(
                                    "[WARN] "
                                    + _(
                                        "Image send confirmation failed; will not send images: %(etype)s: %(err)s"
                                    )
                                    % {"etype": type(e).__name__, "err": e}
                                )

                            if ans in ("y", "yes"):
                                parts: list[dict[str, Any]] = [
                                    {"type": "text", "text": text}
                                ]
                                for abspath in ok_paths:
                                    try:
                                        data_url = image_file_to_data_url(
                                            abspath, max_bytes=10_000_000
                                        )
                                        parts.append(
                                            {
                                                # Responses API expects input_image with image_url as a string.
                                                "type": "input_image",
                                                "image_url": data_url,
                                            }
                                        )
                                    except Exception as e:
                                        parts.append(
                                            {
                                                "type": "text",
                                                "text": "[WARN] "
                                                + (
                                                    _(
                                                        "Failed to attach image: %(path)s (%(etype)s: %(err)s)"
                                                    )
                                                    % {
                                                        "path": abspath,
                                                        "etype": type(e).__name__,
                                                        "err": e,
                                                    }
                                                ),
                                            }
                                        )
                                user_msg = {"role": "user", "content": parts}
                            else:
                                user_msg = {"role": "user", "content": text}
                        else:
                            user_msg = {"role": "user", "content": text}
                    else:
                        user_msg = {"role": "user", "content": text}
                else:
                    user_msg = {"role": "user", "content": text}

                messages.append(user_msg)
                core.log_message(user_msg)

                llm_util.run_llm_rounds(
                    provider,
                    client,
                    depname,
                    messages,
                    core=core,
                    make_client_fn=providers.make_client,
                    append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                    try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                )
                continue

            print(
                "[WARN] "
                + _("Unknown event kind=%(kind)r: %(ev)r") % {"kind": kind, "ev": ev}
            )
    finally:
        try:
            stop_background_scheduler()
        except Exception:
            pass
        # プログラム終了時にキャッシュをクリア
        if provider in ("gemini", "vertexai") and client:
            try:
                from .gemini_cache_mgr import GeminiCacheManager

                mgr = GeminiCacheManager(depname)
                mgr.clear_cache(client)
            except Exception:
                pass

        core.set_status(False, "")
        print(_("Exited uag."))


if __name__ == "__main__":
    main()
