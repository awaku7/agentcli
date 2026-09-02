"""stdin input loop for the uagent CLI (split from cli.py)."""

from __future__ import annotations

import getpass
import os
import sys
import threading
import time

from ..i18n import _
from ..env_utils import env_get
from .. import core
from .. import util_tools as tools_util
from ..tools.pybitchat_shared import forward_to_mesh, is_chat_mode
from .history import _append_prompt_history_entry
from .input_ui import (
    _can_use_textarea,
    _clear_abandoned_prompt,
    _flush_stdin_input_buffer,
    _getpass_fallback,
    _make_prompt_key_bindings,
    _multiline_editor,
    _prompt_toolkit_input,
)
from .prompt_session import _get_prompt_session
from .state import _CLI_SHUTDOWN


def stdin_loop() -> None:
    """
    Read standard input and push events to core.event_queue.
    """
    user_multiline_active = False
    user_lines: list[str] = []
    _last_ha_reply_mono = 0.0

    while True:
        if _CLI_SHUTDOWN.is_set():
            return
        # Never carry the ownership marker across an abandoned prompt slot.
        core.input_prompt_active = False
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
                core.input_prompt_active = True
                if is_reply:
                    line = _prompt_toolkit_input("[REPLY] > ", reply=True)
                    if line is None:
                        # readline() does not render a prompt by itself.
                        try:
                            reply_out = (
                                sys.stderr
                                if getattr(sys.stderr, "isatty", lambda: False)()
                                else sys.stdout
                            )
                            reply_out.write("[REPLY] > ")
                            reply_out.flush()
                        except Exception:
                            print("[REPLY] > ", end="", flush=True)
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

                            # The normal prompt must relinquish stdin when a
                            # tool or human_ask starts.  Without this watcher,
                            # the prompt remains visible and is redrawn on
                            # every status update even though it cannot accept
                            # input.
                            stop_prompt_watch = threading.Event()

                            def _watch_normal_prompt() -> None:
                                while not stop_prompt_watch.wait(0.05):
                                    if _CLI_SHUTDOWN.is_set():
                                        app = getattr(prompt_session, "app", None)
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
                                    app = getattr(prompt_session, "app", None)
                                    if app is not None:
                                        app.exit(result=None)
                                    return

                            prompt_watcher = threading.Thread(
                                target=_watch_normal_prompt,
                                name="prompt-toolkit-normal-state-watcher",
                                daemon=True,
                            )
                            prompt_watcher.start()

                            # Treat the prompt_toolkit-rendered line like the
                            # manual prompt so status output can close it
                            # before writing [STATE].
                            try:
                                core._prompt_line_open = True
                            except Exception:
                                pass
                            try:
                                with patch_stdout():
                                    line = prompt_session.prompt(
                                        prompt, key_bindings=_make_prompt_key_bindings()
                                    )
                            finally:
                                stop_prompt_watch.set()
                                prompt_watcher.join(timeout=0.2)
                                try:
                                    core._prompt_line_open = False
                                except Exception:
                                    pass
                            if line is not None:
                                line = tools_util.strip_surrogates(line)
                        except Exception:
                            line = None
                        if line is None:
                            # ``None`` is also the sentinel used when the
                            # watcher aborts a normal prompt because a tool
                            # or human_ask has taken stdin.  Do not fall back
                            # to blocking readline() while input is unavailable.
                            with core.human_ask_lock:
                                prompt_interrupted = core.human_ask_active
                            if prompt_interrupted or getattr(
                                core, "status_busy", False
                            ):
                                _clear_abandoned_prompt(prompt)
                                core.input_prompt_active = False
                                _skip = True
                                continue
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
                                core.input_prompt_active = False
                            except Exception:
                                pass
                            continue

                        if os.name == "nt":
                            try:
                                import msvcrt  # type: ignore

                                while True:
                                    if _CLI_SHUTDOWN.is_set():
                                        return
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
                                    if _CLI_SHUTDOWN.is_set():
                                        return
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
                from ..hooks_engine import fire_stop_failure

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

        core.input_prompt_active = False
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

                elif line == "f" and not is_ha_password:
                    # Keep `f` usable when prompt_toolkit is not installed.
                    with core.human_ask_lock:
                        core.human_ask_lines.clear()
                        core.human_ask_multiline_active = True
                    print("[REPLY] " + _("Multiline mode: enter lines; submit with an empty line."))

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
                    if not line.strip():
                        with core.human_ask_lock:
                            text = chr(10).join(core.human_ask_lines).strip()
                            core.human_ask_lines.clear()
                            core.human_ask_multiline_active = False
                            if core.human_ask_queue:
                                core.human_ask_queue.put(text)
                        core.set_status(True, "replying_multi")
                        print("[REPLY] " + _("Received multiline reply."))
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

            if line == "f":
                # Fallback for environments without prompt_toolkit.
                user_multiline_active = True
                user_lines.clear()
                print("[MULTILINE] " + _("Enter lines; submit with an empty line, or type c to cancel."))
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
            if line.strip().lower() in ("c", "cancel"):
                user_lines.clear()
                user_multiline_active = False
                print("[MULTILINE] " + _("Cancelled."))
                continue
            if not line.strip():
                text = chr(10).join(user_lines).strip()
                user_lines.clear()
                user_multiline_active = False
                if not text:
                    continue
                _append_prompt_history_entry(text)
                forward_to_mesh(text)
                if is_chat_mode() == "on":
                    core.set_status(False, "")
                    continue
                core.set_status(True, "user_pending_multi")
                core.event_queue.put({"kind": "user", "text": text})
                continue
            user_lines.append(line)
