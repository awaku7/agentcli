"""Console display / status line helpers (split from core.py)."""

from __future__ import annotations

import sys
import time

from ..env_utils import env_get
from .. import core as _core
from ..runtime.spinner import stop_quietly as _stop_spinner_quietly


def _sync_spinner_to_status(busy: bool) -> None:
    """Start/stop the spinner. No-op when disabled (UAGENT_SPINNER=0)."""
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
    if not s:
        return
    # First token arrived: stop the spinner (ollama-style).
    # No-op when the spinner is disabled.
    _stop_spinner_quietly()
    with _core.print_lock:
        if _core._reasoning_stream_open:
            if s != chr(10):
                print("", flush=True)
            _core._reasoning_stream_open = False
        print(s, end="", flush=True)
        # Open iff the final character is not a newline (handles embedded \n).
        _core._stream_line_open = not s.endswith(chr(10))


def print_reasoning_delta(s: str) -> None:
    """Print reasoning output while marking the current line as reasoning."""
    if not s:
        return
    _stop_spinner_quietly()
    with _core.print_lock:
        print(s, end="", flush=True)
        _core._stream_line_open = not s.endswith(chr(10))
        _core._reasoning_stream_open = _core._stream_line_open


def _write_status_line(text: str, *, busy: bool, use_color: bool) -> None:
    """Compatibility shim for runtime.console."""
    from ..runtime.console import write_status_line

    write_status_line(text, busy=busy, use_color=use_color)


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

    # Suppress status display while human_ask is active to avoid disrupting the prompt display
    with _core.human_ask_lock:
        if _core.human_ask_active:
            _stop_spinner_quietly()
            return

    # Web UI already receives status via web_set_status -> room.set_status.
    # Avoid also writing [STATE] to stderr (which becomes type=log and can
    # interleave with assistant stream text).
    if bool(getattr(sys.modules[__name__], "_is_web", False)):
        _stop_spinner_quietly()
        return

    with _core.status_lock:
        busy = _core.status_busy
        label = _core.status_label

    # Braille spinner (ollama-like, default ON). status.py also calls this via
    # set_status(); this covers direct print_status_line() callers too.
    _sync_spinner_to_status(bool(busy))

    # An idle prompt is already the user's visual indication that the CLI is
    # ready. Do not tear it down just to print a redundant IDLE line: the
    # prompt can be redrawn a moment later and produce `agentcli> [STATE] IDLE`
    # on terminals with prompt wrappers.
    if not busy and _core._prompt_line_open:
        _stop_spinner_quietly()
        return

    # Status has priority over a stale prompt. If a prompt is still marked
    # open, close it below and emit the state on its own line; the input loop
    # will redraw the prompt afterward. This also applies to non-TTY prompt
    # wrappers that render `agentcli> ` themselves.
    state = "BUSY" if busy else "IDLE"
    label_part = f" [{label}]" if label else ""

    # Color/ANSI control
    # Default: enable ANSI colors unless explicitly disabled.
    no_color = bool(env_get("NO_COLOR") or env_get("UAGENT_NO_COLOR"))
    stderr_is_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())

    # Prefer a natural newline boundary so status does not split a sentence.
    # If the stream stays open past the deadline, force-close the line with a
    # newline first — never write [STATE] into the middle of assistant text.
    deadline = time.time() + 0.25
    nl = chr(10)
    while True:
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
                    _reasoning_stream_open = False
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
                            _sync_spinner_to_status(True)
                            return
                    except Exception:
                        pass
                use_color = want_color
                _write_status_line(
                    f"[STATE] {state}{label_part}",
                    busy=busy,
                    use_color=use_color,
                )
                return
        time.sleep(0.005)
