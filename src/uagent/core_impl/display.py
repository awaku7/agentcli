"""Console display / status line helpers (split from core.py)."""

from __future__ import annotations

import sys
import time

from ..env_utils import env_get
from .. import core as _core
from ..runtime import display_channel as _display_channel
from ..runtime.spinner import stop_quietly as _stop_spinner_quietly


def _abandoned() -> bool:
    """Whether the calling thread is an LLM call abandoned by a Stop.

    Its stream output must not appear after the turn has returned.
    """
    try:
        from ..llm_helpers import llm_call_abandoned

        return llm_call_abandoned()
    except Exception:
        return False


def _active_console_view():
    """The full-screen console view rendering the terminal, if any."""
    try:
        from ..cli_impl.console_view import active_view

        return active_view()
    except Exception:
        return None


def usage_display_enabled() -> bool:
    """Whether provider-reported usage should be shown (default: enabled)."""
    setting = str(env_get("UAGENT_SHOW_USAGE", "") or "").strip().lower()
    return setting not in {"0", "false", "no", "off"}


def set_usage_status(usage: dict[str, int] | None) -> bool:
    """Overlay provider-reported token usage on the active CLI status line.

    Usage display is enabled by default and can be disabled with
    ``UAGENT_SHOW_USAGE=0``.  The legacy ``[USAGE]`` diagnostic remains the
    fallback when explicitly enabled but no full-screen view is active.
    """
    view = _active_console_view()
    if not usage_display_enabled():
        if view is not None:
            view.set_usage(None)
        return False
    if view is None:
        return False
    view.set_usage(usage)
    return True


def _sync_spinner_to_status(busy: bool) -> None:
    """Start/stop the spinner. No-op when disabled (UAGENT_SPINNER=0).

    While the console view is active, spinner.start/stop drive the
    view's spinner line instead of the stderr thread.
    """
    try:
        from ..runtime import spinner as _spinner

        if busy:
            _spinner.start()
        else:
            _spinner.stop()
    except Exception:
        pass


def print_stream_delta(s: str) -> None:
    """Print a streaming text delta without letting status lines split mid-line.

    Uses print_lock and tracks whether the current stdout line is still open
    (no trailing newline yet). print_status_line() closes an open line before
    emitting [STATE], so status never appears mid-text.
    """
    if not s or _abandoned():
        return
    # Stage 2a relay: on the CLI round worker thread the delta is
    # posted to the display channel and rendered by the pump thread
    # (which calls back into this function with no relay bound).
    relay = _display_channel.stream_relay()
    if relay is not None:
        relay.post_stream(_display_channel.StreamDelta(text=s, kind="answer"))
        return
    # First token arrived: stop the spinner (ollama-style).
    # No-op when the spinner is disabled.
    _stop_spinner_quietly()
    with _core.print_lock:
        print_stream_delta_locked(s)


def print_stream_delta_locked(s: str) -> None:
    """Write a stream delta while the caller holds ``print_lock``.

    The caller must already have stopped the spinner. Unlike
    print_stream_delta(), this never touches the spinner, so it is safe
    under print_lock: calling print_stream_delta() there inverts the
    spinner lifecycle-lock / print_lock order against a concurrent
    spinner stop and can deadlock.
    """
    if _core._reasoning_stream_open:
        if s != chr(10):
            print("", flush=True)
        _core._reasoning_stream_open = False
    print(s, end="", flush=True)
    # Open iff the final character is not a newline (handles embedded \n).
    _core._stream_line_open = not s.endswith(chr(10))


def print_reasoning_delta(s: str) -> None:
    """Print reasoning output while marking the current line as reasoning."""
    if not s or _abandoned():
        return
    relay = _display_channel.stream_relay()
    if relay is not None:
        relay.post_stream(_display_channel.StreamDelta(text=s, kind="reasoning"))
        return
    _stop_spinner_quietly()
    # This printer is the legacy terminal renderer for reasoning, so
    # the gray is applied here — the producer's text carries none,
    # and the console view grays reasoning by segment kind instead.
    # Gray the whole delta and reset in the same write, so later
    # assistant output cannot inherit reasoning's terminal color.
    # The line-open flag is computed from the original text: the
    # wrapped text ends with the reset sequence, not the newline.
    line_open = not s.endswith(chr(10))
    try:
        from ..reasoning_display import _reasoning_ansi_enabled

        if _reasoning_ansi_enabled(_core):
            s = "\x1b[90m" + s + "\x1b[0m"
    except Exception:
        pass
    with _core.print_lock:
        print(s, end="", flush=True)
        _core._stream_line_open = line_open
        _core._reasoning_stream_open = line_open


def _write_status_line(
    text: str, *, busy: bool, use_color: bool, label: str = ""
) -> None:
    """Compatibility shim for runtime.console."""
    from ..runtime.console import write_status_line

    write_status_line(text, busy=busy, use_color=use_color, label=label)


def _is_idle_shell() -> bool:
    """Return True when stdout/stderr are handled by Python IDLE."""
    for stream in (sys.stdout, sys.stderr):
        module = type(stream).__module__.lower()
        name = type(stream).__name__.lower()
        if "idlelib" in module or "idle" in name:
            return True
    return "idlelib" in sys.modules


def print_status_line() -> None:
    """
    Draw the current busy / label status in a single line.

    Policy:
    - Default: colored [STATE] on TTY (yellow BUSY / green IDLE).
    - Windows: color via SetConsoleTextAttribute + WriteConsoleW (no ANSI ESC),
      so hosts that drop VT mid-session cannot leak "?[32m[STATE] IDLE?[0m".
    - Non-Windows: ANSI SGR colors.
    - Disable colors with NO_COLOR, UAGENT_NO_COLOR, UAGENT_STATUS_COLOR=0,
      GUI mode, or non-TTY stderr.
    - Do not use carriage-return + ANSI erase as it may break the prompt on some Windows consoles.
    - Never inject [STATE] mid-text: if a streaming line is still open, first
      finish it with a newline (prefer waiting briefly for a natural newline).
    - In Web mode, status is delivered via WebSocket type=status; skip stderr.
    """

    view = _active_console_view()

    # Suppress status display while human_ask is active to avoid
    # disrupting the prompt display.  A console view is the one
    # exception: while an ask owns the terminal the view is
    # suspended and set_status only stores the text, so routing
    # the update keeps the bottom line truthful when the view
    # resumes.  Dropping it instead loses the transition for
    # good — the state has already changed, so no later call
    # prints it again, and the view keeps showing the stale
    # BUSY line (e.g. [STATE] BUSY [tool:human_ask]) at an idle
    # prompt.
    with _core.human_ask_lock:
        ask_active = _core.human_ask_active
    if ask_active and view is None:
        _stop_spinner_quietly()
        return

    # Web UI already receives status via web_set_status -> room.set_status.
    # Avoid also writing [STATE] to stderr (which becomes type=log and can
    # interleave with assistant stream text).
    if bool(getattr(_core, "_is_web", False)):
        _stop_spinner_quietly()
        return

    # Full-screen console view: the status lives on the fixed bottom
    # line; none of the line-boundary machinery below applies.
    if view is not None:
        with _core.status_lock:
            busy = _core.status_busy
            label = _core.status_label
        _sync_spinner_to_status(bool(busy))
        label_part = f" [{label}]" if label else ""
        view.set_status(
            f"[STATE] {'BUSY' if busy else 'IDLE'}{label_part}",
            busy=bool(busy),
        )
        return

    # Do not tear down or repaint a live CLI prompt merely to show BUSY/IDLE.
    # Apart from stealing the input line, rewriting the terminal invalidates
    # mouse selections (and therefore clipboard copying) in common terminals.
    # A real human_ask is handled above and still takes ownership of stdin.
    if bool(getattr(_core, "_prompt_line_open", False)):
        _stop_spinner_quietly()
        return

    with _core.status_lock:
        busy = _core.status_busy
        label = _core.status_label

    # Braille spinner (ollama-like, default ON). status.py also calls this via
    # set_status(); this covers direct print_status_line() callers too.
    _sync_spinner_to_status(bool(busy))

    state = "BUSY" if busy else "IDLE"
    label_part = f" [{label}]" if label else ""

    # Color/ANSI control
    # Default: enable ANSI colors unless explicitly disabled.
    no_color = bool(env_get("NO_COLOR") or env_get("UAGENT_NO_COLOR"))
    stderr_is_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())

    # A prompt_toolkit prompt owns its line. Erasing it by hand below
    # while its application is still running leaves the application free
    # to redraw the prompt over the spinner and this status line when
    # the prompt watcher exits it a moment later (the merged
    # spinner-frame + "agentcli>" line seen with injected rounds). Ask
    # the application to exit first and wait briefly for the input loop
    # to release the line; the manual erase below remains as the
    # fallback if it does not yield.
    if _core._prompt_line_open and bool(
        getattr(_core, "_cli_prompt_toolkit_active", False)
    ):
        app = getattr(_core, "_cli_prompt_app", None)
        if app is not None:
            try:
                if getattr(app, "is_running", False):
                    app.exit(result=None)
            except Exception:
                pass
        yield_deadline = time.time() + 0.3
        while _core._prompt_line_open and time.time() < yield_deadline:
            time.sleep(0.005)

    # Prefer a natural newline boundary so status does not split a sentence.
    # If the stream stays open past the deadline, force-close the line with a
    # newline first — never write [STATE] into the middle of assistant text.
    deadline = time.time() + 0.25
    nl = chr(10)
    while True:
        _start_spinner_after_lock = False
        with _core.print_lock:
            line_open = _core._stream_line_open
            prompt_open = _core._prompt_line_open
            timed_out = time.time() >= deadline
            if line_open and not timed_out:
                pass
            else:
                if line_open:
                    # Close the open streaming line before emitting status.
                    try:
                        sys.stdout.write(nl)
                        sys.stdout.flush()
                    except Exception:
                        try:
                            print("", flush=True)
                        except Exception:
                            pass
                    _core._stream_line_open = False
                    _core._reasoning_stream_open = False
                if prompt_open:
                    # Close and erase an abandoned prompt before writing
                    # [STATE].  A newline alone leaves a misleading
                    # input-looking `agentcli>` line on screen.
                    try:
                        # Avoid CSI 2K: unsupported Windows console wrappers
                        # print it literally as `?[2K`.
                        sys.stdout.write(chr(13) + (" " * 120) + chr(13) + nl)
                        sys.stdout.flush()
                    except Exception:
                        try:
                            print("", flush=True)
                        except Exception:
                            pass
                    _core._prompt_line_open = False
                # Color policy for [STATE] lines:
                # - Default ON when TTY + (Windows: VT actually enabled).
                # - Color-capable terminals get green IDLE / yellow BUSY.
                # - Opt-out: NO_COLOR, UAGENT_NO_COLOR, UAGENT_STATUS_COLOR=0.
                # - If VT enable fails on Windows, stay plain to avoid
                #   "?[32m[STATE] IDLE?[0m" leaks on broken consoles.
                status_color_env = (
                    (env_get("UAGENT_STATUS_COLOR") or "").strip().lower()
                )
                color_disabled = status_color_env in ("0", "false", "no", "off")
                want_color = (
                    (not _core.IS_GUI)
                    and (not no_color)
                    and (not color_disabled)
                    and stderr_is_tty
                )
                # On Windows, do not gate on VT: we color via console attributes.
                # On other OS, ANSI needs a TTY (already required above).
                # The post-turn IDLE write is the path that can be mangled by
                # prompt/terminal wrappers; keep IDLE plain while retaining
                # color for BUSY status updates.
                # Spinner takes over the BUSY indicator (ollama-like, default ON):
                # skip the legacy [STATE] BUSY line so the two do not fight
                # over the same stderr line (that race leaves a stale line
                # that looks like the spinner "won't disappear").
                # Stream/prompt closing above is still done, so the spinner
                # gets a clean line. IDLE follows the legacy path unchanged.
                if busy:
                    try:
                        from ..runtime.spinner import (
                            spinner_enabled as _spinner_enabled,
                        )

                        if _spinner_enabled():
                            # Defer spinner.start() until print_lock is
                            # released: start() takes _lifecycle_lock only,
                            # while stop() (reached from the [TOOL] trace
                            # path) takes _lifecycle_lock -> print_lock.
                            # Calling start() while holding print_lock
                            # inverts that order and deadlocks both threads.
                            _start_spinner_after_lock = True
                    except Exception:
                        pass
                if not _start_spinner_after_lock:
                    use_color = want_color
                    _write_status_line(
                        f"[STATE] {state}{label_part}",
                        busy=busy,
                        use_color=use_color,
                        label=label,
                    )
                    return
        if _start_spinner_after_lock:
            _sync_spinner_to_status(True)
            return
        time.sleep(0.005)
