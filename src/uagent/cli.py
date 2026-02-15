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

from uagent.utils.paths import get_history_file_path

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
        if " " in arg or "	" in arg:
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
                out.write("\n[WARN] getch() fallback to input()\n")
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
    user_lines: List[str] = []

    while True:
        try:
            # まず回答待ち状態かどうかを確認
            with core.human_ask_lock:
                is_reply = core.human_ask_active
                is_password = is_reply and core.human_ask_is_password

            # 回答待ちでない場合のみ、BUSYチェックを行う
            if not is_reply:
                with core.status_lock:
                    if core.status_busy:
                        time.sleep(0.1)
                        continue

            prompt = getattr(core, "get_prompt", lambda: "User> ")()

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

                # Windows(pyreadline)等で色コードを含むとプロンプトが二重表示される場合があるため、
                # 色付けを行わずシンプルなプロンプトを使用する。
                line = input(prompt)
        except EOFError:
            break
        except KeyboardInterrupt:
            # 入力待ち中の Ctrl+C は、現在のアクティブな状態（human_askなど）を考慮してリセット
            with core.human_ask_lock:
                if core.human_ask_active:
                    print(
                        "\n[INFO] 入力を中断しました（human_ask への回答として送信します）。"
                    )
                    # 空文字または cancel を投げてツール側を復帰させる
                    if core.human_ask_queue:
                        core.human_ask_queue.put("cancel")
                    continue

            # Ctrl+C で即座に終了シーケンスに入るように変更
            print("\n[INFO] Ctrl+C を受信しました。終了処理を開始します...")
            core.event_queue.put({"kind": "command", "text": ":exit"})
            break
        except Exception as e:
            # スレッドの突然死を防ぐための広域キャッチ
            print(
                f"\n[ERROR] stdin_loop で予期せぬエラーが発生しました: {e}",
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
                        "（複数行入力モード: 本文を複数行で入力し、\n"
                        f'  やり直す場合は """retry、最後に {core.MULTI_INPUT_SENTINEL} の行で終了）'
                    )
                else:
                    core.set_status(True, "replying")
                    with core.human_ask_lock:
                        if core.human_ask_queue:
                            core.human_ask_queue.put(line)

                    # human_ask_tool 側が finally で human_ask_active を False に戻す前に
                    # 次の input() に入ると、余計に [REPLY] > が表示されることがある。
                    # 短時間だけ完了を待ってからプロンプトへ戻す。
                    for _ in range(50):  # up to ~0.5s
                        with core.human_ask_lock:
                            if not core.human_ask_active:
                                break
                        time.sleep(0.01)
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
                    print("[REPLY] 中断します。")
                    should_wait_completion = True
                elif line == '"""retry':
                    with core.human_ask_lock:
                        core.human_ask_lines.clear()
                    print(
                        "[REPLY] これまでの入力を破棄しました。最初から入力してください。"
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
                    print("[REPLY] 複数行の回答を受け取りました。")
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
                    "（複数行入力モード: 本文を複数行で入力し、\n"
                    f'  やり直す場合は """retry、最後に {core.MULTI_INPUT_SENTINEL} の行で終了）'
                )
                continue

            if not line.strip():
                continue

            core.set_status(True, "user_pending")
            core.event_queue.put({"kind": "user", "text": line})
        else:
            if line == '"""retry':
                user_lines.clear()
                print("[INFO] これまでの入力を破棄しました。最初から入力してください。")
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


def _handle_docs_cli() -> None:
    """Handle `uag docs` subcommand.

    Spec (mode A):
      - `uag docs` => list
      - `uag docs <name>` => show content
      - `uag docs --path <name>` => print filesystem path
      - `uag docs --open <name>` => open with OS default app

    Docs are bundled under `scheck/docs/` and resolved via importlib.resources.
    """

    from . import docs_util

    # argv: scheck docs [--path|--open] [name]
    args = sys.argv[2:]

    if not args:
        print(docs_util.format_docs_list(docs_util.list_docs()))
        return

    if args[0] in ("--help", "-h"):
        print(docs_util.format_docs_list(docs_util.list_docs()))
        return

    if args[0] in ("--path", "--open"):
        if len(args) < 2:
            print("[docs] name is required", file=sys.stderr)
            print(docs_util.format_docs_list(docs_util.list_docs()))
            sys.exit(2)
        name = args[1]
        p = docs_util.get_doc_path(name)
        if args[0] == "--path":
            print(str(p))
            return
        docs_util.open_path_with_os(p)
        return

    name = args[0]
    text = docs_util.read_doc_text(name)
    print(text)


def main() -> None:
    # --- startup paging: capture *all* stdout/stderr until shared-memory log ---
    # This matches the requested behavior:
    # "起動直後のすべて（toolsロード行も含む）をまとめてページング".
    import io
    from contextlib import redirect_stdout, redirect_stderr

    _startup_capture_out = io.StringIO()
    _startup_capture_err = io.StringIO()

    def _flush_startup_pager_and_continue() -> None:
        from .welcome import _internal_pager

        combined = _startup_capture_out.getvalue() + _startup_capture_err.getvalue()
        if combined:
            _internal_pager(combined)

    # Capture startup logs
    with redirect_stdout(_startup_capture_out), redirect_stderr(_startup_capture_err):
        # 初回だけ README / QUICKSTART を表示（pip/wheel には post-install フックが無いので起動時に表示する）
        try:
            from .readme_util import (
                maybe_print_quickstart_on_first_run,
                maybe_print_readme_on_first_run,
            )

            maybe_print_readme_on_first_run(open_with_os=True)
            maybe_print_quickstart_on_first_run(open_with_os=True)
        except Exception:
            pass

        # Workdir init (moved from module import time into main startup capture)
        try:
            decision = _runtime_init.decide_workdir(
                cli_workdir=_cli_workdir,
                env_workdir=_env_workdir,
            )
            _runtime_init.apply_workdir(decision)
            banner = _runtime_init.build_startup_banner(
                core=core,
                workdir=decision.chosen_expanded,
                workdir_source=decision.chosen_source,
            )
            # NOTE: only for merging into startup capture; actual display is via pager.
            print(banner, end="")
        except Exception as e:
            print(f"[FATAL] workdir の設定に失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

        # docs サブコマンドは welcome 表示や LLM 初期化より先に処理する

        print_welcome()
        check_git_installation()
        ensure_mcp_config_template()

        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            if cmd == "docs":
                _handle_docs_cli()
                return
            if cmd == "gui":
                from .gui import main as gui_main

                sys.argv.pop(1)
                gui_main()
                return
            elif cmd == "web":
                from .web import main as web_main

                sys.argv.pop(1)
                web_main()
                return

        provider, client, depname = providers.make_client(core)

        if provider == "azure":
            depname = os.environ.get("UAGENT_AZURE_DEPNAME", "gpt-5.2")
        elif provider == "openai":
            depname = os.environ.get("UAGENT_OPENAI_DEPNAME", "gpt-5.2")
        elif provider == "grok":
            depname = os.environ.get("UAGENT_GROK_DEPNAME", "grok-4-1-fast-reasoning")
        elif provider == "gemini":
            depname = os.environ.get("UAGENT_GEMINI_DEPNAME", "gemini-1.5-flash")
        elif provider == "claude":
            depname = os.environ.get("UAGENT_CLAUDE_DEPNAME", "claude-sonnet-4.5")
        elif provider == "nvidia":
            depname = os.environ.get(
                "UAGENT_NVIDIA_DEPNAME", "nvidia/nemotron-3-nano-30b-a3b"
            )
        elif provider == "openrouter":
            depname = os.environ.get("UAGENT_OPENROUTER_DEPNAME", "gpt-5.2")
        else:
            depname = os.environ.get("UAGENT_OPENAI_DEPNAME", "gpt-5.2")

        print(f"model(deployment) = {depname}")

        if provider == "openrouter" and (depname or "").strip() == "openrouter/auto":
            raw_fb = (
                os.environ.get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
            ).strip()
            if raw_fb:
                print("[INFO] open router fallback models enabled")

        # LLM API selection (Responses API vs Chat Completions)
        # NOTE: Actual calls are made in scheck_llm.run_llm_rounds().
        use_responses_api = os.environ.get("UAGENT_RESPONSES", "").lower() in (
            "1",
            "true",
        )

        # Responses API is currently supported only on Azure OpenAI (and potentially OpenAI beta).
        # Grok, Gemini, Claude, etc. do not support it.
        if use_responses_api and provider not in ("azure", "openai"):
            print(
                f"[WARN] UAGENT_RESPONSES=1 is set, but provider '{provider}' does not support Responses API. Falling back to ChatCompletions."
            )
            use_responses_api = False
            # Ensure scheck_llm sees the disabled state
            os.environ["UAGENT_RESPONSES"] = "0"

        if use_responses_api:
            print("[INFO] LLM API mode = Responses (UAGENT_RESPONSES is enabled)")
        else:
            print(
                "[INFO] LLM API mode = ChatCompletions (UAGENT_RESPONSES is disabled)"
            )

        try:
            cwd = os.getcwd()
            print(f"[INFO] current workdir = {cwd}")
        except Exception:
            pass

        core.set_status(False, "")

        messages = build_initial_messages(core=core)

        print("[INFO] 長期記憶を読み込みました。")

        try:
            before_len = len(messages)
            flags = _runtime_init.append_long_memory_system_messages(
                core=core,
                messages=messages,
                build_long_memory_system_message_fn=build_long_memory_system_message,
                personal_long_memory_mod=personal_long_memory,
                shared_memory_mod=shared_memory,
            )

            # 互換: 共有メモが有効な場合のみ INFO を出す
            if flags.get("shared_enabled"):
                print("[INFO] 共有長期記憶を読み込みました。")

            # 互換: 追加された system message をすべて log に残す
            for m in messages[before_len:]:
                core.log_message(m)

        except Exception as e:
            print(f"[WARN] 共有長期記憶の読み込み中に例外が発生しました: {e}")

    # Flush startup logs via pager, then continue with normal stdout/stderr.
    _flush_startup_pager_and_continue()

    file_path = INITIAL_FILE_ARG
    if file_path is None and len(sys.argv) > 1:
        file_path = sys.argv[1]

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_text = f.read()
        except Exception:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    file_text = f.read()
            except Exception as e:
                print(
                    f"[WARN] 起動時ファイルの読み込みに失敗しました: {file_path} ({e})"
                )
                file_text = ""

        if file_text and file_text.strip():
            max_chars = 10000
            if len(file_text) > max_chars:
                file_text = file_text[:max_chars] + "\n...[truncated]"

            initial_file_msg = {
                "role": "user",
                "content": f"起動時に渡されたファイル: {file_path}\n\n{file_text}",
            }
            messages.append(initial_file_msg)
            core.log_message(initial_file_msg)
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
        else:
            core.set_status(False, "")

    # 非対話モードなら、起動時ファイル処理（あれば）後にそのまま終了する
    if UAGENT_NON_INTERACTIVE:
        core.set_status(False, "")
        print(
            "[INFO] --non-interactive が指定されたため、標準入力待ちを行わず終了します。"
        )
        return

    t = threading.Thread(target=stdin_loop, daemon=True)
    t.start()

    running = True
    try:
        while running:
            ev = core.event_queue.get()
            kind = ev.get("kind")

            if kind == "command":
                line = ev.get("text", "")
                if not handle_command(line, messages, client, depname, core=core):
                    running = False
                    break
                core.set_status(False, "")
                continue

            if kind in ("user", "timer"):
                text = ev.get("text", "")
                if not text:
                    continue

                # If Responses API is enabled (Azure/OpenAI) and the user message contains local image paths,
                # ask for explicit permission before embedding images as data URLs.
                use_responses_api = os.environ.get("UAGENT_RESPONSES", "").lower() in (
                    "1",
                    "true",
                )
                prov = (os.environ.get("UAGENT_PROVIDER") or "").lower()
                allow_multimodal = use_responses_api and prov in ("azure", "openai")

                user_msg: Dict[str, Any]

                if allow_multimodal:
                    paths = extract_image_paths(text)
                    if paths:
                        # Build a candidate list with absolute paths and sizes (best-effort).
                        infos: List[str] = []
                        ok_paths: List[str] = []
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
                                "画像ファイルパスが入力に含まれています。\n"
                                "これらの画像を LLM（外部API）へ送信して解析しますか？\n\n"
                                + "\n".join(infos)
                                + "\n\n"
                                "送信する場合は y、送信しない場合は n（または c/cancel）を入力してください。"
                            )
                            try:
                                core.set_status(False, "")
                                res_json = tools.run_tool(
                                    "human_ask", {"message": msg, "is_password": False}
                                )
                                res = json.loads(res_json)
                                ans = (res.get("user_reply") or "").strip().lower()
                            except Exception as e:
                                ans = "n"
                                print(
                                    f"[WARN] 画像送信確認に失敗したため送信しません: {type(e).__name__}: {e}"
                                )

                            if ans in ("y", "yes"):
                                parts: List[Dict[str, Any]] = [
                                    {"type": "text", "text": text}
                                ]
                                for abspath in ok_paths:
                                    try:
                                        data_url = image_file_to_data_url(
                                            abspath, max_bytes=10_000_000
                                        )
                                        parts.append(
                                            {
                                                "type": "image_url",
                                                "image_url": {"url": data_url},
                                            }
                                        )
                                    except Exception as e:
                                        parts.append(
                                            {
                                                "type": "text",
                                                "text": f"[WARN] 画像添付に失敗しました: {abspath} ({type(e).__name__}: {e})",
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

            print(f"[WARN] 未知のイベント kind={kind!r}: {ev!r}")
    finally:
        # プログラム終了時にキャッシュをクリア
        if provider == "gemini" and client:
            try:
                from .gemini_cache_mgr import GeminiCacheManager

                mgr = GeminiCacheManager(depname)
                mgr.clear_cache(client)
            except Exception:
                pass

        core.set_status(False, "")
        print("scheck.py を終了しました。")


if __name__ == "__main__":
    main()
