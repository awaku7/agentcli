"""Braille spinner for the interactive CLI (ollama-like progress).

Safety-first design:

- Default ON. Opt out with ``UAGENT_SPINNER=0``. Any of
  ``UAGENT_SPINNER=0`` / ``UAGENT_SPINNER_OFF=1`` / ``NO_COLOR`` / non-TTY stderr / GUI / Web disables it,
  and the legacy ``[STATE]`` one-line display keeps working unchanged.
- stderr only, single-line ``\\r`` rewrite. Never touches stdout, so the
  streaming assistant text is never polluted.
- Leaves one final ``OK done`` line in scrollback on stop
  (disable with ``UAGENT_SPINNER_DONE=off``), so history stays visible
  after scrolling. Stream start stays clean with no done line.
- Stops automatically when the first stream delta arrives
  (:func:`notify_stream_started`), when busy clears, when ``human_ask`` owns
  stdin, or when a prompt line is open — the same conditions the legacy
  ``print_status_line`` already respects.
- Windows legacy consoles (cp932) cannot render braille; fall back to ASCII
  ``|/-\\\\`` there. Disable entirely with ``UAGENT_SPINNER=0``.
"""

from __future__ import annotations

import os
import sys
import threading
import time

_FRAMES_BRAILLE = tuple("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
_FRAMES_ASCII = tuple("|/-\\")

_lock = threading.RLock()
_thread: threading.Thread | None = None
_stop = threading.Event()
_frame_index = 0
_DREW = False
_last_len = 0
_started_at: float | None = None
_last_label = ""


def _env_flag(name: str, *, default: bool = False) -> bool:
    try:
        from ..env_utils import env_get

        raw = (env_get(name, "") or "").strip().lower()
    except Exception:
        raw = (os.environ.get(name, "") or "").strip().lower()
    if raw == "":
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def spinner_enabled() -> bool:
    """Return True unless explicitly disabled and output is safe."""
    # Default ON: opt out with UAGENT_SPINNER=0.
    if not _env_flag("UAGENT_SPINNER", default=True):
        return False
    # Hard OFF switches (any one disables).
    if _env_flag("UAGENT_SPINNER_OFF", default=False):
        return False
    if _env_flag("NO_COLOR", default=False) or _env_flag("UAGENT_NO_COLOR", default=False):
        # NO_COLOR historically means "no decoration"; keep legacy [STATE] only.
        return False
    # Dumb terminals cannot handle CR rewrite; keep legacy [STATE] only.
    # Erase-only policy: stop() clears the line with spaces + CR, no newline,
    # so the next display starts cleanly on the same line.
    try:
        _term = (os.environ.get("TERM") or "").strip().lower()
    except Exception:
        _term = ""
    if _term in {"dumb", "unknown"}:
        return False
    try:
        from .. import core as _core

        if bool(getattr(_core, "IS_GUI", False)):
            return False
    except Exception:
        pass
    try:
        import sys as _sys

        if bool(getattr(_sys.modules.get("uagent.core_impl.display", None), "_is_web", False)):
            return False
    except Exception:
        pass
    try:
        if not sys.stderr.isatty():
            return False
    except Exception:
        return False
    return True


def _frames() -> tuple[str, ...]:
    """Braille when the console can render it, ASCII fallback otherwise."""
    try:
        enc = (getattr(sys.stderr, "encoding", "") or "").lower()
        if os.name == "nt" and ("cp932" in enc or "shift" in enc or "ansi" in enc):
            return _FRAMES_ASCII
        sys.stderr.write("")  # probe writability without visible output
        return _FRAMES_BRAILLE
    except Exception:
        return _FRAMES_ASCII


def _spinner_use_color() -> bool:
    """Mirror the [STATE] BUSY color policy so the spinner stays visible."""
    try:
        from ..env_utils import env_get as _env_get
        no_color = bool(_env_get("NO_COLOR") or _env_get("UAGENT_NO_COLOR"))
        status_color_env = ((_env_get("UAGENT_STATUS_COLOR") or "").strip().lower())
    except Exception:
        no_color = False
        status_color_env = ""
    if status_color_env in ("0", "false", "no", "off"):
        return False
    if no_color:
        return False
    try:
        from .. import core as _core
        if bool(getattr(_core, "IS_GUI", False)):
            return False
    except Exception:
        pass
    try:
        if not sys.stderr.isatty():
            return False
    except Exception:
        return False
    return True


def _write_spinner_frame(text: str, pad: int) -> None:
    """Write one spinner frame in BUSY yellow when color is allowed."""
    cr = chr(13)
    esc = chr(27)
    tail = (" " * pad) if pad > 0 else ""
    if not _spinner_use_color():
        sys.stderr.write(cr + text + tail)
        sys.stderr.flush()
        return
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(wintypes.DWORD(-12).value)
            invalid = wintypes.HANDLE(-1).value
            if handle and handle != invalid:
                class COORD(ctypes.Structure):
                    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]
                class SMALL_RECT(ctypes.Structure):
                    _fields_ = [(n, wintypes.SHORT) for n in ("Left", "Top", "Right", "Bottom")]
                class CSBI(ctypes.Structure):
                    _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD), ("wAttributes", wintypes.WORD), ("srWindow", SMALL_RECT), ("dwMaximumWindowSize", COORD)]
                info = CSBI()
                if kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                    old_attr = int(info.wAttributes)
                    kernel32.SetConsoleTextAttribute(handle, (old_attr & 0xF0) | 0x0E)
                    try:
                        data = cr + text + tail
                        written = wintypes.DWORD(0)
                        if not kernel32.WriteConsoleW(handle, data, len(data), ctypes.byref(written), None):
                            sys.stderr.write(data)
                            sys.stderr.flush()
                    finally:
                        kernel32.SetConsoleTextAttribute(handle, old_attr)
                    return
        except Exception:
            pass
        sys.stderr.write(cr + text + tail)
        sys.stderr.flush()
        return
    sys.stderr.write(cr + esc + "[33m" + text + esc + "[0m" + tail)
    sys.stderr.flush()


def _current_label(default: str = "...") -> str:
    try:
        from .. import core as _core

        with _core.status_lock:
            label = str(getattr(_core, "status_label", "") or "").strip()
        return label or default
    except Exception:
        return default


def _ok_to_draw() -> bool:
    """Mirror the guards in print_status_line so we never fight other output."""
    try:
        from .. import core as _core
    except Exception:
        return False
    try:
        with _core.human_ask_lock:
            if bool(getattr(_core, "human_ask_active", False)):
                return False
        if bool(getattr(_core, "_stream_line_open", False)):
            return False
        if bool(getattr(_core, "_prompt_line_open", False)):
            return False
        if bool(getattr(_core, "_reasoning_stream_open", False)):
            return False
        with _core.status_lock:
            if not bool(getattr(_core, "status_busy", False)):
                return False
    except Exception:
        return False
    return True


def _loop(interval: float, frames: tuple[str, ...]) -> None:
    global _frame_index, _DREW, _last_len, _last_label
    n = len(frames)
    while not _stop.wait(interval):
        if not spinner_enabled():
            continue
        if not _ok_to_draw():
            continue
        try:
            from .. import core as _core

            with _core.print_lock:
                if not _ok_to_draw():
                    continue
                frame = frames[_frame_index % n]
                _frame_index += 1
                label = _current_label()
                text = frame + " [" + label + "] ..."
                pad = max(0, _last_len - len(text))
                _write_spinner_frame(text, pad)
                _DREW = True
                _last_len = len(text)
                _last_label = label
        except Exception:
            continue


def start(interval: float = 0.08) -> None:
    """Start the spinner thread (no-op when disabled)."""
    global _thread, _started_at, _last_label
    if not spinner_enabled():
        return
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _started_at = time.monotonic()
        _last_label = _current_label()
        frames = _frames()
        _thread = threading.Thread(
            target=_loop, args=(interval, frames), name="uagent-spinner", daemon=True
        )
        _thread.start()


def _done_line_kept() -> bool:
    """Return True when the finished line should stay in scrollback."""
    try:
        from ..env_utils import env_get as _env_get

        raw = ((_env_get("UAGENT_SPINNER_DONE") or "").strip().lower())
    except Exception:
        try:
            raw = ((os.environ.get("UAGENT_SPINNER_DONE") or "").strip().lower())
        except Exception:
            raw = ""
    # Default: keep "done" line ("off"/"0"/"false"/"no"/"clear" to erase).
    return raw not in ("0", "false", "no", "off", "clear", "erase")


def _write_done_line(label: str, elapsed: float | None) -> None:
    """Write the final status line that stays in scrollback history."""
    nl = (chr(13) + chr(10)) if os.name == "nt" else chr(10)
    esc = chr(27)
    msg = "done"
    if label:
        msg = msg + " [" + label + "]"
    if elapsed is not None and elapsed >= 0:
        msg = msg + " in " + ("%.1fs" % (elapsed,))
    line = "OK " + msg
    use_color = False
    try:
        use_color = _spinner_use_color()
    except Exception:
        use_color = False
    if not use_color:
        sys.stderr.write(line + nl)
        sys.stderr.flush()
        return
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(wintypes.DWORD(-12).value)
            invalid = wintypes.HANDLE(-1).value
            if handle and handle != invalid:

                class _C(ctypes.Structure):
                    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

                class _R(ctypes.Structure):
                    _fields_ = [(n, wintypes.SHORT) for n in ("Left", "Top", "Right", "Bottom")]

                class _B(ctypes.Structure):
                    _fields_ = [("dwSize", _C), ("dwCursorPosition", _C), ("wAttributes", wintypes.WORD), ("srWindow", _R), ("dwMaximumWindowSize", _C)]

                info = _B()
                if kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                    old_attr = int(info.wAttributes)
                    kernel32.SetConsoleTextAttribute(handle, (old_attr & 0xF0) | 0x0A)
                    try:
                        data = line + nl
                        written = wintypes.DWORD(0)
                        if not kernel32.WriteConsoleW(handle, data, len(data), ctypes.byref(written), None):
                            sys.stderr.write(data)
                            sys.stderr.flush()
                    finally:
                        kernel32.SetConsoleTextAttribute(handle, old_attr)
                    return
        except Exception:
            pass
        sys.stderr.write(line + nl)
        sys.stderr.flush()
        return
    sys.stderr.write(esc + "[32m" + line + esc + "[0m" + nl)
    sys.stderr.flush()


def stop(*, clear: bool = True, keep_last_line: bool | None = None) -> None:
    """Stop the spinner and erase its line. Always safe to call."""
    global _thread, _DREW, _last_len, _started_at, _last_label
    with _lock:
        th = _thread
        _thread = None
        _stop.set()
        drew = _DREW
        _DREW = False
        last_len = _last_len
        _last_len = 0
    if th is not None:
        try:
            th.join(timeout=0.2)
        except Exception:
            pass
    # Erase the drawn line, then leave one final line in scrollback
    # (e.g. "OK done [LLM] in 3.2s") so the work stays visible after scroll.
    # Never emit output when the spinner never drew (disabled path).
    keep = keep_last_line
    if keep is None:
        try:
            keep = _done_line_kept()
        except Exception:
            keep = True
    label = ""
    elapsed = None
    try:
        label = str(_last_label or "").strip()
    except Exception:
        label = ""
    if not label:
        try:
            label = _current_label(default="")
        except Exception:
            label = ""
    try:
        if _started_at is not None:
            elapsed = time.monotonic() - float(_started_at)
    except Exception:
        elapsed = None
    try:
        with _lock:
            _started_at = None
            _last_label = ""
    except Exception:
        pass
    if clear and drew:
        try:
            from .. import core as _core

            with _core.print_lock:
                width = max(int(last_len), 0)
                if width <= 0:
                    width = 40
                sys.stderr.write("\r" + (" " * width) + "\r")
                sys.stderr.flush()
                if keep:
                    _write_done_line(label, elapsed)
        except Exception:
            pass


def notify_stream_started() -> None:
    """Stop spinning as soon as the first token arrives (ollama-style)."""
    try:
        # No done-line here: the answer itself stays in scrollback.
        stop(keep_last_line=False)
    except Exception:
        pass


def stop_quietly(*, clear: bool = True) -> None:
    """Best-effort spinner stop; never raises, never changes legacy output.

    The spinner draws on the same stderr line via CR rewrite.
    Call this before any print so the text does not stick to the spinner
    frame like "⠧ [LLM:auto] ...[INFO] ...". Always safe: no-op when
    disabled or never drew.
    """
    try:
        stop(clear=clear)
    except Exception:
        pass


def paused():
    """Context manager: clear the spinner line while other output prints.

    Usage:
        with spinner.paused():
            print("[TOOL] ...")

    Stops the thread, erases the drawn line, yields, then restarts only
    when still BUSY. Always safe: no-op when disabled or never drew.
    """
    from contextlib import contextmanager as _cm

    @_cm
    def _inner():
        try:
            stop(clear=True)
        except Exception:
            pass
        try:
            yield
        finally:
            try:
                from .. import core as _core

                busy = bool(getattr(_core, "status_busy", False))
            except Exception:
                busy = False
            if busy:
                try:
                    start()
                except Exception:
                    pass

    return _inner()
