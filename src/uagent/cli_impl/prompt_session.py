"""Prompt-session management for the uagent CLI (split from cli.py)."""

from __future__ import annotations

import os
import sys
from typing import Any


def _ensure_prompt_toolkit() -> bool:
    """Load prompt_toolkit, installing the allow-listed package on demand."""
    try:
        from prompt_toolkit import PromptSession  # noqa: F401

        return True
    except ImportError:
        # Do not install merely because a non-interactive invocation imported
        # the CLI module.  The package is only needed for a TTY prompt.
        if not getattr(sys.stdin, "isatty", lambda: False)():
            return False
        try:
            from .._pip_auto import auto_install

            return auto_install("prompt-toolkit", "prompt_toolkit")
        except Exception:
            return False


from . import state
from .. import tools
from .. import util_tools as tools_util
from ..uagent_env_keys import get_known_uagent_env_keys
from ..utils.paths import get_history_file_path


def _create_prompt_output() -> Any:
    """Prefer prompt_toolkit's VT output on Windows.

    Win32Output can render BMP text but may turn supplementary-plane emoji
    such as U+1F5FB (🗻) into question marks.  The VT backend writes UTF-8
    through the terminal, matching ordinary ``print()`` output.
    """
    if sys.platform != "win32":
        return None
    try:
        from .. import core as _core

        _core._enable_windows_vt_mode()
        # Do not let create_output() silently select Win32Output again when
        # VT detection is conservative.  Windows10_Output uses the same UTF-8
        # VT path as ordinary print() and supports supplementary-plane emoji.
        from prompt_toolkit.output.windows10 import Windows10_Output

        return Windows10_Output(sys.stdout)
    except Exception:
        return None


def _get_prompt_session(*, reply: bool = False) -> Any:
    if not _ensure_prompt_toolkit():
        if reply:
            state._PROMPT_REPLY_SESSION = False
        else:
            state._PROMPT_SESSION = False
        return None

    if reply:
        if state._PROMPT_REPLY_SESSION is False:
            return None
        if state._PROMPT_REPLY_SESSION is None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.history import InMemoryHistory
            except Exception:
                state._PROMPT_REPLY_SESSION = False
                return None

            try:
                output = _create_prompt_output()
                session_kwargs = {"history": InMemoryHistory()}
                if output is not None:
                    session_kwargs["output"] = output
                session = PromptSession(**session_kwargs)
                for entry in state._PROMPT_HISTORY:
                    try:
                        session.history.append_string(entry)
                    except Exception:
                        pass
                state._PROMPT_REPLY_SESSION = session
            except Exception:
                state._PROMPT_REPLY_SESSION = False
                return None
        return state._PROMPT_REPLY_SESSION

    if state._PROMPT_SESSION is False:
        return None
    if state._PROMPT_SESSION is None:
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
            state._PROMPT_SESSION = False
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
                    elif stripped.startswith(":logs "):
                        # :logs subcommands and numeric/export arguments.
                        after_logs = stripped[len(":logs ") :]
                        parts = after_logs.split()
                        last = parts[-1] if parts else ""
                        if len(parts) <= 1:
                            log_opts = ["all", "--all", "-a", "pdf"] + [
                                str(n) for n in (5, 10, 20, 50, 100)
                            ]
                            for value in log_opts:
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                        elif parts[0].lower() == "pdf" and len(parts) == 2:
                            for value in ("0", "1", "2", "3", "4", "5", "10"):
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                    elif stripped.startswith(":auto "):
                        # :auto accepts a free-form goal plus stop/round options.
                        after_auto = stripped[len(":auto ") :]
                        parts = after_auto.split()
                        last = parts[-1] if parts else ""
                        if not parts or after_auto.endswith(" "):
                            candidates = [
                                "off",
                                "INFINITE",
                                "--infinite",
                                "--max-rounds",
                            ]
                            for value in candidates:
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                        elif last.startswith("--"):
                            for value in ("--infinite", "--max-rounds"):
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                        elif len(parts) >= 2 and parts[-2] == "--max-rounds":
                            for value in (
                                "1",
                                "5",
                                "10",
                                "20",
                                "30",
                                "50",
                                "100",
                                "INFINITE",
                            ):
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                    elif stripped.startswith(":plugin "):
                        # :plugin subcommands, plugin options, and marketplace actions.
                        after_plugin = stripped[len(":plugin ") :]
                        parts = after_plugin.split()
                        last = parts[-1] if parts else ""
                        if len(parts) <= 1:
                            values = [
                                "list",
                                "install",
                                "remove",
                                "uninstall",
                                "enable",
                                "disable",
                                "reload",
                                "info",
                                "init",
                                "validate",
                                "marketplace",
                            ]
                            for value in values:
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                        else:
                            sub = parts[0].lower()
                            if sub == "marketplace" and len(parts) <= 2:
                                values = ["add", "remove", "list", "update"]
                                for value in values:
                                    if value.startswith(last):
                                        yield Completion(
                                            value, start_position=-len(last)
                                        )
                            elif sub == "install" and (
                                last.startswith("--") or after_plugin.endswith(" ")
                            ):
                                values = [
                                    "--scope",
                                    "--name",
                                    "user",
                                    "project",
                                    "local",
                                ]
                                for value in values:
                                    if value.startswith(last):
                                        yield Completion(
                                            value, start_position=-len(last)
                                        )
                            elif sub == "list" and (
                                last.startswith("--") or after_plugin.endswith(" ")
                            ):
                                for value in ("--enabled", "--verbose"):
                                    if value.startswith(last):
                                        yield Completion(
                                            value, start_position=-len(last)
                                        )
                    elif stripped.startswith(":mem-del "):
                        # Memory indexes are numeric; offer common index values.
                        after_mem = stripped[len(":mem-del ") :]
                        last = after_mem.split()[-1] if after_mem.split() else ""
                        for value in ("0", "1", "2", "3", "4", "5", "10"):
                            if value.startswith(last):
                                yield Completion(value, start_position=-len(last))
                    elif stripped.startswith(":shared-mem-del "):
                        after_shared_mem = stripped[len(":shared-mem-del ") :]
                        last = (
                            after_shared_mem.split()[-1]
                            if after_shared_mem.split()
                            else ""
                        )
                        for value in ("0", "1", "2", "3", "4", "5", "10"):
                            if value.startswith(last):
                                yield Completion(value, start_position=-len(last))
                    elif stripped.startswith(":profile-fromlog "):
                        after_profile = stripped[len(":profile-fromlog ") :]
                        last = (
                            after_profile.split()[-1] if after_profile.split() else ""
                        )
                        for value in ("0", "10", "50", "100", "500"):
                            if value.startswith(last):
                                yield Completion(value, start_position=-len(last))
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
                    elif stripped.startswith(":sessions "):
                        after_sessions = stripped[len(":sessions ") :]
                        parts = after_sessions.split()
                        last = parts[-1] if parts else ""
                        if len(parts) <= 1:
                            for value in (
                                "list",
                                "load",
                                "search",
                                "summarize",
                                "prune",
                                "candidates",
                                "approve",
                                "delete",
                                "vacuum",
                                "pdf",
                                "import",
                            ):
                                if value.startswith(last):
                                    yield Completion(value, start_position=-len(last))
                        elif parts[0] == "delete":
                            if after_sessions.endswith(" "):
                                yield Completion("--yes", start_position=0)
                            elif last.startswith("--") and "--yes".startswith(last):
                                yield Completion("--yes", start_position=-len(last))
                    elif stripped.startswith(":skills "):
                        # :skills subcommand and option completion. Keep the
                        # built-ins here as well as CMD_SPEC entries: the
                        # latter are loaded lazily, so completion should not
                        # depend on a previous invocation of :skills.
                        after_skills = stripped[len(":skills ") :]
                        if " " not in after_skills:
                            skills_subcmds = sorted(
                                set(dyn_map.get("skills", []))
                                | {
                                    "list",
                                    "find",
                                    "search",
                                    "grep",
                                    "active",
                                    "status",
                                    "show",
                                    "clear",
                                    "off",
                                    "unset",
                                    "reset",
                                    "install",
                                    "uninstall",
                                    "review",
                                    "enable",
                                    "apm",
                                    "mp_search",
                                }
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
                            if cmd2 == "apm":
                                if " " not in arg2:
                                    # ``path`` is accepted as an alias for
                                    # ``dir`` by the handler.
                                    apm_subcmds = ["list", "use", "dir", "path", "help"]
                                    for sc2 in apm_subcmds:
                                        if sc2.startswith(arg2):
                                            yield Completion(
                                                sc2, start_position=-len(arg2)
                                            )
                                else:
                                    apm_cmd, apm_arg = arg2.split(" ", 1)
                                    if apm_cmd.lower() == "use" and not apm_arg.strip():
                                        # The handler accepts a name or a
                                        # 1-based list number. Avoid scanning
                                        # the filesystem on every tab press.
                                        for value in ("1", "2", "3", "4", "5"):
                                            yield Completion(value, start_position=0)
                            elif cmd2 == "enable":
                                # The lifecycle command requires --yes.
                                enable_last = arg2.split()[-1] if arg2.split() else ""
                                if arg2.endswith(" "):
                                    yield Completion("--yes", start_position=0)
                                elif enable_last.startswith(
                                    "--"
                                ) and "--yes".startswith(enable_last):
                                    yield Completion(
                                        "--yes", start_position=-len(enable_last)
                                    )
                            elif cmd2 == "mp_search":
                                mp_parts = arg2.split()
                                last = mp_parts[-1] if mp_parts else ""
                                previous = (
                                    mp_parts[-1]
                                    if arg2.endswith(" ") and mp_parts
                                    else ""
                                )
                                if arg2.endswith(" "):
                                    last = ""
                                if last.startswith("--") or arg2.endswith(" "):
                                    for flag in (
                                        "--page",
                                        "--limit",
                                        "--sort",
                                        "--source",
                                    ):
                                        if flag not in mp_parts and flag.startswith(
                                            last
                                        ):
                                            yield Completion(
                                                flag, start_position=-len(last)
                                            )
                                value_for = (
                                    previous
                                    if arg2.endswith(" ")
                                    else (mp_parts[-2] if len(mp_parts) >= 2 else "")
                                )
                                if value_for == "--sort":
                                    for value in ("recent", "stars", "name"):
                                        if value.startswith(last):
                                            yield Completion(
                                                value, start_position=-len(last)
                                            )
                                elif value_for == "--source":
                                    for value in ("skillsmp", "clawhub"):
                                        if value.startswith(last):
                                            yield Completion(
                                                value, start_position=-len(last)
                                            )
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
                    elif stripped.startswith(":profile fromlog "):
                        after_profile = stripped[len(":profile fromlog ") :]
                        last = (
                            after_profile.split()[-1] if after_profile.split() else ""
                        )
                        for value in ("0", "10", "50", "100", "500"):
                            if value.startswith(last):
                                yield Completion(value, start_position=-len(last))
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
                            "sessions",
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

            output = _create_prompt_output()
            session = PromptSession(
                output=output,
                history=_SafeFileHistory(str(get_history_file_path())),
                completer=_CommandCompleter(),
            )
            for entry in state._PROMPT_HISTORY:
                try:
                    session.history.append_string(entry)
                except Exception:
                    pass
            state._PROMPT_SESSION = session
        except Exception:
            state._PROMPT_SESSION = False
            return None
    return state._PROMPT_SESSION


def _reset_prompt_sessions() -> None:
    """Drop prompt_toolkit sessions after an interrupted/failed prompt.

    PromptSession caches its Application/input context.  If a watcher calls
    ``Application.exit`` while a tool owns stdin, that cached context can be
    left associated with a closed Windows asyncio executor.  Reusing it makes
    every later prompt fail with ``Application is not running`` or
    ``Executor shutdown has been called``.  A new PromptSession is cheap and
    is safer than reusing a poisoned one.
    """
    state._PROMPT_SESSION = None
    state._PROMPT_REPLY_SESSION = None
