"""stdin input loop for the uagent CLI (split from cli.py)."""

from __future__ import annotations

import getpass
import os
import sys
import threading
import time

from ..i18n import _
from .. import core
from .. import util_tools as tools_util
from ..tools.pybitchat_shared import forward_to_mesh, is_chat_mode
from .history import _append_prompt_history_entry
from .input_ui import (
    _can_use_textarea,
    _clear_abandoned_prompt,
    _exit_prompt_application,
    _flush_stdin_input_buffer,
    _getpass_fallback,
    _make_prompt_key_bindings,
    _multiline_editor,
    _normalize_multiline_text,
    _prompt_toolkit_input,
)
from .prompt_session import _get_prompt_session, _reset_prompt_sessions
from .state import _CLI_SHUTDOWN

_console_view = None
_console_view_failed = False


def _request_turn_interrupt() -> None:
    """Ask the running turn to stop (the core interrupt flags).

    Shared by the view's Ctrl+C, its F12 handler's semantics, and the
    interrupt confirmation for a message submitted during
    generation: one place sets the flags, mirroring the round
    worker's KeyboardInterrupt path.
    """
    try:
        with core.interrupt_lock:
            core.interrupt_requested = True
    except Exception:
        pass
    try:
        with core.auto_pilot_exit_lock:
            core.auto_pilot_exit_requested = True
    except Exception:
        pass


def _console_view_ctrl_c() -> None:
    """Ctrl+C inside the console view (it arrives as a key, not SIGINT)."""
    with core.human_ask_lock:
        ask_active = bool(core.human_ask_active)
        ask_queue = core.human_ask_queue if ask_active else None
    if ask_active:
        # Mirror the legacy Ctrl+C-during-ask behaviour.
        if ask_queue is not None:
            try:
                ask_queue.put("cancel")
            except Exception:
                pass
        return
    if getattr(core, "status_busy", False):
        # Interrupt the running turn, mirroring the F12 monitor and the
        # round worker's KeyboardInterrupt path.
        _request_turn_interrupt()
        return
    # Idle: the legacy prompt path starts the shutdown sequence.
    if _console_view is not None:
        from ..runtime import display_channel

        display_channel.post_segment(
            "notice",
            "\n[INFO] " + _("Received Ctrl+C. Starting shutdown...") + "\n",
        )
    core.event_queue.put({"kind": "command", "text": ":exit"})


def _console_view_f12() -> None:
    """F12 inside the console view: the legacy interrupt key.

    Mirrors the F12 monitor's busy-only semantics: cancel a
    pending ask and request the interrupt. Idle F12 does nothing.
    While the view owns the terminal, the legacy monitor does not
    read stdin (see core_impl.interrupt), so this binding is the
    only F12 path.
    """
    with core.human_ask_lock:
        ask_active = bool(core.human_ask_active)
        ask_queue = core.human_ask_queue if ask_active else None
    if not ask_active and not getattr(core, "status_busy", False):
        return
    if ask_queue is not None:
        try:
            ask_queue.put("cancel")
        except Exception:
            pass
    _request_turn_interrupt()


def _get_console_view():
    """The session's full-screen console view, or None when unavailable."""
    global _console_view, _console_view_failed
    if _console_view_failed:
        return None
    if _console_view is None:
        try:
            from .console_view import ConsoleView, view_enabled

            if not view_enabled():
                _console_view_failed = True
                return None
            session = _get_prompt_session()
            _console_view = ConsoleView(
                completer=getattr(session, "completer", None),
                history=getattr(session, "history", None),
                on_ctrl_c=_console_view_ctrl_c,
                on_f12=_console_view_f12,
                on_interrupt=_request_turn_interrupt,
            )
            # Startup printed its welcome/banner before the view
            # existed; seed the document with that output so it
            # stays visible inside the view.
            try:
                from .console_view import seed_document_from_startup_output

                seed_document_from_startup_output()
            except Exception:
                pass
        except Exception:
            _console_view_failed = True
            return None
    return _console_view


def _read_line_from_view(view, prompt: str):
    """Read one normal-prompt line through the console view.

    Returns ``(line, pending_token)``: the submitted line and the
    output document's pending-user segment when the line was queued
    during generation (else None).  Returns ``(None, None)`` when
    the wait was aborted because a human_ask took stdin or shutdown
    began.  On a human_ask abort the view stays up — the loop's
    reply branch answers the ask inside it — while a shutdown
    abort still suspends it for the legacy exit paths.  Raises
    EOFError on Ctrl+D, like the legacy prompt paths.
    """
    if not view.running:
        view.start()
    view.set_prompt_text(prompt)
    # Status updates only reach the view while it is active; a
    # turn that ended while the view was suspended for a human_ask
    # leaves its cached busy flag stale.  Re-align it with the
    # core before the flag gates any submission.
    resync_busy = getattr(view, "resync_busy", None)
    if resync_busy is not None:
        try:
            resync_busy(bool(getattr(core, "status_busy", False)))
        except Exception:
            pass
    try:
        core._prompt_line_open = True
        core._cli_prompt_toolkit_active = True
    except Exception:
        pass

    def _abort() -> bool:
        if _CLI_SHUTDOWN.is_set():
            return True
        with core.human_ask_lock:
            return bool(core.human_ask_active)

    try:
        item = view.wait_line(abort=_abort)
    finally:
        try:
            core._prompt_line_open = False
            core._cli_prompt_toolkit_active = False
        except Exception:
            pass
    if item is None:
        with core.human_ask_lock:
            ask_active = bool(core.human_ask_active)
        if not ask_active:
            view.suspend()
        return None, None
    if item is view.eof_sentinel:
        view.suspend()
        raise EOFError
    return tools_util.strip_surrogates(str(item)), getattr(
        view, "last_pending_token", None
    )


def _read_reply_from_view(view, prompt: str, *, is_password: bool, reply_job_id):
    """Read one human_ask reply line through the console view.

    The view stays on screen: its input row switches to reply
    mode (masked for a password) and the question remains visible
    in the output document above it.  Returns the reply line, or
    None when the wait was aborted — the ask was answered or
    cancelled from another channel, or shutdown began — so the
    caller's existing None handling decides what happens next.
    Raises EOFError on Ctrl+D and KeyboardInterrupt on Ctrl+C,
    exactly like the legacy reply prompt paths, so the loop's
    handlers deliver the same outcomes.
    """
    view.begin_reply(prompt, is_password=is_password)
    try:
        core._prompt_line_open = True
        core._cli_prompt_toolkit_active = True
    except Exception:
        pass

    def _abort() -> bool:
        if _CLI_SHUTDOWN.is_set():
            return True
        with core.human_ask_lock:
            if reply_job_id:
                return bool(
                    not core.human_ask_active
                    or getattr(core, "human_ask_job_id", None) != reply_job_id
                )
            return not core.human_ask_active

    try:
        item = view.wait_reply(abort=_abort)
    finally:
        try:
            core._prompt_line_open = False
            core._cli_prompt_toolkit_active = False
        except Exception:
            pass
    if item is None:
        view.end_reply()
        return None
    if item is view.eof_sentinel:
        raise EOFError
    if item is view.reply_cancelled:
        raise KeyboardInterrupt
    return tools_util.strip_surrogates(str(item))


def _requeue_pending_line(view, line, token) -> bool:
    """Return a queued-during-generation line to the view queue.

    A line carrying a pending token was a deliberate queue
    decision, so when stdin ownership changes underneath it (a
    human_ask takes over) it must survive and dispatch at the
    next ordinary prompt, instead of taking the legacy
    ambiguous-input drop that lines typed at a replaced prompt
    get.  Returns True when the line was requeued.
    """
    if view is None or token is None:
        return False
    try:
        view.requeue_front(line, token)
    except Exception:
        return False
    return True


def _preserve_line_across_ask(view, line, token) -> bool:
    """Whether a line the loop read survives a human_ask takeover.

    Queued lines go back with their pending token
    (:func:`_requeue_pending_line`).  An interrupt-chosen line
    carries no token — it was echoed as an ordinary user segment
    at once — but it is an explicit "send this next" choice, so
    it goes back to the view's priority queue instead of taking
    the legacy drop.  Returns True when the line was preserved.
    """
    if _requeue_pending_line(view, line, token):
        return True
    if view is None or token is not None:
        return False
    if not getattr(view, "last_line_priority", False):
        return False
    requeue = getattr(view, "requeue_priority", None)
    if requeue is None:
        return False
    try:
        requeue(line)
    except Exception:
        return False
    return True


def _resolve_pending_echo(token) -> None:
    """Drop the queued marker from a view line that is being sent.

    Lines submitted during generation are echoed into the output
    document with a pending marker; the marker comes off at the
    moment the line is actually dispatched (or definitively
    dropped), so the transcript never claims a sent line is still
    waiting, or a dropped one was sent.
    """
    if token is None:
        return
    view = _console_view
    if view is not None:
        try:
            view.resolve_pending(token)
        except Exception:
            pass


def _suspend_console_view() -> bool:
    """Yield the terminal to a legacy prompt or editor, if the view runs.

    The next normal read restarts the view, so callers only suspend.
    Returns True when a running view was actually suspended.
    """
    view = _console_view
    if view is not None and view.running:
        try:
            view.suspend()
        except Exception:
            return False
        return True
    return False


def _replay_pending_question() -> None:
    """Re-show the pending human_ask question on the restored terminal.

    The question was printed while the console view owned the screen,
    so it only exists inside the view's document; once the view is
    suspended for a legacy reply prompt, the user would otherwise see
    nothing but ``[REPLY] > ``.  The message is the one the ask
    registered on the core (foreground asks and sub-agent job asks
    alike).
    """
    try:
        with core.human_ask_lock:
            message = str(getattr(core, "human_ask_message", "") or "")
    except Exception:
        return
    if message.strip():
        print(message, flush=True)


def _stop_console_view() -> None:
    """Stop the console view for good (the stdin loop is exiting)."""
    view = _console_view
    if view is not None:
        try:
            view.stop()
        except Exception:
            pass


from ..runtime.spinner import (
    paused as _spinner_paused,
    stop_quietly as _stop_spinner_quietly,
)


def stdin_loop(*, hook_runner=None) -> None:
    """
    Read standard input and push events to core.event_queue.
    """
    try:
        _stdin_loop_impl(hook_runner=hook_runner)
    finally:
        # The view is a separate daemon thread owning the terminal;
        # every exit path (shutdown, EOF, error) must stop it so the
        # terminal's raw mode and alternate screen are restored.
        _stop_console_view()


def _stdin_loop_impl(*, hook_runner=None) -> None:
    user_multiline_active = False
    user_lines: list[str] = []
    _last_ha_reply_mono = 0.0

    while True:
        if _CLI_SHUTDOWN.is_set():
            return
        # Never carry the ownership marker across an abandoned prompt slot.
        core.input_prompt_active = False
        _skip = False
        _pending_token = None
        _line_view = None
        try:
            # First, check if we are waiting for a reply
            with core.human_ask_lock:
                is_reply = core.human_ask_active
                is_password = is_reply and core.human_ask_is_password
                reply_job_id = getattr(core, "human_ask_job_id", None)
                password_prompt = (
                    getattr(core, "human_ask_prompt", "") or "[PASSWORD] > "
                )
                reply_prompt = getattr(core, "human_ask_prompt", "") or "[REPLY] > "

            # Prompt is resolved *only when we are ready to actually read input*.
            # If we compute it while BUSY and then loop/sleep, it can become stale
            # (e.g. show a normal prompt while a human_ask is actually active).

            # A console view that is already running answers the
            # ask in place: no suspension, no screen switch.  Only
            # an already-running view qualifies — one that was
            # never started let the question print to the real
            # terminal, and the legacy reply path owns it there.
            reply_view = None
            if is_reply and _console_view is not None and _console_view.running:
                reply_view = _console_view

            if is_reply and reply_view is None:
                # A legacy reply/password prompt is about to own the
                # terminal — including asks opened during generation,
                # where no view read is outstanding to abort. The
                # next normal read restarts the view. The question was
                # printed into the view's document, so replay it onto
                # the restored terminal for the user to answer.
                if _suspend_console_view():
                    _replay_pending_question()

            if is_password:
                # When replying to a prompt (human_ask password), flush any pending
                # typeahead to prevent unintended immediate submission.
                # The view path needs no flush: the view stashes the
                # pre-ask draft itself, and draining the descriptor
                # would eat keystrokes the view has not read yet.
                if is_reply and reply_view is None:
                    _flush_stdin_input_buffer()

                if reply_view is not None:
                    line = _read_reply_from_view(
                        reply_view,
                        password_prompt,
                        is_password=True,
                        reply_job_id=reply_job_id,
                    )
                else:
                    line = _prompt_toolkit_input(
                        password_prompt, is_password=True, reply=True
                    )
                if line is None:
                    with core.human_ask_lock:
                        reply_cancelled = bool(
                            reply_job_id
                            and (
                                not core.human_ask_active
                                or getattr(core, "human_ask_job_id", None)
                                != reply_job_id
                            )
                        )
                        # The view wait ended because the ask was
                        # answered from another channel; the legacy
                        # fallbacks below would fight the running
                        # view for the terminal, so just re-loop.
                        answered_elsewhere = bool(
                            reply_view is not None and not core.human_ask_active
                        )
                    if reply_cancelled or answered_elsewhere:
                        continue
                    if reply_job_id:
                        line = "cancel"
                    elif os.name == "nt":
                        line = _getpass_fallback(password_prompt)
                    elif sys.stdin.isatty() and sys.stdout.isatty():
                        line = getpass.getpass(password_prompt)
                    else:
                        line = _getpass_fallback(password_prompt)
            else:
                # When replying to a prompt (human_ask), flush any pending typeahead
                # to prevent unintended immediate submission. Skip the flush right
                # after a previous reply (e.g. :skills number selection then 'y'
                # confirmation) so fast consecutive replies are not discarded.
                # The view path skips it for the same reason as the
                # password branch: the view owns the descriptor.
                if (
                    is_reply
                    and reply_view is None
                    and (is_password or time.monotonic() - _last_ha_reply_mono >= 2.0)
                ):
                    _flush_stdin_input_buffer()

                # Since prompts containing color codes may be displayed twice in Windows (pyreadline) etc.,
                # use a simple prompt without coloring.
                # NOTE: Since prompt drawing by input(prompt) may be missing depending on the environment,
                # always unify to "draw manually -> input()".
                # Since the status color display is output to stderr by the core side, colors are not lost by this change.
                # Do not open a fresh interactive prompt while an LLM/tool
                # response is streaming. Status output may close an active
                # prompt; reopening it during BUSY makes redraws race.
                if not is_reply:
                    while getattr(core, "status_busy", False):
                        if _CLI_SHUTDOWN.is_set():
                            return
                        with core.human_ask_lock:
                            if core.human_ask_active:
                                break
                        time.sleep(0.05)
                    with core.human_ask_lock:
                        if core.human_ask_active:
                            continue

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
                prompt = getattr(core, "get_prompt", lambda: "User> ")()

                # Read input
                core.input_prompt_active = True
                if is_reply:
                    if reply_view is not None:
                        line = _read_reply_from_view(
                            reply_view,
                            reply_prompt,
                            is_password=False,
                            reply_job_id=reply_job_id,
                        )
                    else:
                        line = _prompt_toolkit_input(reply_prompt, reply=True)
                    if line is None:
                        with core.human_ask_lock:
                            reply_cancelled = bool(
                                reply_job_id
                                and (
                                    not core.human_ask_active
                                    or getattr(core, "human_ask_job_id", None)
                                    != reply_job_id
                                )
                            )
                            # The ask was answered from another channel
                            # (Nostr remote / bitchat bridge) while this
                            # prompt was blocked, and the prompt watcher
                            # withdrew it. Nothing typed here belongs to
                            # an ask anymore: re-loop and render the
                            # current prompt instead of reading a reply
                            # nobody is waiting for.
                            ask_answered_elsewhere = bool(
                                not reply_job_id and not core.human_ask_active
                            )
                        if reply_cancelled or ask_answered_elsewhere:
                            continue
                        if reply_view is not None:
                            # The view wait ends without a line only
                            # for the causes handled above, or for
                            # shutdown; the readline fallback below
                            # would fight the running view for the
                            # terminal, so just re-loop (the loop
                            # head returns on shutdown).
                            continue
                        if reply_job_id:
                            line = "cancel"
                        else:
                            # readline() does not render a prompt by itself.
                            try:
                                reply_out = (
                                    sys.stderr
                                    if getattr(sys.stderr, "isatty", lambda: False)()
                                    else sys.stdout
                                )
                                reply_out.write(reply_prompt)
                                reply_out.flush()
                            except Exception:
                                print(reply_prompt, end="", flush=True)
                            line = sys.stdin.readline()
                            if line == "":
                                raise EOFError
                else:
                    line = None

                    # Use prompt_toolkit when available (it draws the
                    # prompt itself). The session read restores history,
                    # completion and bracketed paste for the idle prompt.
                    # patch_stdout is deliberately not used: the prompt
                    # opens only while idle (see the wait above) and must
                    # not stay alive across streamed output.
                    prompt_session = _get_prompt_session()
                    # bitchat chat_mode="llm" 中は prompt_toolkit を無効化する。
                    # プロンプト表示中に注入メッセージの LLM ラウンドが始まると、
                    # patch_stdout がストリーム毎にプロンプトを再描画して
                    # Reasoning/アシスタント表示が乱れる。手動パスなら行の
                    # 追跡・再描画を制御できる。
                    _chat_mode_active = is_chat_mode() == "llm"
                    # Full-screen console view (single-writer 2b): while
                    # it is enabled it replaces the per-prompt
                    # PromptSession read; submitted lines flow into the
                    # same post-processing below either way.
                    _view = None
                    if (
                        not _chat_mode_active
                        and getattr(sys.stdin, "isatty", lambda: False)()
                        and getattr(sys.stdout, "isatty", lambda: False)()
                    ):
                        _view = _get_console_view()
                    if _chat_mode_active:
                        # Chat mode reads manually; a view left
                        # running from an earlier read must yield
                        # the terminal first.
                        _suspend_console_view()
                    if _view is not None:
                        _line_view = _view
                        line, _pending_token = _read_line_from_view(_view, prompt)
                    elif (
                        prompt_session is not None
                        and getattr(sys.stdin, "isatty", lambda: False)()
                        and not _chat_mode_active
                    ):
                        # Ordinary BUSY/status changes do not interrupt an
                        # idle prompt. A human_ask is different because it
                        # explicitly takes ownership of stdin.
                        stop_prompt_watch = threading.Event()

                        def _watch_normal_prompt() -> None:
                            while not stop_prompt_watch.wait(0.05):
                                if _CLI_SHUTDOWN.is_set():
                                    app = getattr(prompt_session, "app", None)
                                    _exit_prompt_application(app)
                                    return
                                with core.human_ask_lock:
                                    interrupted = bool(core.human_ask_active)
                                if not interrupted:
                                    continue
                                app = getattr(prompt_session, "app", None)
                                _exit_prompt_application(app)
                                return

                        prompt_watcher = threading.Thread(
                            target=_watch_normal_prompt,
                            name="prompt-toolkit-normal-state-watcher",
                            daemon=True,
                        )
                        prompt_watcher.start()

                        # Treat the prompt_toolkit-rendered line like the
                        # manual prompt so status output can close it
                        # before writing [STATE]. The application handle is
                        # published so status output can ask the prompt to
                        # yield instead of erasing its line.
                        try:
                            core._prompt_line_open = True
                            core._cli_prompt_toolkit_active = True
                            core._cli_prompt_app = getattr(prompt_session, "app", None)
                        except Exception:
                            pass
                        try:
                            line = prompt_session.prompt(
                                prompt, key_bindings=_make_prompt_key_bindings()
                            )
                        except EOFError:
                            raise
                        except Exception:
                            # Do not reuse a PromptSession whose
                            # Application/input context failed.
                            _reset_prompt_sessions()
                            line = None
                        finally:
                            stop_prompt_watch.set()
                            prompt_watcher.join(timeout=0.2)
                            try:
                                core._prompt_line_open = False
                                core._cli_prompt_toolkit_active = False
                                core._cli_prompt_app = None
                            except Exception:
                                pass
                        if line is not None:
                            line = tools_util.strip_surrogates(line)
                        if line is None:
                            # ``None`` is also the sentinel used when the
                            # watcher aborts a normal prompt because a tool
                            # or human_ask has taken stdin.  Do not fall
                            # back to blocking readline() while input is
                            # unavailable.
                            with core.human_ask_lock:
                                prompt_interrupted = core.human_ask_active
                            if prompt_interrupted or getattr(
                                core, "status_busy", False
                            ):
                                _clear_abandoned_prompt(prompt)
                                core.input_prompt_active = False
                    else:
                        # Manual prompt drawing. The prompt opens only
                        # while idle, so it never shares the terminal with
                        # streamed output.
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
            # Release a pending human_ask first: its waiter (e.g. the
            # pairing prompt) blocks the dispatcher, so without this
            # the exit event could not be processed until the ask
            # timeout expired.
            try:
                with core.human_ask_lock:
                    if core.human_ask_active and core.human_ask_queue is not None:
                        core.human_ask_queue.put_nowait(None)
            except Exception:
                pass
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
                        + _("Input cancelled (will be sent as a reply to human_ask).")
                    )
                    # Send an empty string or cancel to resume the tool side
                    if core.human_ask_queue:
                        if getattr(core, "human_ask_job_id", None):
                            core.human_ask_queue.put("cancel")
                        elif core.human_ask_is_password and core.human_ask_prompt:
                            core.human_ask_queue.put(None)
                        else:
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

                if hook_runner is None:
                    fire_stop_failure()
                else:
                    hook_runner(fire_stop_failure)
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
        busy_at_submit = bool(not is_reply and getattr(core, "status_busy", False))

        # Never route text entered at a normal prompt into a newly opened
        # human_ask/password prompt, or vice versa. An interrupted prompt may
        # race with Enter; dropping that ambiguous line is safer than exposing
        # a reply as an ordinary user message.
        with core.human_ask_lock:
            human_ask_active_now = bool(core.human_ask_active)
        if (not is_reply and human_ask_active_now) or (
            is_reply and not human_ask_active_now
        ):
            if _preserve_line_across_ask(_line_view, line, _pending_token):
                continue
            _resolve_pending_echo(_pending_token)
            with _spinner_paused():
                print(
                    _(
                        "Input was not sent because the active prompt changed "
                        "while you were typing. Please enter it again at the "
                        "current prompt."
                    )
                )
            continue

        # Response processing for human_ask
        handled_human_ask = False
        with core.human_ask_lock:
            if is_reply and core.human_ask_active and core.human_ask_queue is not None:
                handled_human_ask = True
                is_ha_multiline = core.human_ask_multiline_active
                is_ha_password = core.human_ask_is_password
                is_job_confirmation = bool(getattr(core, "human_ask_job_id", None))

        if handled_human_ask:

            def _set_reply_status(label: str) -> None:
                if not is_job_confirmation:
                    core.set_status(True, label)

            # Normalize CRLF/CR in the fallback line-by-line path as well as
            # in the prompt_toolkit editor. This keeps human_ask replies
            # consistent when a terminal paste supplies carriage returns.
            line = _normalize_multiline_text(line)
            should_wait_completion = False
            if not is_ha_multiline:
                # Do not treat 'f' as a command to switch to multiline mode when entering a password
                if (
                    line == "f"
                    and not is_ha_password
                    and not is_job_confirmation
                    and _can_use_textarea()
                ):
                    # The editor opens its own application; a view
                    # that served the reply in place must yield the
                    # terminal first (a no-op when the legacy reply
                    # path already suspended it).
                    _suspend_console_view()
                    text = _multiline_editor()
                    if text is None:
                        _set_reply_status("replying_cancel")
                        with core.human_ask_lock:
                            if core.human_ask_queue:
                                core.human_ask_queue.put("cancel")
                        print("[REPLY] " + _("Cancelled."))
                        should_wait_completion = True
                    else:
                        _set_reply_status("replying_multi")
                        with core.human_ask_lock:
                            if core.human_ask_queue:
                                core.human_ask_queue.put(text)
                        print("[REPLY] " + _("Received multiline reply."))
                        should_wait_completion = True

                elif line == "f" and not is_ha_password and not is_job_confirmation:
                    # Keep `f` usable when prompt_toolkit is not installed.
                    with core.human_ask_lock:
                        core.human_ask_lines.clear()
                        core.human_ask_multiline_active = True
                    print(
                        "[REPLY] "
                        + _("Multiline mode: enter lines; submit with an empty line.")
                    )

                else:
                    _set_reply_status("replying")
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
                    _set_reply_status("replying_cancel")
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
                        _set_reply_status("replying_multi")
                        print("[REPLY] " + _("Received multiline reply."))
                    else:
                        with core.human_ask_lock:
                            core.human_ask_lines.append(line)

            # Return to the main loop without waiting for completion (to suppress next input while status_busy is True).
            # Removed because waiting here could cause a deadlock when multiple human_asks are consecutive.
            if should_wait_completion:
                pass
            continue

        # A line submitted at a prompt that was open when a turn started is
        # held until the current turn finishes, unless stdin ownership
        # changes. Never reinterpret it as a human_ask/confirmation reply if
        # that prompt became active during the race between Enter and this
        # check.
        if busy_at_submit:
            # The manual prompt cannot safely coexist with streamed output,
            # so the submitted line waits for the turn to finish.
            while getattr(core, "status_busy", False):
                if _CLI_SHUTDOWN.is_set():
                    return
                with core.human_ask_lock:
                    if core.human_ask_active:
                        break
                time.sleep(0.05)
            with core.human_ask_lock:
                human_ask_active_now = bool(core.human_ask_active)
            if human_ask_active_now:
                if _preserve_line_across_ask(_line_view, line, _pending_token):
                    continue
                _resolve_pending_echo(_pending_token)
                with _spinner_paused():
                    print(
                        _(
                            "Input was not sent because the active prompt changed "
                            "while you were typing. Please enter it again at the "
                            "current prompt."
                        )
                    )
                continue
            busy_at_submit = False

        # A line the user chose to interrupt for may have been
        # submitted while this line was being held (or while it was
        # read across the turn boundary): it was explicitly chosen
        # to go next, so it overtakes the held line, which returns
        # to the front of the view queue with its marker intact.
        if _line_view is not None:
            try:
                _priority_line = _line_view.take_priority_line()
            except Exception:
                _priority_line = None
            if _priority_line is not None:
                _line_view.requeue_front(line, _pending_token)
                line = _priority_line
                _pending_token = None

        # The line is committed to dispatch now: a line that was
        # queued during generation loses its pending marker here, so
        # every dispatch branch below (command, editor, message)
        # presents it as sent.
        _resolve_pending_echo(_pending_token)

        if not user_multiline_active:
            if line.startswith(":"):
                if not line.startswith(":load"):
                    _append_prompt_history_entry(line)
                core.set_status(True, "command_pending")
                command_name = line.split(maxsplit=1)[0]
                if command_name in {":load", ":cont", ":nostr"}:
                    # Session restore and :nostr print several status/detail
                    # lines. Stop the stderr spinner before dispatch so its
                    # CR redraws do not interleave with those stdout messages
                    # or leave a stale frame behind after the command
                    # completes.
                    _stop_spinner_quietly()
                core.event_queue.put({"kind": "command", "text": line})
                continue

            if line == "f" and _can_use_textarea():
                # The editor opens its own application; the view
                # must not compete with it for the terminal.
                suspended_view = _console_view
                view_was_suspended = _suspend_console_view()
                try:
                    text = _multiline_editor()
                finally:
                    # The normal prompt loop may wait for the submitted
                    # response to finish before reading another line. Resume
                    # the view now so its input/display mode is restored
                    # immediately after Ctrl+X or Esc, including while the
                    # response is running.
                    if view_was_suspended and suspended_view is not None:
                        try:
                            suspended_view.start()
                        except Exception:
                            pass
                if text is None:
                    continue
                if not text.strip():
                    continue
                with core.human_ask_lock:
                    prompt_changed = bool(core.human_ask_active)
                if prompt_changed or getattr(core, "status_busy", False):
                    with _spinner_paused():
                        print(
                            _(
                                "Multiline input cannot be submitted while a response "
                                "or another prompt is active. Please try again when idle."
                            )
                        )
                    continue
                _append_prompt_history_entry(text)
                if _console_view is not None:
                    # The editor ran on the restored terminal while
                    # the view was suspended; without this the resumed
                    # transcript shows only the "f" line, not the
                    # message itself.
                    from ..runtime import display_channel

                    prompt = getattr(core, "get_prompt", lambda: "User> ")()
                    display_channel.post_segment("user", f"{prompt}{text}\n")
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
                print(
                    "[MULTILINE] "
                    + _("Enter lines; submit with an empty line, or type c to cancel.")
                )
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
