from __future__ import annotations

import uagent.runtime.runtime_init  # noqa: F401
import getpass
import importlib
import json
import os

from .env_utils import env_get
from .uagent_env_keys import get_known_uagent_env_keys
import sys

from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

import threading
import time
from typing import Any

from . import tools

tools.configure_default_confirmation()
from .runtime.logging_setup import log_event
from .runtime.execution import lifecycle_execution

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


# OpenAI / Azure OpenAI / Google Gemini (google-genai)
# These are imported lazily inside the functions that actually need them to speed up CLI startup.
OpenAI = None
genai = None
gemini_types = None
gemini_errors = None

from .providers import util_providers as providers
from . import util_tools as tools_util
from .cli_startup import run_cli_startup as _run_cli_startup
from .scheduler import start_background_scheduler, stop_background_scheduler

from uagent.utils.paths import get_history_file_path

from .tools.pybitchat_shared import (
    forward_to_mesh,
    is_chat_mode,
    reply_to_mesh,
    set_llm_event_queue,
)

from .util_tools import (
    extract_image_paths,
    provider_allows_chat_vision,
    build_multimodal_user_message,
    parse_startup_args as _parse_startup_args,
    handle_command,
)

# Import scheck_core
core = importlib.import_module(".core", package="uagent")

_startup_args, _startup_unknown = _parse_startup_args()
_cli_workdir = _startup_args.get("workdir")
_env_workdir = env_get("UAGENT_WORKDIR")

UAGENT_NON_INTERACTIVE = bool(_startup_args.get("non_interactive"))
UAGENT_INJECT_MESSAGE = _startup_args.get("inject_message")
if UAGENT_INJECT_MESSAGE is not None:
    UAGENT_NON_INTERACTIVE = True
UAGENT_TOOL_GENRE_MASK = _startup_args.get("tool_genre_mask")
UAGENT_ENABLE_TOOLS = _startup_args.get("enable_tools")
UAGENT_REALTIME = bool(_startup_args.get("realtime"))

# Initialize the shared Computer Use policy override before startup config is used.
_computer_use_arg = _startup_args.get("computer_use")
if _computer_use_arg is not None:
    os.environ["UAGENT_COMPUTER_USE"] = "1" if _computer_use_arg else "0"

# Initialize runtime tools_enabled flag.
# Priority: --use-tool / --no-use-tool CLI arg > UAGENT_USE_TOOL env var > default ON.
_use_tool_arg = _startup_args.get("use_tool")
if _use_tool_arg is not None:
    core.tools_enabled = bool(_use_tool_arg)
else:
    _use_tool_env = (env_get("UAGENT_USE_TOOL") or "").strip().lower()
    core.tools_enabled = _use_tool_env not in ("0", "false", "no", "off")

# NOTE(Mode A): workdir initialization (mkdir/chdir + startup info) is performed inside main()
# under startup stdout/stderr capture, so importing this module does not change CWD.

# Use the first element of unknown as the initial file argument if present (equivalent to the traditional sys.argv[1])
INITIAL_FILE_ARG = _startup_unknown[0] if _startup_unknown else None

_PROMPT_SESSION: Any = None
_PROMPT_REPLY_SESSION: Any = None
_PROMPT_HISTORY: list[str] = []


def _append_prompt_history_entry(text: str) -> None:
    normalized = tools_util.strip_surrogates((text or "").replace("\r", "").strip())
    if not normalized:
        return
    if normalized not in _PROMPT_HISTORY:
        _PROMPT_HISTORY.append(normalized)

    for session in (_PROMPT_SESSION, _PROMPT_REPLY_SESSION):
        if session is None:
            continue
        history = getattr(session, "history", None)
        append_string = getattr(history, "append_string", None)
        if callable(append_string):
            try:
                append_string(normalized)
            except Exception:
                pass


def _bootstrap_prompt_history(messages: list[dict[str, Any]]) -> None:
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            _append_prompt_history_entry(content)


def _persist_prompt_history_entry(text: str) -> None:
    normalized = tools_util.strip_surrogates(
        (text or "")
        .replace(
            "\
",
            "",
        )
        .strip()
    )
    if not normalized:
        return

    try:
        from datetime import datetime

        history_path = get_history_file_path()
        os.makedirs(history_path.parent, exist_ok=True)
        with open(history_path, "ab") as f:
            f.write(f"\
# {datetime.now()}\
".encode("utf-8"))
            for line in normalized.split("\
"):
                f.write(f"+{line}\
".encode("utf-8"))
    except Exception:
        pass


def _get_prompt_session(*, reply: bool = False) -> Any:
    global _PROMPT_SESSION, _PROMPT_REPLY_SESSION
    if reply:
        if _PROMPT_REPLY_SESSION is False:
            return None
        if _PROMPT_REPLY_SESSION is None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.history import InMemoryHistory
            except Exception:
                _PROMPT_REPLY_SESSION = False
                return None

            try:
                session = PromptSession(history=InMemoryHistory())
                for entry in _PROMPT_HISTORY:
                    try:
                        session.history.append_string(entry)
                    except Exception:
                        pass
                _PROMPT_REPLY_SESSION = session
            except Exception:
                _PROMPT_REPLY_SESSION = False
                return None
        return _PROMPT_REPLY_SESSION

    if _PROMPT_SESSION is False:
        return None
    if _PROMPT_SESSION is None:
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.document import Document
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.completion import (
                Completer,
                Completion,
                PathCompleter,
            )
        except Exception:
            _PROMPT_SESSION = False
            return None

        try:

            class _SafeFileHistory(FileHistory):
                """FileHistory that strips lone surrogates before disk write."""

                def append_string(self, string: str) -> None:
                    super().append_string(tools_util.strip_surrogates(string))

            # Custom completer: :ls/:cd → path completion, others → command completion
            class _CommandCompleter(Completer):
                def get_completions(self, document, complete_event):
                    text = document.text_before_cursor
                    stripped = text.lstrip()
                    # Snapshot the dynamic command map once per completion request.
                    # block=False: never block on first-time plugin import; the
                    # background warmup keeps loading and partial results are fine.
                    dyn_map = tools.get_dynamic_commands_map(block=False)

                    # Free-form path completion: ./ or ../ prefix
                    if stripped.startswith(("./", "../")):
                        path_doc = Document(
                            text=stripped,
                            cursor_position=len(stripped),
                        )
                        for comp in PathCompleter().get_completions(
                            path_doc, complete_event
                        ):
                            yield comp
                        return

                    # Path completion for file-operating commands
                    path_cmds = (
                        ":ls ",
                        ":cd ",
                        ":rm ",
                        ":cp ",
                        ":mv ",
                        ":head ",
                        ":tail ",
                        ":load ",
                        # Free-form commands (without :)
                        "ls ",
                        "rm ",
                        "cp ",
                        "mv ",
                        "cat ",
                    )
                    if stripped.startswith(path_cmds):
                        # Strip the command prefix so PathCompleter sees only the path
                        prefix_end = stripped.index(" ") + 1
                        path_text = stripped[prefix_end:]
                        path_doc = Document(
                            text=path_text,
                            cursor_position=len(path_text),
                        )
                        for comp in PathCompleter().get_completions(
                            path_doc, complete_event
                        ):
                            yield comp
                    elif stripped.startswith(":env "):
                        # :env subcommand completion
                        after_env = stripped[len(":env ") :]
                        if " " not in after_env:
                            env_subcmds = [
                                "help",
                                "h",
                                "?",
                                "show",
                                "list",
                                "set",
                                "unset",
                                "save",
                            ]
                            for sc in env_subcmds:
                                if sc.startswith(after_env):
                                    yield Completion(
                                        sc,
                                        start_position=-len(after_env),
                                    )
                        elif any(
                            after_env.startswith(cmd + " ")
                            for cmd in ("show", "set", "unset")
                        ):
                            # :env show/set/unset KEY → complete UAGENT_* env var names
                            key_prefix = (
                                after_env.split(" ", 1)[1] if " " in after_env else ""
                            )
                            seen = set()
                            for ek in sorted(
                                set(get_known_uagent_env_keys())
                                | set(os.environ.keys())
                            ):
                                if ek.upper().startswith(
                                    "UAGENT_"
                                ) and ek.lower().startswith(key_prefix.lower()):
                                    if ek not in seen:
                                        seen.add(ek)
                                        yield Completion(
                                            ek,
                                            start_position=-len(key_prefix),
                                        )
                    elif stripped.startswith((":help ", ":h ", ":? ")):
                        # Complete built-in and dynamically registered help topics.
                        if stripped.startswith(":help "):
                            help_prefix_len = len(":help ")
                        elif stripped.startswith(":h "):
                            help_prefix_len = len(":h ")
                        else:
                            help_prefix_len = len(":? ")
                        help_arg = stripped[help_prefix_len:]
                        if " " not in help_arg:
                            help_topics = {
                                "help",
                                "h",
                                "?",
                                "cd",
                                "ls",
                                "logs",
                                "load",
                                "cont",
                                "clean",
                                "shrink",
                                "shrink_llm",
                                "tokens",
                                "response",
                                "env",
                                "skills",
                                "tools",
                                "tool",
                                "auto",
                                "model",
                                "r",
                                "reasoning",
                                "v",
                                "verbosity",
                                "mem-list",
                                "mem-del",
                                "profile",
                                "profile-fromlog",
                                "profile-clear",
                                "cp",
                                "mv",
                                "rm",
                                "head",
                                "tail",
                                "reload",
                                "exit",
                                "quit",
                            }
                            help_topics.update(dyn_map)
                            for topic in sorted(help_topics):
                                if topic.startswith(help_arg):
                                    yield Completion(
                                        topic, start_position=-len(help_arg)
                                    )
                    elif stripped.startswith((":tools ", ":tool ")):
                        # :tools or :tool subcommand completion
                        cmd_prefix_len = (
                            len(":tool ")
                            if stripped.startswith(":tool ")
                            else len(":tools ")
                        )
                        cmd_name = "tool" if stripped.startswith(":tool ") else "tools"
                        after_tools = stripped[cmd_prefix_len:]
                        if " " not in after_tools:
                            tools_subcmds = sorted(
                                set(dyn_map.get(cmd_name, []))
                                | {"list", "load", "on", "off", "reload", "output"}
                            )
                            for sc in tools_subcmds:
                                if sc.startswith(after_tools):
                                    yield Completion(
                                        sc, start_position=-len(after_tools)
                                    )
                        elif after_tools.startswith("create "):
                            # :tool create <name> [--lang python|rust] [--description ...] [--output-dir ...]
                            create_arg = after_tools[len("create ") :]
                            create_parts = create_arg.split()
                            if create_arg.endswith(" "):
                                if "--lang" not in create_parts:
                                    yield Completion("--lang", start_position=0)
                                if "--description" not in create_parts:
                                    yield Completion("--description", start_position=0)
                                if "--output-dir" not in create_parts:
                                    yield Completion("--output-dir", start_position=0)
                            else:
                                last_token = create_parts[-1] if create_parts else ""
                                if (
                                    len(create_parts) >= 2
                                    and create_parts[-2] == "--lang"
                                ):
                                    lang_opts = ["python", "rust"]
                                    for lo in lang_opts:
                                        if lo.startswith(last_token):
                                            yield Completion(
                                                lo, start_position=-len(last_token)
                                            )
                                else:
                                    flags = ["--lang", "--description", "--output-dir"]
                                    for fl in flags:
                                        if fl not in create_parts and fl.startswith(
                                            last_token
                                        ):
                                            yield Completion(
                                                fl, start_position=-len(last_token)
                                            )
                        elif after_tools.startswith(("on ", "off ")):
                            genre_prefix = (
                                after_tools.split(" ", 1)[1]
                                if " " in after_tools
                                else ""
                            )
                            genres = [
                                "basic",
                                "file",
                                "comm",
                                "office",
                                "devel",
                                "iot",
                                "exec",
                                "external",
                                "media",
                                "index",
                            ]
                            for g in genres:
                                if g.startswith(genre_prefix):
                                    yield Completion(
                                        g, start_position=-len(genre_prefix)
                                    )
                    elif stripped.startswith(":skills "):
                        # :skills subcommand completion
                        after_skills = stripped[len(":skills ") :]
                        if " " not in after_skills:
                            skills_subcmds = sorted(
                                set(dyn_map.get("skills", []))
                                | {"list", "find", "active", "clear"}
                            )
                            for sc in skills_subcmds:
                                if sc.startswith(after_skills):
                                    yield Completion(
                                        sc, start_position=-len(after_skills)
                                    )
                        else:
                            # :skills <subcmd> <subarg> completion
                            cmd2 = after_skills.split(" ", 1)[0].lower()
                            arg2 = (
                                after_skills.split(" ", 1)[1]
                                if " " in after_skills
                                else ""
                            )
                            if cmd2 == "apm" and " " not in arg2:
                                apm_subcmds = ["list", "use", "dir", "help"]
                                for sc2 in apm_subcmds:
                                    if sc2.startswith(arg2):
                                        yield Completion(sc2, start_position=-len(arg2))
                    elif stripped.startswith(":response "):
                        # :response subcommand completion
                        after_response = stripped[len(":response ") :]
                        if " " not in after_response:
                            response_subcmds = [
                                "status",
                                "cancel",
                                "tokens",
                                "compact",
                                "items",
                                "delete",
                            ]
                            for sc in response_subcmds:
                                if sc.startswith(after_response):
                                    yield Completion(
                                        sc,
                                        start_position=-len(after_response),
                                    )
                    elif (
                        stripped.startswith(":")
                        and " " in stripped
                        and not stripped.startswith(
                            (":r ", ":reasoning ", ":v ", ":verbosity ", ":profile ")
                        )
                    ):
                        # Generic dynamic command completion
                        cmd_word = stripped.lstrip(":").split(" ", 1)[0].lower()
                        after_cmd = stripped[len(f":{cmd_word} ") :]
                        if " " not in after_cmd and cmd_word in dyn_map:
                            dyn_subcmds = dyn_map[cmd_word]
                            for sc in dyn_subcmds:
                                if sc.startswith(after_cmd):
                                    yield Completion(sc, start_position=-len(after_cmd))
                    elif stripped.startswith((":r ", ":reasoning ")):
                        # :r reasoning mode values
                        r_prefix = stripped.split(" ", 1)[1] if " " in stripped else ""
                        if " " not in r_prefix:
                            r_vals = ["0", "1", "2", "3", "auto", "minimal", "xhigh"]
                            for v in r_vals:
                                if v.startswith(r_prefix):
                                    yield Completion(v, start_position=-len(r_prefix))
                    elif stripped.startswith((":v ", ":verbosity ")):
                        # :v verbosity mode values
                        v_prefix = stripped.split(" ", 1)[1] if " " in stripped else ""
                        if " " not in v_prefix:
                            v_vals = [
                                "0",
                                "1",
                                "2",
                                "3",
                                "off",
                                "low",
                                "medium",
                                "high",
                            ]
                            for val in v_vals:
                                if val.startswith(v_prefix):
                                    yield Completion(val, start_position=-len(v_prefix))
                    elif stripped.startswith(":profile "):
                        # :profile subcommand
                        p_prefix = stripped[len(":profile ") :]
                        if " " not in p_prefix:
                            p_vals = ["fromlog"]
                            for val in p_vals:
                                if val.startswith(p_prefix):
                                    yield Completion(val, start_position=-len(p_prefix))
                    elif stripped.startswith(":") and " " not in stripped:
                        # Command name completion
                        word = stripped.lstrip(":")
                        cmds = [
                            "ls",
                            "cd",
                            "h",
                            "?",
                            "rm",
                            "cp",
                            "mv",
                            "head",
                            "tail",
                            "load",
                            "cont",
                            "save",
                            "env",
                            "help",
                            "exit",
                            "quit",
                            "logs",
                            "clear",
                            "reset",
                            "undo",
                            "redo",
                            "history",
                            "replay",
                            "tool",
                            "tools",
                            "skills",
                            "clean",
                            "auto",
                            "shrink",
                            "shrink_llm",
                            "tokens",
                            "response",
                            "r",
                            "reasoning",
                            "v",
                            "verbosity",
                            "mem-list",
                            "mem-del",
                            "profile",
                            "profile-fromlog",
                            "profile-clear",
                            "model",
                            "reload",
                            "plugin",
                        ]
                        # Add dynamic command names (e.g., "tool" from CMD_SPEC)
                        for dyn_cmd in dyn_map:
                            if dyn_cmd not in cmds:
                                cmds.append(dyn_cmd)
                        for c in cmds:
                            if c.startswith(word):
                                yield Completion(":" + c, start_position=-len(text))

            session = PromptSession(
                history=_SafeFileHistory(str(get_history_file_path())),
                completer=_CommandCompleter(),
            )
            for entry in _PROMPT_HISTORY:
                try:
                    session.history.append_string(entry)
                except Exception:
                    pass
            _PROMPT_SESSION = session
        except Exception:
            _PROMPT_SESSION = False
            return None
    return _PROMPT_SESSION


def _reset_prompt_sessions() -> None:
    """Drop prompt_toolkit sessions after an interrupted/failed prompt.

    PromptSession caches its Application/input context.  If a watcher calls
    ``Application.exit`` while a tool owns stdin, that cached context can be
    left associated with a closed Windows asyncio executor.  Reusing it makes
    every later prompt fail with ``Application is not running`` or
    ``Executor shutdown has been called``.  A new PromptSession is cheap and
    is safer than reusing a poisoned one.
    """
    global _PROMPT_SESSION, _PROMPT_REPLY_SESSION
    _PROMPT_SESSION = None
    _PROMPT_REPLY_SESSION = None


def _prompt_toolkit_input(
    prompt: str, *, is_password: bool = False, reply: bool = False
) -> str | None:
    session = _get_prompt_session(reply=reply)
    if session is None:
        return None

    try:
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.patch_stdout import patch_stdout
    except Exception:
        KeyBindings = None  # type: ignore[assignment]
        patch_stdout = None  # type: ignore

    kb = None
    if KeyBindings is not None:
        kb = KeyBindings()

        @kb.add("escape", eager=True)
        def _cancel(event: Any) -> None:
            raise KeyboardInterrupt()

    # A tool (most notably human_ask) can start while the normal prompt is
    # already inside prompt_toolkit's blocking prompt(). In that case the
    # stdin_loop cannot notice the state change until prompt() returns, while
    # the tool is waiting for the same stdin. Watch the shared state and
    # terminate the normal prompt as soon as a tool round takes ownership.
    # Reply prompts must not be interrupted: they own stdin while active.
    stop_watching = threading.Event()
    watcher: threading.Thread | None = None
    if not reply:
        prompt_app = getattr(session, "app", None)

        def _interrupt_when_busy() -> None:
            while not stop_watching.wait(0.05):
                try:
                    with core.human_ask_lock:
                        interrupted = bool(core.human_ask_active)
                    interrupted = interrupted or bool(
                        getattr(core, "status_busy", False)
                    )
                    if not interrupted:
                        continue
                    app = prompt_app
                    if app is not None:
                        # None tells stdin_loop to discard the stale normal
                        # prompt and render the current tool/reply prompt.
                        app.exit(result=None)
                    return
                except Exception:
                    return

        watcher = threading.Thread(
            target=_interrupt_when_busy,
            name="prompt-toolkit-state-watcher",
            daemon=True,
        )
        watcher.start()

    try:
        if patch_stdout is not None:
            with patch_stdout():
                result = session.prompt(
                    prompt, is_password=is_password, key_bindings=kb
                )
        else:
            result = session.prompt(prompt, is_password=is_password, key_bindings=kb)
        if result is None and not reply:
            # The state watcher intentionally exits the normal prompt when a
            # tool takes stdin.  That Application must not be reused.
            _reset_prompt_sessions()
        elif result is not None and not is_password:
            result = tools_util.strip_surrogates(result)
        return result
    except EOFError:
        raise
    except KeyboardInterrupt:
        _reset_prompt_sessions()
        return None
    except Exception:
        # Do not reuse a PromptSession whose Application/input context failed.
        _reset_prompt_sessions()
        return None
    finally:
        if watcher is not None:
            stop_watching.set()
            watcher.join(timeout=0.2)


setattr(core, "prompt_history_append", _append_prompt_history_entry)


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


def _can_use_textarea() -> bool:
    """Check if prompt_toolkit TextArea can be used for multiline editing."""
    try:
        from prompt_toolkit.widgets import TextArea  # noqa: F401
        from prompt_toolkit.application import Application  # noqa: F401

        return sys.stdin.isatty()
    except ImportError:
        return False


def _multiline_editor(initial_text: str = "") -> str | None:
    """Open a prompt_toolkit TextArea for multiline editing (non-fullscreen).

    Returns the entered text, or None if cancelled.
    """
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import TextArea as TA

    kb = KeyBindings()

    def _submit(event: Any) -> None:
        event.app.exit(result=textarea.text)

    # Ctrl+X to submit (Alt+Enter removed; Ctrl+Enter is indistinguishable from Enter on most terminals)
    kb.add("c-x")(_submit)

    @kb.add("escape")  # Esc to cancel
    def _cancel(event: Any) -> None:
        event.app.exit(result=None)

    textarea = TA(
        text=initial_text,
        multiline=True,
        focusable=True,
        style="bg:#222222 #ffffff",
        height=10,
    )

    footer = Window(
        FormattedTextControl(" [multiline] Ctrl+X: send  |  Esc: cancel"),
        height=1,
        align=WindowAlign.LEFT,
        style="bg:#444444 #ffffff",
    )

    layout = Layout(HSplit([textarea, footer]), focused_element=textarea)

    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=True,
    )

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        return None


def _getpass_fallback(prompt: str) -> str:
    """Fallback for environments where getpass.getpass cannot disable echo back (e.g. isatty=False)."""
    if os.name == "nt":
        import msvcrt

        # To ensure synchronization with the status display (stderr), the prompt also prioritizes stderr.
        # This prevents missing displays due to stdout buffering or order inconsistency.
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

            # Flushing look-ahead input would erase input entered just before the prompt appears,
            # making it feel like key inputs are not accepted. Do not flush here.
            pass

            pw = []
            while True:
                # Use getwch() to retrieve Unicode characters directly (no echo)
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
                    # Skip the leading byte of special keys (arrow keys, etc.)
                    msvcrt.getwch()
                else:
                    pw.append(char)
        except Exception:
            # Final fallback
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
    Read standard input and push events to core.event_queue.
    """
    user_multiline_active = False
    user_lines: list[str] = []
    _last_ha_reply_mono = 0.0

    while True:
        _skip = False
        try:
            # First, check if we are waiting for a reply
            with core.human_ask_lock:
                is_reply = core.human_ask_active
                is_password = is_reply and core.human_ask_is_password

            # Perform BUSY check only when not waiting for a reply.
            # However, even during BUSY, user input for an already displayed prompt is accepted.
            # If we wait here, a line entered into an already displayed prompt during LLM/tool execution
            # may remain unread, requiring another input event.
            # Prompt is resolved *only when we are ready to actually read input*.
            # If we compute it while BUSY and then loop/sleep, it can become stale
            # (e.g. show a normal prompt while a human_ask is actually active).

            if is_password:
                # When replying to a prompt (human_ask password), flush any pending
                # typeahead to prevent unintended immediate submission.
                if is_reply:
                    _flush_stdin_input_buffer()

                line = _prompt_toolkit_input(
                    "[PASSWORD] > ", is_password=True, reply=True
                )
                if line is None:
                    if os.name == "nt":
                        line = _getpass_fallback("[PASSWORD] > ")
                    elif sys.stdin.isatty() and sys.stdout.isatty():
                        line = getpass.getpass("[PASSWORD] > ")
                    else:
                        line = _getpass_fallback("[PASSWORD] > ")
            else:
                # When replying to a prompt (human_ask), flush any pending typeahead
                # to prevent unintended immediate submission. Skip the flush right
                # after a previous reply (e.g. :skills number selection then 'y'
                # confirmation) so fast consecutive replies are not discarded.
                if is_reply and (
                    is_password or time.monotonic() - _last_ha_reply_mono >= 2.0
                ):
                    _flush_stdin_input_buffer()

                # NOTE: If LLM/Tools response start conflicts with stdin_loop, only the prompt
                # might be displayed even though it is BUSY.
                # However, if we stop waiting for input itself here because of BUSY, a line entered
                # into an already displayed prompt may remain unread, requiring another input,
                # so we do not block immediately before drawing.

                # Since prompts containing color codes may be displayed twice in Windows (pyreadline) etc.,
                # use a simple prompt without coloring.
                # NOTE: Since prompt drawing by input(prompt) may be missing depending on the environment,
                # always unify to "draw manually -> input()".
                # Since the status color display is output to stderr by the core side, colors are not lost by this change.
                try:
                    sys.stderr.flush()
                except Exception:
                    pass
                try:
                    sys.stdout.flush()
                except Exception:
                    pass

                # NOTE: Since the prompt may become invisible at the bottom of the screen or washed away by other outputs,
                # prioritize drawing the prompt on stderr (tty).
                # Furthermore, since it may be washed away if it conflicts with outputs like core.print_status_line(),
                # serialize with core.print_lock.
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

                # Short stabilization wait to avoid output conflicts immediately after response
                time.sleep(0.1)

                if not is_reply:
                    with core.human_ask_lock:
                        if core.human_ask_active:
                            continue
                    if getattr(core, "status_busy", False):
                        time.sleep(0.1)
                        continue

                prompt = getattr(core, "get_prompt", lambda: "User> ")()

                # Read input
                if is_reply:
                    line = _prompt_toolkit_input("[REPLY] > ", reply=True)
                    if line is None:
                        line = sys.stdin.readline()
                        if line == "":
                            raise EOFError
                else:
                    line = None

                    # Use prompt_toolkit when available (handles prompt drawing internally)
                    use_simple_prompt = str(
                        env_get("UAGENT_SIMPLE_PROMPT", "0") or ""
                    ).lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    )
                    prompt_session = _get_prompt_session()
                    # bitchat chat_mode="llm" 中は prompt_toolkit を無効化する。
                    # プロンプト表示中に注入メッセージの LLM ラウンドが始まると、
                    # patch_stdout がストリーム毎にプロンプトを再描画して
                    # Reasoning/アシスタント表示が乱れる。手動パスなら行の
                    # 追跡・再描画を制御できる。
                    _chat_mode_active = is_chat_mode() == "llm"
                    if (
                        prompt_session is not None
                        and sys.stdin.isatty()
                        and not use_simple_prompt
                        and not _chat_mode_active
                    ):
                        try:
                            from prompt_toolkit.patch_stdout import patch_stdout

                            # prompt_toolkit redraws the prompt itself. Mark it
                            # as open while waiting so the status worker does not
                            # emit a redundant IDLE line between prompt redraws.
                            try:
                                core._prompt_line_open = True
                            except Exception:
                                pass
                            try:
                                with patch_stdout():
                                    line = prompt_session.prompt(prompt)
                            finally:
                                try:
                                    core._prompt_line_open = False
                                except Exception:
                                    pass
                            if line is not None:
                                line = tools_util.strip_surrogates(line)
                        except Exception:
                            line = None
                    else:
                        # Manual prompt drawing fallback
                        lock = getattr(core, "print_lock", None)
                        if lock is None:
                            lock = threading.RLock()
                        # Advertise the prompt before taking print_lock.  If
                        # this is set only inside the lock, the status thread
                        # can decide to print IDLE just before the prompt is
                        # written, producing `agentcli> [STATE] IDLE`.
                        try:
                            core._prompt_line_open = True
                        except Exception:
                            pass
                        with lock:
                            try:
                                if out:
                                    out.write(prompt)
                                    out.flush()
                                else:
                                    print(prompt, end="", flush=True)
                            except Exception:
                                try:
                                    print(prompt, end="", flush=True)
                                except Exception:
                                    pass

                        # A normal prompt can become stale if an LLM/tool round
                        # or human_ask starts after it was drawn but before the
                        # input wait begins. Do not keep waiting on that prompt;
                        # let the next loop render the active prompt instead.
                        with core.human_ask_lock:
                            prompt_interrupted = core.human_ask_active
                        if prompt_interrupted or getattr(core, "status_busy", False):
                            # The prompt was drawn, but this input slot is no
                            # longer usable because another tool owns stdin.
                            # Clear the stale prompt before continuing; otherwise
                            # it remains visible immediately before the next
                            # [STATE] IDLE line even though no input is accepted.
                            try:
                                with lock:
                                    clear = (
                                        chr(13)
                                        + (" " * len(prompt.rstrip("\r\n")))
                                        + chr(13)
                                    )
                                    if out:
                                        out.write(clear)
                                        out.flush()
                                    else:
                                        print(clear, end="", flush=True)
                            except Exception:
                                pass
                            try:
                                core._prompt_line_open = False
                                core.prompt_needs_redraw = False
                            except Exception:
                                pass
                            continue

                        if os.name == "nt":
                            try:
                                import msvcrt  # type: ignore

                                while True:
                                    with core.human_ask_lock:
                                        if core.human_ask_active:
                                            break
                                    # 注入メッセージのラウンド等でプロンプト行が
                                    # 閉じられた場合、アイドルになったら再描画する。
                                    if getattr(
                                        core, "prompt_needs_redraw", False
                                    ) and not getattr(core, "status_busy", False):
                                        with core.print_lock:
                                            if getattr(
                                                core, "prompt_needs_redraw", False
                                            ) and not getattr(
                                                core, "status_busy", False
                                            ):
                                                try:
                                                    core._prompt_line_open = True
                                                except Exception:
                                                    pass
                                                core.prompt_needs_redraw = False
                                                try:
                                                    if out:
                                                        out.write(prompt)
                                                        out.flush()
                                                    else:
                                                        print(
                                                            prompt, end="", flush=True
                                                        )
                                                except Exception:
                                                    pass
                                    if msvcrt.kbhit():
                                        line = sys.stdin.readline()
                                        if line == "":
                                            raise EOFError
                                        try:
                                            core._prompt_line_open = False
                                        except Exception:
                                            pass
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
                                    if getattr(
                                        core, "prompt_needs_redraw", False
                                    ) and not getattr(core, "status_busy", False):
                                        with core.print_lock:
                                            if getattr(
                                                core, "prompt_needs_redraw", False
                                            ) and not getattr(
                                                core, "status_busy", False
                                            ):
                                                core.prompt_needs_redraw = False
                                                try:
                                                    if out:
                                                        out.write(prompt)
                                                        out.flush()
                                                    else:
                                                        print(
                                                            prompt, end="", flush=True
                                                        )
                                                except Exception:
                                                    pass
                                                try:
                                                    core._prompt_line_open = True
                                                except Exception:
                                                    pass
                                    r, _w, _x = select.select([sys.stdin], [], [], 0.05)
                                    if r:
                                        line = sys.stdin.readline()
                                        if line == "":
                                            raise EOFError
                                        try:
                                            core._prompt_line_open = False
                                        except Exception:
                                            pass
                                        break
                            except EOFError:
                                raise
                            except Exception:
                                line = sys.stdin.readline()
                                if line == "":
                                    raise EOFError

                if line is None:
                    _skip = True
        except EOFError:
            # EOF (e.g. piped stdin end): request clean exit so short logs are discarded
            try:
                core.event_queue.put({"kind": "command", "text": ":exit"})
            except Exception:
                pass
            break
        except KeyboardInterrupt:
            # Reset Ctrl+C during input wait, taking into account the currently active state (such as human_ask)
            with core.human_ask_lock:
                if core.human_ask_active:
                    print(
                        "\n[INFO] "
                        + "Input cancelled (will be sent as a reply to human_ask)."
                    )
                    # Send an empty string or cancel to resume the tool side
                    if core.human_ask_queue:
                        core.human_ask_queue.put("cancel")
                    continue

            # Changed to immediately enter the shutdown sequence on Ctrl+C
            print("\n[INFO] " + _("Received Ctrl+C. Starting shutdown..."))
            core.event_queue.put({"kind": "command", "text": ":exit"})
            break
        except Exception as e:
            # Broad catch to prevent sudden thread death
            try:
                from .hooks_engine import fire_stop_failure

                fire_stop_failure()
            except Exception:
                pass
            print(
                "\n[ERROR] " + "Unexpected error in stdin_loop: %(err)s" % {"err": e},
                file=sys.stderr,
            )
            time.sleep(1)
            continue

        if _skip:
            continue

        line = line.rstrip("\n")

        # Response processing for human_ask
        handled_human_ask = False
        with core.human_ask_lock:
            if core.human_ask_active and core.human_ask_queue is not None:
                handled_human_ask = True
                is_ha_multiline = core.human_ask_multiline_active
                is_ha_password = core.human_ask_is_password

        if handled_human_ask:
            should_wait_completion = False
            if not is_ha_multiline:
                # Do not treat 'f' as a command to switch to multiline mode when entering a password
                if line == "f" and not is_ha_password and _can_use_textarea():
                    text = _multiline_editor()
                    if text is None:
                        core.set_status(True, "replying_cancel")
                        with core.human_ask_lock:
                            if core.human_ask_queue:
                                core.human_ask_queue.put("cancel")
                        print("[REPLY] " + _("Cancelled."))
                        should_wait_completion = True
                    else:
                        core.set_status(True, "replying_multi")
                        with core.human_ask_lock:
                            if core.human_ask_queue:
                                core.human_ask_queue.put(text)
                        print("[REPLY] " + _("Received multiline reply."))
                        should_wait_completion = True

                else:
                    core.set_status(True, "replying")
                    with core.human_ask_lock:
                        if core.human_ask_queue:
                            core.human_ask_queue.put(line)
                    _last_ha_reply_mono = time.monotonic()

                    # If we enter the next input() before human_ask_tool sets human_ask_active back to False in finally,
                    # an extra [REPLY] > might be displayed.
                    # Wait for a short time for completion before returning to the prompt.
                    for _i in range(50):  # up to ~0.5s
                        with core.human_ask_lock:
                            if not core.human_ask_active:
                                break
                        time.sleep(0.03)
                    # NOTE: Do not print acknowledgement here. It can interleave with subsequent human_ask prompts
                    # and confuse the user when multiple human_ask calls happen back-to-back.
                    should_wait_completion = True
            else:
                # Treat a single line of c / cancel as an interruption even in multiline mode
                if line.strip().lower() in ("c", "cancel"):
                    core.set_status(True, "replying_cancel")
                    with core.human_ask_lock:
                        core.human_ask_lines.clear()
                        core.human_ask_multiline_active = False
                        if core.human_ask_queue:
                            core.human_ask_queue.put(line)
                    print("[REPLY] " + _("Cancelled."))
                    should_wait_completion = True
                else:
                    with core.human_ask_lock:
                        core.human_ask_lines.append(line)

            # Return to the main loop without waiting for completion (to suppress next input while status_busy is True).
            # Removed because waiting here could cause a deadlock when multiple human_asks are consecutive.
            if should_wait_completion:
                pass
            continue

        if not user_multiline_active:
            if line.startswith(":"):
                if not line.startswith(":load"):
                    _append_prompt_history_entry(line)
                core.set_status(True, "command_pending")
                core.event_queue.put({"kind": "command", "text": line})
                continue

            if line == "f" and _can_use_textarea():
                text = _multiline_editor()
                if text is None:
                    continue
                if not text.strip():
                    continue
                _append_prompt_history_entry(text)
                forward_to_mesh(text)
                if is_chat_mode() == "on":
                    # "on" mode: forward to mesh only, not to LLM
                    core.set_status(False, "")
                    continue
                core.set_status(True, "user_pending_multi")
                core.event_queue.put({"kind": "user", "text": text})
                continue

            if not line.strip():
                if os.name != "nt":
                    print()
                continue

            _append_prompt_history_entry(line)
            forward_to_mesh(line)
            if is_chat_mode() == "on":
                # "on" mode: forward to mesh only, not to LLM
                core.set_status(False, "")
                continue
            core.set_status(True, "user_pending")
            core.event_queue.put({"kind": "user", "text": line})
        else:
            user_lines.append(line)


def main() -> None:
    from .runtime.logging_setup import bind_event_context

    bind_event_context(session_id="cli", correlation_id="cli")
    log_event("cli.start")
    sys.stdout.reconfigure(encoding="utf-8")
    if UAGENT_REALTIME:
        from .realtime import run as run_realtime

        raise SystemExit(run_realtime())

    from . import uagent_llm as llm_util  # lazy

    startup = _run_cli_startup(
        core=core,
        cli_workdir=_cli_workdir,
        env_workdir=_env_workdir,
        initial_file_arg=INITIAL_FILE_ARG,
        non_interactive=UAGENT_NON_INTERACTIVE,
        tool_genre_mask=UAGENT_TOOL_GENRE_MASK,
        inject_message=UAGENT_INJECT_MESSAGE,
        enable_tools=UAGENT_ENABLE_TOOLS,
    )

    provider = startup.provider
    client = startup.client
    depname = startup.depname
    messages = startup.messages
    _bootstrap_prompt_history(messages)

    if startup.should_exit:
        return

    # Do not automatically resume a saved Responses chain at startup.
    # Explicit :load selects a log and may restore its validated latest ID.
    if provider in ("openai", "azure"):
        core.responses_state["provider"] = provider
        core.responses_state["model"] = depname
        core.responses_state.pop("previous_response_id", None)
        core.responses_state.pop("active_response_id", None)

    start_background_scheduler(core.event_queue)
    # Allow pybitchat chat_mode="llm" to inject peer messages into the LLM.
    set_llm_event_queue(core.event_queue)
    core.start_interrupt_monitor()

    # Preload tool plugins in background so the first ':' command/completion
    # does not pay the full plugin-import cost on the interactive path.
    if not UAGENT_NON_INTERACTIVE:
        try:
            tools.start_tools_warmup()
        except Exception:
            pass

    # Fire SessionStart and Setup hooks (inject stdout context into messages)
    try:
        from .hooks_engine import (
            fire_session_start,
            fire_event,
            load_hooks_registry,
            get_default_registry_path,
            inject_hook_context,
            take_pending_session_hook_texts,
        )

        _ss_results = fire_session_start()
        inject_hook_context(
            messages, _ss_results, event_name="SessionStart", replace_event=False
        )
        # Avoid double-inject if a later path pulls the SessionStart stash.
        take_pending_session_hook_texts()
        _hooks = load_hooks_registry(get_default_registry_path())
        if _hooks:
            _setup_results = fire_event("Setup", _hooks)
            inject_hook_context(
                messages, _setup_results, event_name="Setup", replace_event=False
            )
    except Exception:
        pass

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
                    _append_prompt_history_entry(prompt)
                    core.log_message(user_msg)
                    with lifecycle_execution() as lifecycle:
                        try:
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
                        except Exception as exc:
                            lifecycle.fail()
                            print(f"LLM round interrupted: {exc}")

                    # Auto-pilot loop: if auto mode is active, continue rounds
                    if core.auto_pilot_active:
                        try:
                            with lifecycle_execution():
                                tools_util._run_auto_pilot_loop(
                                    provider,
                                    client,
                                    depname,
                                    messages,
                                    core=core,
                                    make_client_fn=providers.make_client,
                                    append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                                    try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                                )
                        except Exception as exc:
                            print(f"[AUTO] Auto-pilot interrupted: {exc}")
                        core.set_status(False, "")
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

                # Fire UserPromptSubmit hook (stdin JSON + context / block)
                try:
                    from .hooks_engine import (
                        fire_user_prompt_submit,
                        inject_hook_context,
                        collect_hook_block_decision,
                    )

                    _ups_results = fire_user_prompt_submit(text)
                    _ups_block = collect_hook_block_decision(_ups_results)
                    if _ups_block is not None:
                        _reason = (_ups_block.get("reason") or "").strip()
                        if not _reason:
                            _reason = "Blocked by UserPromptSubmit hook."
                        print(_reason)
                        core.set_status(False, "")
                        continue
                    inject_hook_context(
                        messages,
                        _ups_results,
                        event_name="UserPromptSubmit",
                        replace_event=True,
                    )
                except Exception:
                    pass

                # If the active provider can accept images on the main chat path and the
                # user message contains local image paths, ask for permission before
                # embedding images as data URLs / attachments.
                use_responses_api = env_get("UAGENT_RESPONSES", "").lower() in (
                    "1",
                    "true",
                )
                prov = (env_get("UAGENT_PROVIDER") or "").lower()
                allow_multimodal = provider_allows_chat_vision(
                    prov,
                    use_responses_api=use_responses_api,
                    model_id=depname,
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
                            except (Exception, SystemExit) as e:
                                ans = "n"
                                print(
                                    "[WARN] "
                                    + _(
                                        "Image send confirmation failed; will not send images: %(etype)s: %(err)s"
                                    )
                                    % {"etype": type(e).__name__, "err": e}
                                )

                            if ans in ("y", "yes"):
                                user_msg = build_multimodal_user_message(
                                    text,
                                    ok_paths,
                                    provider=prov,
                                    use_responses_api=use_responses_api,
                                )
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

                with lifecycle_execution() as lifecycle:
                    try:
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
                    except Exception as exc:
                        lifecycle.fail()
                        print(f"[bitchat] LLM round interrupted: {exc}")

                # bitchat 経由のメッセージ: LLM 応答を mesh に自動返信
                if ev.get("src") == "bitchat":
                    reply = tools_util.extract_last_assistant_text(messages)
                    if reply:
                        reply_to_mesh(reply)
                    # 注入ラウンド中に手動プロンプトの行が閉じられているため、
                    # アイドルに戻ったら stdin_loop に再描画を要求する。
                    try:
                        core.prompt_needs_redraw = True
                    except Exception:
                        pass
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
        try:
            core.stop_interrupt_monitor()
        except Exception:
            pass
        # Fire Stop and SessionEnd hooks
        try:
            from .hooks_engine import (
                fire_stop,
                fire_event,
                load_hooks_registry,
                get_default_registry_path,
            )

            fire_stop()
            _hooks = load_hooks_registry(get_default_registry_path())
            if _hooks:
                fire_event("SessionEnd", _hooks)
        except Exception:
            pass
        # Clear cache on program exit
        if provider in ("gemini", "vertexai") and client:
            try:
                from .providers.gemini_cache_mgr import GeminiCacheManager

                mgr = GeminiCacheManager(depname)
                mgr.clear_cache(client)
            except Exception:
                pass

        core.set_status(False, "")
        print(_("Exited uag."))


if __name__ == "__main__":
    main()
