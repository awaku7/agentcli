"""Interactive input UI helpers (split from cli.py)."""

from __future__ import annotations

import getpass
import os
import sys
import threading
from typing import Any

from ..i18n import _
from .. import core
from .. import util_tools as tools_util
from .prompt_session import (
    _create_prompt_output,
    _get_prompt_session,
    _reset_prompt_sessions,
)
from .state import _CLI_SHUTDOWN


def _normalize_pasted_text(value: str) -> str:
    """Normalize CRLF/CR delivered by terminals into prompt newlines."""
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _make_prompt_key_bindings() -> Any:
    """Return prompt_toolkit bindings shared by normal and reply prompts."""
    try:
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.keys import Keys
    except Exception:
        return None
    kb = KeyBindings()

    @kb.add("f11", eager=True)
    def _stop_auto_pilot(event: Any) -> None:
        if not core.auto_pilot_active:
            return
        with core.auto_pilot_exit_lock:
            core.auto_pilot_exit_requested = True
        event.app.exit(result=None)

    @kb.add("escape", eager=True)
    def _cancel(event: Any) -> None:
        # Ask prompt_toolkit to propagate the cancellation through its
        # Application future instead of raising from the key handler.  A
        # direct raise is reported by prompt_toolkit as "Unhandled exception
        # in event loop" before stdin_loop gets a chance to handle it.
        # ESC cancels only the current prompt; KeyboardInterrupt is Ctrl-C.
        event.app.exit(result=None)

    @kb.add("up", eager=True)
    def _history_or_cursor_up(event: Any) -> None:
        buffer = event.current_buffer
        # When the completion menu is open, Up/Down belong to completion
        # navigation.  This binding is eager, so delegate explicitly instead
        # of accidentally replacing the completion selection with history.
        if buffer.complete_state is not None:
            buffer.complete_previous()
            return
        document = buffer.document
        if document.cursor_position_row == 0:
            before = buffer.text
            buffer.history_backward()
            if buffer.text != before and buffer.document.line_count > 1:
                buffer.cursor_position = 0
        else:
            buffer.cursor_up()

    @kb.add("down", eager=True)
    def _history_or_cursor_down(event: Any) -> None:
        buffer = event.current_buffer
        if buffer.complete_state is not None:
            buffer.complete_next()
            return
        document = buffer.document
        if document.cursor_position_row == document.line_count - 1:
            before = buffer.text
            buffer.history_forward()
            if buffer.text != before and buffer.document.line_count > 1:
                buffer.cursor_position = 0
        else:
            buffer.cursor_down()

    @kb.add(Keys.BracketedPaste)
    def _safe_paste(event: Any) -> None:
        data = _normalize_pasted_text(event.data)
        event.current_buffer.insert_text(tools_util.strip_surrogates(data))

    pending_high = ""

    @kb.add("<any>")
    def _safe_insert(event: Any) -> None:
        # Some Windows input paths deliver a surrogate pair in two key events.
        # Keep a high surrogate until the low surrogate arrives; replacing it
        # immediately would turn a valid emoji into a question mark.
        nonlocal pending_high
        data = pending_high + event.data
        pending_high = ""
        if data and 0xD800 <= ord(data[-1]) <= 0xDBFF:
            pending_high = data[-1]
            data = data[:-1]
        if data:
            event.current_buffer.insert_text(tools_util.strip_surrogates(data))

    return kb


def _prompt_toolkit_input(
    prompt: str, *, is_password: bool = False, reply: bool = False
) -> str | None:
    session = _get_prompt_session(reply=reply)
    if session is None:
        return None

    try:
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.keys import Keys
    except Exception:
        KeyBindings = None  # type: ignore[assignment]
        patch_stdout = None  # type: ignore

    kb = None
    if KeyBindings is not None:
        kb = KeyBindings()

        @kb.add("escape", eager=True)
        def _cancel(event: Any) -> None:
            # Raising from a prompt_toolkit key handler makes the exception
            # look like an event-loop failure.  Let Application.run()
            # propagate it via its normal exception path instead.
            # ESC cancels only the current prompt; KeyboardInterrupt is Ctrl-C.
            event.app.exit(result=None)

        @kb.add("up", eager=True)
        def _history_or_cursor_up(event: Any) -> None:
            buffer = event.current_buffer
            if buffer.complete_state is not None:
                buffer.complete_previous()
                return
            document = buffer.document
            if document.cursor_position_row == 0:
                before = buffer.text
                buffer.history_backward()
                # For recalled multiline entries, start editing at the first
                # line. Keep prompt_toolkit's normal behavior for one-line
                # history entries (cursor at the end).
                if buffer.text != before and "\n" in buffer.text:
                    buffer.cursor_position = 0
            else:
                buffer.cursor_up()

        @kb.add("down", eager=True)
        def _history_or_cursor_down(event: Any) -> None:
            buffer = event.current_buffer
            if buffer.complete_state is not None:
                buffer.complete_next()
                return
            document = buffer.document
            if document.cursor_position_row == document.line_count - 1:
                before = buffer.text
                buffer.history_forward()
                if buffer.text != before and "\n" in buffer.text:
                    buffer.cursor_position = 0
            else:
                buffer.cursor_down()

        @kb.add(Keys.BracketedPaste)
        def _safe_paste(event: Any) -> None:
            data = _normalize_pasted_text(event.data)
            event.current_buffer.insert_text(tools_util.strip_surrogates(data))

        pending_high = ""

        @kb.add("<any>")
        def _safe_insert(event: Any) -> None:
            # Windows may deliver a valid surrogate pair in two key events.
            nonlocal pending_high
            data = pending_high + event.data
            pending_high = ""
            if data and 0xD800 <= ord(data[-1]) <= 0xDBFF:
                pending_high = data[-1]
                data = data[:-1]
            if data:
                event.current_buffer.insert_text(tools_util.strip_surrogates(data))

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
                    if _CLI_SHUTDOWN.is_set():
                        app = prompt_app
                        if app is not None:
                            app.exit(result=None)
                        return
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


def _clear_abandoned_prompt(prompt: str = "") -> None:
    """Erase a prompt line that was abandoned when work became busy."""
    try:
        with core.print_lock:
            # Do not emit CSI 2K here. Some Windows console wrappers render
            # unsupported ANSI sequences literally as `?[2K`.
            width = max(80, len(prompt) + 1)
            sys.stdout.write("\r" + (" " * width) + "\r")
            sys.stdout.flush()
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


def _can_use_textarea() -> bool:
    """Check whether the multiline editor is available, installing it if needed."""
    if not sys.stdin.isatty():
        return False

    try:
        from prompt_toolkit.widgets import TextArea  # noqa: F401
        from prompt_toolkit.application import Application  # noqa: F401

        return True
    except ImportError:
        # prompt-toolkit is an allow-listed optional dependency.  Use the
        # shared installer rather than silently disabling the `f` shortcut.
        try:
            from .._pip_auto import auto_install

            if not auto_install("prompt-toolkit", "prompt_toolkit"):
                return False
            from prompt_toolkit.widgets import TextArea  # noqa: F401
            from prompt_toolkit.application import Application  # noqa: F401

            return True
        except Exception:
            return False


def _multiline_editor(initial_text: str = "") -> str | None:
    """Open a prompt_toolkit TextArea for multiline editing (non-fullscreen).

    Returns the entered text, or None if cancelled.
    """
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import TextArea as TA

    kb = KeyBindings()

    @kb.add(Keys.BracketedPaste)
    def _safe_paste(event: Any) -> None:
        event.current_buffer.insert_text(tools_util.strip_surrogates(event.data))

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
        output=_create_prompt_output(),
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
