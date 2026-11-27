"""Full-screen console view for the interactive CLI (single-writer 2b).

The view is the terminal renderer decided for stage 2b: a scrolling
output area above a fixed bottom region — spinner line, rule, the
1-line input area, rule, and the status line on the very bottom line.
The status line can also show the latest provider-reported token usage
without adding a transcript line.  The layout follows Claude Code's CLI.
The input line carries no prompt
text, only the cursor; the prompt's identifying text (the working
directory at idle) rides inside the upper rule instead.  The output area is a projection
of the shared output document (``runtime.display_channel``): the
view subscribes to the document and re-projects its tail as new
segments arrive, colouring each segment by its kind — colour is
this renderer's decision, and the document itself holds none.  The
status/spinner setters mirror ``core.set_status`` state, and
submitted input lines are handed to ``stdin_loop`` through a queue
so every existing post-processing path (commands, human_ask
routing, chat-mode forwarding) is unchanged.

The view is a replaceable renderer: while it is suspended (the
multiline editor, or a legacy prompt in a mode the view does not
serve) or not started, :func:`active_view` returns None and every
producer falls back to the legacy terminal writers.  A human_ask
does not suspend it: the question already sits in the output
document, so the view switches its input row into reply mode and
answers there (see :meth:`ConsoleView.begin_reply`); the legacy
reply/password prompts serve only the modes where no view runs.

Enablement: interactive TTY + prompt_toolkit available + chat mode
off, unless ``UAGENT_CLI_VIEW=0`` (the one new switch; it is the
escape hatch for the full-screen renderer).  Region colours reuse
the existing flags: the spinner follows ``UAGENT_SPINNER_COLOR``
(named colours, with the legacy label-based defaults), and the
status line follows the ``UAGENT_STATUS_COLOR`` / ``NO_COLOR``
on-off policy with the legacy BUSY yellow / IDLE green.  The rule
lines use a fixed muted colour; no existing flag covers them and no
new one is added.

While the view runs, ``sys.stdout``/``sys.stderr`` are replaced with
line-buffering proxies that forward Python-level writes (``print``,
debug output, tracebacks) into the output document — stdout as
``output`` segments, stderr as ``debug`` segments — so stray writes
do not corrupt the full-screen rendering or vanish with the
alternate screen.  The originals are restored whenever the view
suspends or stops.  File-descriptor-level output (child processes
inheriting the real terminal) is not captured.

Input during generation (stage 2b, second half): the input area
stays live while a turn runs.  A message submitted while busy opens
an interrupt confirmation on its own line above the input area —
Enter/y interrupts the turn and sends the message next, n queues
it.  Commands (``:``-prefixed) skip the question and queue
directly.  Queued lines dispatch in FIFO order once the turn ends;
their document echo carries a pending marker until the moment they
are dispatched.  The confirmation never interrupts by default: a
human_ask preempting it (the view suspends) or the turn simply
ending resolves it as "queue", with a notice in the transcript for
the preempted case.

Mouse: the view owns the mouse while it runs, so it provides the
two things the terminal's own handling otherwise would — the
wheel scrolls the output area no matter where the pointer is,
and dragging over the output (or the input) selects text and
copies it to the system clipboard on release; right-click pastes
into the input.
"""

from __future__ import annotations

import collections
import io
import queue
import sys
import threading
import time
from typing import Any, Callable, Mapping


from ..env_utils import env_get
from ..i18n import _

_EOF = object()
# A reply wait ended by Ctrl+C inside the view (see wait_reply).
_REPLY_CANCELLED = object()
# Cap on the prompt prefix: longer prompts are truncated with an
# ellipsis so they cannot eat the whole input row.  The prompt
# window itself hugs the (possibly truncated) text.
_PREFIX_MAX_WIDTH = 24

_active_lock = threading.Lock()
_active_view: "ConsoleView | None" = None


def active_view() -> "ConsoleView | None":
    """The console view currently rendering the terminal, if any."""
    with _active_lock:
        return _active_view


def _set_active(view: "ConsoleView | None") -> None:
    global _active_view
    with _active_lock:
        _active_view = view


class _ViewStreamProxy(io.TextIOBase):
    """Line-buffering stand-in for sys.stdout/sys.stderr.

    Everything written at Python level while the view runs lands in
    the shared output document, under the stream's kind (stdout is
    ``output``, stderr is ``debug`` — the app's diagnostics go to
    stderr).  Partial lines are held until a newline (or flush) so
    interleaved writers cannot split each other's lines mid-way
    more than the legacy terminal already did.
    """

    def __init__(self, original: Any, kind: str) -> None:
        super().__init__()
        self._original = original
        self._kind = kind
        self._pending = ""
        self._lock = threading.Lock()

    # -- writing ------------------------------------------------------

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)
        with self._lock:
            self._pending += text
            while "\n" in self._pending:
                line, self._pending = self._pending.split("\n", 1)
                self._post(line + "\n")
        return len(text)

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        with self._lock:
            if self._pending:
                pending, self._pending = self._pending, ""
                self._post(pending)

    def _post(self, text: str) -> None:
        from ..runtime import display_channel

        display_channel.post_segment(self._kind, text)

    def flush_partial(self) -> None:
        """Push any held partial line into the document (on suspend)."""
        self.flush()

    # -- delegation ---------------------------------------------------

    @property
    def buffer(self):  # fd-level escape hatch, intentionally the real one
        return self._original.buffer

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", None) or "utf-8"

    @property
    def errors(self):
        return getattr(self._original, "errors", None)

    def isatty(self) -> bool:
        try:
            return bool(self._original.isatty())
        except Exception:
            return False

    def fileno(self) -> int:
        return self._original.fileno()

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False


# ---------------------------------------------------------------------
# Pre-view startup output capture
#
# Startup prints (welcome, banner, [INFO], warnings) happen before
# the full-screen view exists.  Once the view takes over the
# terminal, that earlier output sits on the main screen buffer,
# hidden for the whole session.  A transparent tee over
# sys.stdout/sys.stderr keeps a bounded copy of everything printed
# before the view starts; when the view is created, the copy seeds
# its output document, so the startup output stays visible inside
# the view like any other output.
# ---------------------------------------------------------------------

_STARTUP_CAPTURE_LIMIT = 100_000

_startup_capture_lock = threading.Lock()
_startup_stdout_parts: list[str] = []
_startup_stderr_parts: list[str] = []
_startup_stdout_len = 0
_startup_stderr_len = 0


class _StartupOutputTee(io.TextIOBase):
    """Forward a stream unchanged while keeping a copy of writes."""

    def __init__(self, original: Any, sink: list[str], is_stdout: bool) -> None:
        super().__init__()
        self._original = original
        self._sink = sink
        self._is_stdout = is_stdout

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)
        global _startup_stdout_len, _startup_stderr_len
        with _startup_capture_lock:
            if self._is_stdout:
                if _startup_stdout_len < _STARTUP_CAPTURE_LIMIT:
                    self._sink.append(text)
                    _startup_stdout_len += len(text)
            else:
                if _startup_stderr_len < _STARTUP_CAPTURE_LIMIT:
                    self._sink.append(text)
                    _startup_stderr_len += len(text)
        return self._original.write(text)

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        return self._original.flush()

    def isatty(self) -> bool:
        try:
            return bool(self._original.isatty())
        except Exception:
            return False

    def fileno(self) -> int:
        return self._original.fileno()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


def install_startup_output_capture() -> None:
    """Wrap sys.stdout/sys.stderr with the startup tee (idempotent).

    The wrappers forward everything, so installing them changes
    nothing unless a console view is later created and drains the
    copies.  Best-effort: any failure leaves the streams as they
    were.
    """
    try:
        if not isinstance(sys.stdout, _StartupOutputTee):
            sys.stdout = _StartupOutputTee(sys.stdout, _startup_stdout_parts, True)
        if not isinstance(sys.stderr, _StartupOutputTee):
            sys.stderr = _StartupOutputTee(sys.stderr, _startup_stderr_parts, False)
    except Exception:
        pass


def take_startup_output() -> tuple[str, str]:
    """Drain the captured pre-view startup output (stdout, stderr)."""
    global _startup_stdout_len, _startup_stderr_len
    with _startup_capture_lock:
        out = "".join(_startup_stdout_parts)
        err = "".join(_startup_stderr_parts)
        _startup_stdout_parts.clear()
        _startup_stderr_parts.clear()
        _startup_stdout_len = 0
        _startup_stderr_len = 0
    return out, err


def seed_document_from_startup_output() -> None:
    """Post the captured startup output into the shared document."""
    out, err = take_startup_output()
    if not out and not err:
        return
    from ..runtime import display_channel

    if out:
        display_channel.post_segment("output", out)
    if err:
        display_channel.post_segment("debug", err)


class _OutputLexer:
    """Applies the projected kind-colour ranges line by line.

    The ranges are computed when the view projects the output
    document (see ``ConsoleView._project_document``); each fragment's
    style is the raw prompt_toolkit spec for that span's kind.
    """

    def __init__(self, view: "ConsoleView") -> None:
        self._view = view

    def invalidation_hash(self) -> int:
        # prompt_toolkit keys its fragment cache on this; the
        # projected ranges change exactly when the projection
        # version does.
        return self._view._proj_version

    def lex_document(self, document: Any):
        text = document.text
        ranges = list(self._view._style_ranges)
        starts = [0]
        for index, char in enumerate(text):
            if char == "\n":
                starts.append(index + 1)

        def get_line(line_no: int):
            if line_no >= len(starts):
                return [("", "")]
            start = starts[line_no]
            end = text.find("\n", start)
            if end < 0:
                end = len(text)
            fragments: list[tuple[str, str]] = []
            pos = start
            for range_start, range_end, spec in ranges:
                if range_end <= start or range_start >= end:
                    continue
                lo = max(range_start, start)
                hi = min(range_end, end)
                if lo > pos:
                    fragments.append(("", text[pos:lo]))
                fragments.append((spec, text[lo:hi]))
                pos = hi
            if pos < end:
                fragments.append(("", text[pos:end]))
            return fragments or [("", text[start:end])]

        return get_line


def _write_system_clipboard(text: str) -> bool:
    """Best-effort write to the OS clipboard (Windows via ctypes).

    The full-screen view owns the mouse, so the terminal's own
    selection is unavailable; text the user selects in the view
    is copied through here.  Any failure just leaves the copy
    inside the app.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            # ctypes defaults to C int for return values and
            # arguments; the handles and pointers here are
            # pointer-sized on 64-bit Windows, so declare the
            # signatures — otherwise the values truncate, and
            # memmove can write through a truncated pointer.
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalFree.restype = wintypes.HGLOBAL
            kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.argtypes = []
            user32.SetClipboardData.restype = wintypes.HANDLE
            user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            kernel32.GetConsoleWindow.restype = wintypes.HWND
            kernel32.GetConsoleWindow.argtypes = []
            # Fill the memory block before touching the clipboard,
            # so a failure up to here leaves the user's current
            # clipboard contents alone.
            data = text.encode("utf-16-le") + b"\x00\x00"
            handle = kernel32.GlobalAlloc(0x0002, len(data))
            if not handle:
                return False
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                return False
            try:
                ctypes.memmove(pointer, data, len(data))
            finally:
                kernel32.GlobalUnlock(handle)
            # The clipboard needs a real owner window: opened
            # with NULL, EmptyClipboard leaves the owner NULL and
            # SetClipboardData then fails — after the previous
            # contents were already erased.  The console window
            # is this process's window.
            owner = kernel32.GetConsoleWindow()
            if not owner:
                kernel32.GlobalFree(handle)
                return False
            if not user32.OpenClipboard(owner):
                kernel32.GlobalFree(handle)
                return False
            try:
                user32.EmptyClipboard()
                if not user32.SetClipboardData(13, handle):
                    kernel32.GlobalFree(handle)
                    return False
                return True
            finally:
                user32.CloseClipboard()
        except Exception:
            return False
    # The native command-line clipboard tools need no extra
    # dependency: pbcopy always ships with macOS, and on Linux
    # the Wayland and X11 tools are tried in turn.  pyperclip,
    # when a user happens to have it, is the last resort.
    import shutil
    import subprocess

    if sys.platform == "darwin":
        candidates = [["pbcopy"]]
    else:
        candidates = [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ]
    for command in candidates:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(
                command,
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return True
        except Exception:
            continue
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:
        return False


def _read_system_clipboard() -> str | None:
    """Best-effort read of plain text from the OS clipboard."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.GetClipboardData.restype = wintypes.HANDLE
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            kernel32.GetConsoleWindow.restype = wintypes.HWND
            kernel32.GetConsoleWindow.argtypes = []
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

            if user32.OpenClipboard(kernel32.GetConsoleWindow()):
                try:
                    handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
                    if handle:
                        pointer = kernel32.GlobalLock(handle)
                        if pointer:
                            try:
                                return ctypes.wstring_at(pointer)
                            finally:
                                kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

    import shutil
    import subprocess

    if sys.platform == "darwin":
        candidates = [["pbpaste"]]
    elif sys.platform != "win32":
        candidates = [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]
    else:
        candidates = []
    for command in candidates:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace")
        except Exception:
            continue
    try:
        import pyperclip

        pasted = pyperclip.paste()
        return pasted if isinstance(pasted, str) else None
    except Exception:
        return None


def _make_clipboard(write_guard: Callable[[], bool] | None = None) -> Any:
    """An app clipboard that also mirrors copies to the OS one.

    ``write_guard``, when given, is consulted on every write: a
    False verdict freezes the clipboard (the previous content is
    kept, nothing is stored or mirrored).  The console view uses
    it to keep a password reply's text out of the clipboard —
    the keyboard cut bindings (Ctrl+K and friends) write through
    here just like the mouse copy does.
    """
    from prompt_toolkit.clipboard.base import Clipboard, ClipboardData

    class _SystemClipboard(Clipboard):
        def __init__(self) -> None:
            self._data = ClipboardData("")

        def set_data(self, data: Any) -> None:
            if write_guard is not None:
                try:
                    if not write_guard():
                        return
                except Exception:
                    pass
            self._data = data
            try:
                _write_system_clipboard(data.text)
            except Exception:
                pass

        def get_data(self) -> Any:
            return self._data

    return _SystemClipboard()


def view_enabled() -> bool:
    """Whether the full-screen view may be used for this session."""
    if str(env_get("UAGENT_CLI_VIEW", "1")).strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    try:
        import prompt_toolkit  # noqa: F401
    except Exception:
        return False
    return True


_ANSI_NAMES = {
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
}


def _spinner_style() -> dict[str, str]:
    """Spinner styles from the existing UAGENT_SPINNER_COLOR flag."""
    configured = str(env_get("UAGENT_SPINNER_COLOR", "") or "").strip().lower()
    if configured in _ANSI_NAMES:
        colour = f"ansi{configured}"
        return {
            "spinner": colour,
            "spinner.tool": colour,
            "spinner.subagent": colour,
        }
    # Legacy label-based defaults (spinner._spinner_color).
    return {
        "spinner": "ansiyellow",
        "spinner.tool": "ansicyan",
        "spinner.subagent": "ansimagenta",
    }


def _status_styles() -> dict[str, str]:
    """Status styles from the existing colour on/off policy."""
    no_color = bool(env_get("NO_COLOR") or env_get("UAGENT_NO_COLOR"))
    status_env = str(env_get("UAGENT_STATUS_COLOR", "") or "").strip().lower()
    if no_color or status_env in ("0", "false", "no", "off"):
        return {"status.busy": "", "status.idle": ""}
    return {"status.busy": "ansiyellow", "status.idle": "ansigreen"}


def _kind_style(kind: str) -> str:
    """The view's own colour for a segment kind.

    Typed output carries no colour decision of its own; the view
    decides by kind — reasoning is gray, as the legacy terminal's
    ANSI 90m wrap made it.  The existing NO_COLOR policy turns
    kind colours off as well.
    """
    if kind != "reasoning":
        return ""
    if env_get("NO_COLOR") or env_get("UAGENT_NO_COLOR"):
        return ""
    return "ansibrightblack"


class ConsoleView:
    """Owns the full-screen terminal layout while it is running."""

    def __init__(
        self,
        *,
        completer: Any = None,
        history: Any = None,
        on_ctrl_c: Callable[[], None] | None = None,
        on_f12: Callable[[], None] | None = None,
        on_interrupt: Callable[[], None] | None = None,
        pt_input: Any = None,
        pt_output: Any = None,
        document: Any = None,
    ) -> None:
        from prompt_toolkit.buffer import Buffer
        from prompt_toolkit.document import Document
        from prompt_toolkit.filters import Condition

        self._Document = Document
        self._output_buffer = Buffer(read_only=True)
        self._output_window: Any = None
        self._output_control: Any = None
        # The view is a projection of the shared output document
        # (runtime.display_channel): it keeps the projected text and
        # the kind-colour ranges computed from the document's
        # segments.  Colour by kind is this view's decision.
        self._document: Any = document
        self._subscribed = False
        self._style_ranges: list[tuple[int, int, str]] = []
        self._proj_version = -1
        self._proj_epoch = -1
        self._proj_seg_count = 0
        self._proj_prefix_len = 0
        self._lexer = _OutputLexer(self)
        # The text of a message submitted during generation, while
        # its interrupt confirmation is unanswered (see _submit).
        # The input buffer is read-only exactly while this is set.
        self._confirm_text: str | None = None
        self._reset_pending: bool = False
        self._input_buffer = Buffer(
            completer=completer,
            history=history,
            multiline=True,
            # Like the legacy PromptSession: candidates appear
            # while typing, not only on Tab.
            complete_while_typing=True,
            read_only=Condition(
                lambda: self._confirm_text is not None or self._reset_pending
            ),
        )
        # Queue items are (text, pending token) pairs; the token is
        # the output document's pending-user segment for a line that
        # was queued during generation, else None.
        self._submissions: queue.Queue[Any] = queue.Queue()
        # Lines the user chose to interrupt for: wait_line returns
        # them ahead of the ordinary queue.
        self._priority: queue.Queue[Any] = queue.Queue()
        # Lines the reader already took and hands back to go first
        # among the ordinary ones (see requeue_front): a line held
        # by the busy-at-submit wait that a priority line overtook.
        self._front: collections.deque[Any] = collections.deque()
        self._last_pending_token: Any = None
        self._last_line_priority: bool = False
        # human_ask reply mode: while a question is open, the input
        # row answers it instead of submitting a new line, so the
        # view never has to suspend for the legacy reply prompt.
        # _reply_label is the ask's prompt text (None = reply mode
        # off); the buffer surgery (stash the draft, clear, mask)
        # runs on the application thread and arms the mode — an
        # Enter that lands before it runs must not turn the stashed
        # draft into the reply.
        self._reply_label: str | None = None
        self._reply_is_password: bool = False
        self._reply_armed: bool = False
        self._reply_queue: queue.Queue[Any] = queue.Queue()
        self._reply_draft: Any = None
        self._reply_completer: Any = None
        self._reply_history: Any = None
        self._reply_macro_before: Any = None
        self._on_ctrl_c = on_ctrl_c
        self._on_f12 = on_f12
        self._on_interrupt = on_interrupt
        self._pt_input = pt_input
        self._pt_output = pt_output
        self._prompt_text = ""
        self._spinner_label: str | None = None
        self._spinner_started = time.monotonic()
        self._status_text = ""
        self._status_busy = False
        self._usage_text = ""
        self._usage_compact_text = ""
        self._usage_session_id: str | None = None
        self._usage_totals = {
            "input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens": 0,
        }
        self._output_text = ""
        self._app: Any = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._generation = 0
        self._state_lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._orig_stdout: Any = None
        self._orig_stderr: Any = None
        self._proxy_stdout: _ViewStreamProxy | None = None
        self._proxy_stderr: _ViewStreamProxy | None = None

    # -- lifecycle ------------------------------------------------------

    def start(self) -> None:
        """Run the application on its own thread (no-op if running)."""
        with self._state_lock:
            if self._running:
                return
            self._running = True
            self._generation += 1
            generation = self._generation
        if self._document is None:
            from ..runtime import display_channel

            self._document = display_channel.default_document()
        if not self._subscribed:
            self._document.subscribe(self._on_document_change)
            self._subscribed = True
        _set_active(self)
        self._thread = threading.Thread(
            target=self._run_app,
            args=(generation,),
            name="uagent-console-view",
            daemon=True,
        )
        self._thread.start()

    def suspend(self) -> None:
        """Exit the application so legacy prompts can own the terminal.

        Buffers and region state survive; :meth:`start` resumes with a
        fresh Application around the same state.
        """
        with self._state_lock:
            self._running = False
            # Invalidate any startup still constructing its application;
            # _run_app checks the generation before it may install the
            # stream capture or enter its run loop.
            self._generation += 1
            app = self._app
            thread = self._thread
        if active_view() is self:
            _set_active(None)
        if app is not None:
            try:
                loop = app.loop
                if loop is not None:
                    loop.call_soon_threadsafe(lambda: app.exit())
                else:
                    app.exit()
            except Exception:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
            if thread.is_alive():
                # The application did not unwind in time.  The real
                # streams must be back before any legacy prompt owns
                # the terminal, so restore the capture here; the run
                # thread's own restore is identity-checked and will
                # simply find nothing left to do.
                self._restore_capture()
        with self._state_lock:
            if self._thread is thread:
                self._thread = None
            if self._app is app:
                self._app = None
        # A human_ask (or another legacy prompt) taking the terminal
        # preempts an open interrupt confirmation.  The message is
        # never lost and never interrupts as a side effect: it
        # queues, and the transcript says so.  This runs after the
        # application thread has unwound, so touching the input
        # buffer here cannot race it.
        if self._resolve_open_confirmation_as_queue():
            self._reset_input_buffer()
        # A reply wait still outstanding ends with the suspension:
        # wait_reply sees the view stop running and reports EOF.
        # Restore the stashed draft and completer here, while no
        # application thread can race the buffer.
        with self._state_lock:
            reply_was_active = self._reply_label is not None
        if reply_was_active:
            self._restore_reply_buffer()

    def stop(self) -> None:
        self.suspend()

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._running

    def _run_app(self, generation: int) -> None:
        app = self._make_app()
        with self._state_lock:
            if generation != self._generation or not self._running:
                # Suspended (or superseded by a newer start) while the
                # application was being constructed: never touch the
                # terminal, the streams, or the run loop.
                return
            self._app = app
        if self._reset_pending:
            # A reset posted for a worker-resolved confirmation
            # never ran (the previous application exited first);
            # the buffer still holds the answered message and is
            # still read-only.
            self._reset_input_buffer()
        # The application output is built from the real streams inside
        # _make_app; only now is it safe to redirect Python-level
        # stdout/stderr into the document.
        self._install_capture()
        installed = sys.stdout is self._proxy_stdout
        self._project_document()
        try:
            app.run()
        except Exception:
            pass
        finally:
            if installed:
                self._restore_capture()
            with self._state_lock:
                if self._app is app:
                    self._app = None
                if generation == self._generation:
                    self._running = False
            if active_view() is self:
                _set_active(None)

    def _install_capture(self) -> None:
        with self._capture_lock:
            if isinstance(sys.stdout, _ViewStreamProxy) or isinstance(
                sys.stderr, _ViewStreamProxy
            ):
                return
            self._orig_stdout = sys.stdout
            self._orig_stderr = sys.stderr
            self._proxy_stdout = _ViewStreamProxy(sys.stdout, "output")
            self._proxy_stderr = _ViewStreamProxy(sys.stderr, "debug")
            sys.stdout = self._proxy_stdout
            sys.stderr = self._proxy_stderr
            self._redirect_stream_handlers()

    def _restore_capture(self) -> None:
        with self._capture_lock:
            # Held partial lines belong to the view's output history,
            # not to the restored terminal.
            for proxy in (self._proxy_stdout, self._proxy_stderr):
                if proxy is not None:
                    try:
                        proxy.flush_partial()
                    except Exception:
                        pass
            self._restore_stream_handlers()
            if sys.stdout is self._proxy_stdout and self._orig_stdout is not None:
                sys.stdout = self._orig_stdout
            if sys.stderr is self._proxy_stderr and self._orig_stderr is not None:
                sys.stderr = self._orig_stderr
            self._proxy_stdout = None
            self._proxy_stderr = None

    def _redirect_stream_handlers(self) -> None:
        """Point pre-existing stderr logging handlers at the capture.

        Handlers created before the view starts (the UAGENT_DEBUG_EVENTS
        event logger, for one) hold the original stderr object, so
        replacing sys.stderr alone leaves them writing onto the
        full-screen terminal and out of the transcript.  Only handlers
        bound to the very stream being captured are redirected.  A
        handler bound before the startup tee was installed holds the
        stream the tee wraps rather than the tee itself; that stream
        counts as the captured one too.
        """
        try:
            import logging

            captured = [self._orig_stderr]
            inner = getattr(self._orig_stderr, "_original", None)
            if inner is not None and inner is not self._orig_stderr:
                captured.append(inner)
            loggers = [logging.getLogger()]
            loggers += [
                logging.getLogger(name)
                for name in list(logging.Logger.manager.loggerDict)
            ]
            for logger in loggers:
                for handler in getattr(logger, "handlers", []):
                    # Per-handler isolation: one broken handler
                    # must not skip the remaining ones.
                    try:
                        if isinstance(handler, logging.StreamHandler) and any(
                            getattr(handler, "stream", None) is stream
                            for stream in captured
                        ):
                            handler.setStream(self._proxy_stderr)
                    except Exception:
                        pass
        except Exception:
            pass

    def _restore_stream_handlers(self) -> None:
        """Undo :meth:`_redirect_stream_handlers` (identity-checked)."""
        try:
            import logging

            loggers = [logging.getLogger()]
            loggers += [
                logging.getLogger(name)
                for name in list(logging.Logger.manager.loggerDict)
            ]
            for logger in loggers:
                for handler in getattr(logger, "handlers", []):
                    try:
                        if (
                            isinstance(handler, logging.StreamHandler)
                            and getattr(handler, "stream", None) is self._proxy_stderr
                        ):
                            handler.setStream(self._orig_stderr)
                    except Exception:
                        pass
        except Exception:
            pass

    # -- document projection -------------------------------------------

    def _on_document_change(self) -> None:
        self._call_on_loop(self._project_document)

    def _project_document(self) -> None:
        """Bring the output buffer in line with the output document.

        Within one document epoch only the tail can change (the
        last segment may grow; new segments append), so projection
        redoes just the tail segment onward.  An epoch change
        (snapshot replacement, trimming) rebuilds from the start.
        Colour comes from the segment kinds alone — this view's
        decision, via :func:`_kind_style`.
        """
        document = self._document
        if document is None:
            return
        segments, version, epoch = document.snapshot()
        if version == self._proj_version:
            return
        if epoch != self._proj_epoch or self._proj_seg_count > len(segments):
            start = 0
            text = ""
            ranges: list[tuple[int, int, str]] = []
            prefix_len = 0
        else:
            start = max(0, self._proj_seg_count - 1)
            text = self._output_text[: self._proj_prefix_len]
            ranges = [r for r in self._style_ranges if r[1] <= self._proj_prefix_len]
            prefix_len = self._proj_prefix_len
        for index in range(start, len(segments)):
            segment = segments[index]
            seg_start = len(text)
            text += segment.text
            if index == len(segments) - 1:
                prefix_len = seg_start
            style = _kind_style(segment.kind)
            if style and segment.text:
                entry = (seg_start, seg_start + len(segment.text), style)
                if ranges and ranges[-1][1] == entry[0] and ranges[-1][2] == style:
                    ranges[-1] = (ranges[-1][0], entry[1], style)
                else:
                    ranges.append(entry)
        self._output_text = text
        self._style_ranges = ranges
        self._proj_version = version
        self._proj_epoch = epoch
        self._proj_seg_count = len(segments)
        self._proj_prefix_len = prefix_len if segments else 0
        self._output_buffer.set_document(
            self._Document(text, cursor_position=len(text)),
            bypass_readonly=True,
        )

    def set_spinner(self, label: str | None) -> None:
        """Show the spinner with ``label``, or hide it with None."""
        with self._state_lock:
            if label != self._spinner_label:
                self._spinner_label = label
                self._spinner_started = time.monotonic()
        self._invalidate()

    def set_status(self, text: str, *, busy: bool) -> None:
        """Set the bottom status line (e.g. ``[STATE] BUSY [LLM]``)."""
        with self._state_lock:
            was_busy = self._status_busy
            self._status_text = text
            self._status_busy = bool(busy)
        self._resolve_confirmation_on_idle(was_busy, busy)
        self._invalidate()

    def set_usage(
        self,
        usage: Mapping[str, Any] | None,
        *,
        session_id: str | None = None,
    ) -> None:
        """Accumulate provider-reported token usage for the active session."""
        if usage is None:
            with self._state_lock:
                self._usage_text = ""
                self._usage_compact_text = ""
            self._invalidate()
            return

        clean_session_id = str(session_id or "").strip() or None
        with self._state_lock:
            if (
                clean_session_id is not None
                and clean_session_id != self._usage_session_id
            ):
                self._usage_session_id = clean_session_id
                self._usage_totals = {
                    "input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 0,
                }

            deltas: dict[str, int] = {}
            for source, target in (
                ("input_tokens_delta", "input_tokens"),
                ("cache_read_input_tokens_delta", "cache_read_input_tokens"),
                ("output_tokens_delta", "output_tokens"),
            ):
                value = usage.get(source)
                if type(value) is int and value >= 0:
                    deltas[target] = value
            for key, value in deltas.items():
                self._usage_totals[key] += value

            labels = (
                ("input_tokens", "in"),
                ("cache_read_input_tokens", "cached"),
                ("output_tokens", "out"),
            )
            parts = [
                f"{label} {self._usage_totals[key]:,}"
                for key, label in labels
                if key in deltas or self._usage_totals[key] > 0
            ]
            text = "Session: " + " / ".join(parts) if parts else ""
            compact = (
                f"in {self._usage_totals['input_tokens']:,} / "
                f"c {self._usage_totals['cache_read_input_tokens']:,} / "
                f"out {self._usage_totals['output_tokens']:,}"
                if parts
                else text
            )
            self._usage_text = text
            self._usage_compact_text = compact
        self._invalidate()

    def resync_busy(self, busy: bool) -> None:
        """Re-align the cached busy flag with the core's truth.

        Status updates only reach the view while it is active, so
        a turn that ends while the view is suspended for a
        human_ask leaves the cached flag stale — and submissions
        are gated by it (an idle prompt would offer an interrupt
        confirmation, or a running turn would look idle).  The
        reader calls this on resume with the core's current flag.
        The status text is left alone; the next status render
        refreshes it.
        """
        with self._state_lock:
            was_busy = self._status_busy
            self._status_busy = bool(busy)
        self._resolve_confirmation_on_idle(was_busy, busy)
        self._invalidate()

    def _resolve_confirmation_on_idle(self, was_busy: bool, busy: bool) -> None:
        if was_busy and not busy:
            # The turn ended while an interrupt confirmation was
            # still open: the question is moot, so the message
            # takes the safe side and queues (it dispatches next
            # through the ordinary path).  This runs on a worker
            # thread, so the input buffer is reset on the
            # application thread; until then it stays read-only.
            pending = self._take_confirmation(defer_reset=True)
            if pending is not None:
                self._finish_confirmation(pending, interrupt=False)
                self._call_on_loop(self._reset_input_buffer)

    def set_prompt_text(self, text: str) -> None:
        with self._state_lock:
            self._prompt_text = text
        self._invalidate()

    # -- input ----------------------------------------------------------

    def wait_line(self, *, abort: Callable[[], bool]) -> Any:
        """Return the next submitted line, the EOF sentinel, or None.

        ``abort`` is polled while waiting; when it turns true the wait
        ends with None (the caller decides why: human_ask took stdin,
        shutdown, ...).  Submitted text is returned as ``str``.  A
        line the user chose to interrupt for is returned ahead of
        lines queued earlier.  After a ``str`` return,
        :attr:`last_pending_token` holds the output document's
        pending-user segment for the line when it was queued during
        generation (else None), so the dispatcher can resolve the
        marker at the moment the line is actually sent.
        """
        while True:
            try:
                text, token = self._priority.get_nowait()
                self._last_pending_token = token
                self._last_line_priority = True
                return text
            except queue.Empty:
                pass
            if self._front:
                text, token = self._front.popleft()
                self._last_pending_token = token
                self._last_line_priority = False
                return text
            try:
                text, token = self._submissions.get(timeout=0.05)
                self._last_pending_token = token
                self._last_line_priority = False
                return text
            except queue.Empty:
                if abort():
                    return None
                if not self._running:
                    # The application ended on its own (terminal input
                    # closed, or the renderer raised): report EOF so
                    # the reader exits cleanly instead of polling a
                    # queue no one will ever fill again.
                    return self.eof_sentinel

    def take_priority_line(self) -> str | None:
        """Pop one interrupt-chosen line without waiting, if any.

        The reader calls this before committing a line it already
        holds: a line the user explicitly chose to send next must
        overtake a line that was merely dequeued earlier and is
        being held by the busy-at-submit wait.
        """
        try:
            text, _token = self._priority.get_nowait()
        except queue.Empty:
            return None
        return text

    def requeue_front(self, text: str, token: Any = None) -> None:
        """Return a line the reader already took to the queue front.

        Used when a priority line overtakes the held line: the held
        line keeps its pending token and is read again before any
        ordinary queued line.
        """
        self._front.appendleft((text, token))

    def requeue_priority(self, text: str) -> None:
        """Return an interrupt-chosen line to the priority queue.

        Used when a human_ask takes stdin after the reader took
        the line but before it could dispatch: the user's
        explicit "send this next" choice survives the question
        and is read again ahead of ordinary queued lines.
        """
        self._priority.put((text, None))

    @property
    def eof_sentinel(self) -> object:
        return _EOF

    @property
    def last_pending_token(self) -> Any:
        """The pending-user segment of the line wait_line returned."""
        return self._last_pending_token

    @property
    def last_line_priority(self) -> bool:
        """Whether the line wait_line returned was interrupt-chosen.

        Tracked separately from the pending token: an
        interrupt-chosen line carries no token (it was echoed as
        an ordinary user segment at once), but it is still a
        deliberate choice that must survive a human_ask takeover.
        """
        return self._last_line_priority

    def resolve_pending(self, token: Any) -> None:
        """Drop the queued marker from a pending line being sent."""
        if token is not None and self._document is not None:
            try:
                self._document.resolve_pending_user(token)
            except Exception:
                pass

    def _resolve_open_confirmation_as_queue(self) -> bool:
        """Settle an open interrupt confirmation on its safe side.

        A terminal takeover (a suspension, or a human_ask opening
        its reply mode) preempts the question: the message queues
        and the transcript says so.  Returns True when a
        confirmation was open (the caller then resets the input
        buffer, on whichever thread owns it at that point).
        """
        pending = self._take_confirmation()
        if pending is None:
            return False
        self._finish_confirmation(pending, interrupt=False)
        if self._document is not None:
            try:
                self._document.append(
                    "notice",
                    "\n[INFO] "
                    + _(
                        "The interrupt confirmation was cancelled, "
                        "so the message was queued."
                    )
                    + "\n",
                )
            except Exception:
                pass
        return True

    # -- human_ask reply mode ------------------------------------------

    @property
    def reply_cancelled(self) -> object:
        """The sentinel wait_reply returns when Ctrl+C ends a reply."""
        return _REPLY_CANCELLED

    def _reply_password_active(self) -> bool:
        with self._state_lock:
            return self._reply_label is not None and self._reply_is_password

    def begin_reply(self, label: str, *, is_password: bool = False) -> None:
        """Open reply mode for a human_ask (called by the reader).

        The question already sits in the output document; the
        input row now answers it.  An open interrupt confirmation
        is settled as a queue first, exactly as a suspension would
        settle it.  The buffer surgery runs on the application
        thread: the half-typed draft and the completer are stashed
        (a password must never be completed, and pre-ask typing
        must never become part of the reply), the buffer is
        cleared, and only then is the mode armed — an Enter that
        lands earlier is ignored rather than submitting the draft
        as the answer.
        """
        settled = self._resolve_open_confirmation_as_queue()
        # Nothing stale may survive into this ask: a reply finished
        # after its wait had already aborted belongs to no one.
        while True:
            try:
                self._reply_queue.get_nowait()
            except queue.Empty:
                break
        with self._state_lock:
            already = self._reply_label is not None
            self._reply_label = label
            self._reply_is_password = bool(is_password)
            if not already:
                self._reply_armed = False

        def _arm() -> None:
            if not already:
                try:
                    if settled:
                        # The settled confirmation's text was
                        # queued by the helper but still sits in
                        # the buffer; clear it BEFORE the draft is
                        # stashed, or the restore after the reply
                        # would hand it back as editable input and
                        # Enter would submit it a second time.  The
                        # suspension path clears it the same way.
                        self._input_buffer.reset()
                    self._reply_draft = self._input_buffer.document
                    self._reply_completer = self._input_buffer.completer
                    self._reply_history = self._input_buffer.history
                    self._input_buffer.completer = None
                    # Isolate the reply from the prompt's
                    # (file-backed) history for the whole mode:
                    # nothing typed as a reply — above all a
                    # password — may be written to it by any
                    # binding, and browsing stays off, exactly
                    # like completion.  The reset below restarts
                    # the history load against the throwaway.
                    from prompt_toolkit.history import InMemoryHistory

                    self._input_buffer.history = InMemoryHistory()
                    if is_password:
                        # An Emacs macro recording must never
                        # capture password keystrokes (the macro
                        # lives on the application, so the buffer
                        # reset does not help): stop any recording
                        # in progress — it is discarded, tainted
                        # from here on — and remember the stored
                        # macro, so the restore can drop a macro
                        # completed during the reply.
                        emacs = self._emacs_state()
                        if emacs is not None:
                            self._reply_macro_before = emacs.macro
                            if emacs.is_recording:
                                emacs.reset()
                    self._input_buffer.reset()
                except Exception:
                    pass
                with self._state_lock:
                    self._reply_armed = True
            self._invalidate()

        self._call_on_loop(_arm)

    def end_reply(self) -> None:
        """Close reply mode without an answer (the ask ended).

        The ask was answered or cancelled from another channel
        while the reader waited: the typed text belongs to no one,
        so it is dropped and the stashed draft comes back.  The
        state is cleared by the restore itself, on the application
        thread, so an Enter that lands in between is still treated
        as a reply (and then dropped as stale by the next
        begin_reply) instead of leaking out as a normal line.

        This call waits until the restore has actually run.  The
        reader goes on to open the NEXT ask's reply mode from this
        same thread, and a restore still queued behind it would
        observe the old label, skip arming, and then clear the
        new mode's state when it finally ran — leaving the reader
        blocked in wait_reply while Enter submits normal lines.
        If the view stops first the state no longer matters, so
        the wait ends there too.
        """
        with self._state_lock:
            if self._reply_label is None:
                return
        done = threading.Event()

        def _restore_and_signal() -> None:
            try:
                self._restore_reply_buffer()
            finally:
                done.set()

        self._call_on_loop(_restore_and_signal)
        while self._running and not done.wait(0.05):
            pass

    def wait_reply(self, *, abort: Callable[[], bool]) -> Any:
        """Return the reply line, the EOF sentinel, or None.

        Mirrors :meth:`wait_line`: ``abort`` is polled while
        waiting and ends the wait with None (the caller unwinds
        with :meth:`end_reply`).  Ctrl+C inside the view returns
        :attr:`reply_cancelled`; Ctrl+D returns the EOF sentinel.
        """
        while True:
            try:
                return self._reply_queue.get(timeout=0.05)
            except queue.Empty:
                if abort():
                    return None
                if not self._running:
                    return self.eof_sentinel

    def _emacs_state(self) -> Any:
        """The running application's Emacs state, if it has one."""
        app = self._app
        if app is None:
            return None
        return getattr(app, "emacs_state", None)

    def _restore_reply_buffer(self) -> None:
        """Undo begin_reply's buffer surgery (application thread).

        The reply text is dropped, the stashed draft and completer
        come back.  Also used by suspend(), once its application
        thread has unwound.
        """
        with self._state_lock:
            armed = self._reply_armed
            was_password = self._reply_is_password
            self._reply_label = None
            self._reply_is_password = False
            self._reply_armed = False
            draft = self._reply_draft
            completer = self._reply_completer
            history = self._reply_history
            self._reply_draft = None
            self._reply_completer = None
            self._reply_history = None
        if not armed:
            # The buffer surgery never ran (or a racing restore
            # already undid it): the buffer still holds exactly
            # what the user had typed before the ask, so there is
            # nothing to restore — resetting here would wipe it.
            self._invalidate()
            return
        if was_password:
            # Drop whatever macro state the reply could have
            # tainted: a recording still in progress was started
            # during the reply (the arm stopped any earlier one),
            # and a stored macro whose identity changed was
            # completed during it.  A macro stored before the ask
            # and untouched since is clean and stays.
            emacs = self._emacs_state()
            if emacs is not None:
                try:
                    if emacs.is_recording:
                        emacs.reset()
                    if emacs.macro is not self._reply_macro_before:
                        emacs.macro = []
                except Exception:
                    pass
            self._reply_macro_before = None
        try:
            self._input_buffer.completer = completer
            if history is not None:
                # The real history comes back BEFORE the reset,
                # so the reset's history load repopulates the
                # working lines from it (browsing works again
                # immediately, as if no reply had happened).
                self._input_buffer.history = history
            # reset(), not set_document(): the reply's editing
            # state (above all the undo stack, which still holds
            # the reply text — a password in the clear) must not
            # survive into the normal prompt, where Ctrl+_ would
            # bring it back visibly and Enter could send it.
            self._input_buffer.reset(document=draft)
        except Exception:
            pass
        self._invalidate()

    def _finish_reply(self, item: Any) -> None:
        """End reply mode from a key binding and hand over ``item``.

        Runs on the application thread, so the buffer is restored
        synchronously: keys batched behind the answer start from
        the restored draft, never from the reply text.  The item
        (the reply text, or a cancel/EOF sentinel) is queued only
        after the restore, so the reader never observes the reply
        while the input row is still in reply mode.
        """
        self._restore_reply_buffer()
        self._reply_queue.put(item)

    # -- interrupt confirmation (input during generation) -------------

    def _take_confirmation(self, *, defer_reset: bool = False) -> str | None:
        """Pop the open confirmation's message, if one is open.

        With ``defer_reset``, the input buffer's clearing is still
        owed: ``_reset_pending`` keeps the buffer read-only until
        the reset runs on the application thread, so keys batched
        behind the answer cannot append to the answered message.
        """
        with self._state_lock:
            text = self._confirm_text
            self._confirm_text = None
            if text is not None and defer_reset:
                self._reset_pending = True
            return text

    def _resolve_confirmation(self, *, interrupt: bool) -> None:
        """Answer the open confirmation (from a key binding).

        Runs on the application thread, so the input buffer is
        reset synchronously: keys batched behind the answer (the
        next message typed in the same paste) start from an empty
        buffer, not from the answered message's text.
        """
        text = self._take_confirmation()
        if text is not None:
            self._finish_confirmation(text, interrupt=interrupt)
            self._reset_input_buffer()

    def _finish_confirmation(self, text: str, *, interrupt: bool) -> None:
        """Carry out a decided (or defaulted) confirmation outcome.

        Interrupt: the line is echoed as an ordinary user line, the
        turn interrupt is requested through the ``on_interrupt``
        callback, and the line goes to the priority queue so it is
        the next one dispatched once the turn winds down.  Queue:
        the line joins the ordinary FIFO behind anything already
        waiting, echoed with the pending marker until dispatched.
        """
        with self._state_lock:
            prompt_text = self._prompt_text
        if interrupt:
            if self._document is not None:
                try:
                    self._document.append("user", f"{prompt_text}{text}\n")
                except Exception:
                    pass
            self._priority.put((text, None))
            if self._on_interrupt is not None:
                try:
                    self._on_interrupt()
                except Exception:
                    pass
        else:
            self._queue_line(text)
        self._invalidate()

    def _queue_line(self, text: str) -> None:
        """Queue a line submitted during generation (FIFO order).

        The line is echoed into the document with the pending
        marker; the marker is resolved when the line is dispatched.
        """
        with self._state_lock:
            prompt_text = self._prompt_text
        token = None
        if self._document is not None:
            try:
                token = self._document.append_pending_user(
                    f"{prompt_text}{text}{_(' (queued)')}\n",
                    _(" (queued)"),
                )
            except Exception:
                token = None
        self._submissions.put((text, token))

    def _reset_input_buffer(self) -> None:
        """Clear the input buffer and reopen it for typing.

        Runs on the application thread — directly from a key
        binding, posted for a worker-triggered resolution, or at
        startup when a posted reset never ran.  Until it runs,
        ``_reset_pending`` keeps the buffer read-only.
        """
        try:
            self._input_buffer.reset()
        except Exception:
            pass
        with self._state_lock:
            self._reset_pending = False

    def _confirm_fragments(self) -> list[tuple[str, str]]:
        with self._state_lock:
            active = self._confirm_text is not None
        if not active:
            return [("class:confirm", "")]
        return [
            (
                "class:confirm",
                _(
                    "Interrupt the current response and send this "
                    "message now?  Enter/y: interrupt   n: queue"
                ),
            )
        ]

    # -- internals ------------------------------------------------------

    def _call_on_loop(self, fn: Callable[[], None]) -> None:
        app = self._app
        if app is None:
            fn()
            return
        try:
            loop = app.loop
            if loop is not None:
                loop.call_soon_threadsafe(fn)
                return
        except Exception:
            pass
        fn()

    def _invalidate(self) -> None:
        app = self._app
        if app is not None:
            try:
                app.invalidate()
            except Exception:
                pass

    def _spinner_fragments(self) -> list[tuple[str, str]]:
        with self._state_lock:
            label = self._spinner_label
            started = self._spinner_started
        if label is None:
            return [("class:spinner", "")]
        try:
            from ..runtime.spinner import _frames

            frames = _frames()
        except Exception:
            frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
        frame = frames[int((time.monotonic() - started) / 0.12) % len(frames)]
        lowered = label.lower()
        if lowered.startswith("sub-agent:"):
            style = "class:spinner.subagent"
        elif lowered.startswith("tool:"):
            style = "class:spinner.tool"
        else:
            style = "class:spinner"
        return [(style, f"{frame} {label}")]

    def _status_fragments(self) -> list[tuple[str, str]]:
        with self._state_lock:
            text = self._status_text
            busy = self._status_busy
            usage = self._usage_text
            compact_usage = self._usage_compact_text
        style = "class:status.busy" if busy else "class:status.idle"
        if not usage:
            return [(style, text)]

        try:
            from prompt_toolkit.utils import get_cwidth

            width_fn = get_cwidth
        except Exception:
            width_fn = len
        columns = 80
        app = self._app
        if app is not None:
            try:
                columns = max(1, int(app.output.get_size().columns))
            except Exception:
                pass

        usage_text = usage
        if width_fn(text) + 2 + width_fn(usage_text) > columns:
            usage_text = compact_usage
        if width_fn(text) + 2 + width_fn(usage_text) > columns:
            available = max(0, columns - width_fn(text) - 1)
            usage_text = usage_text[:available]
        padding = max(2, columns - width_fn(text) - width_fn(usage_text))
        if width_fn(text) + padding + width_fn(usage_text) > columns:
            padding = 1
        return [(style, text), (style, " " * padding + usage_text)]

    @staticmethod
    def _trim_rule_label(text: str) -> str:
        text = text.rstrip()
        if text.endswith(">"):
            text = text[:-1].rstrip()
        if len(text) > _PREFIX_MAX_WIDTH:
            text = text[: _PREFIX_MAX_WIDTH - 1] + "…"
        return text

    def _rule_label(self) -> str:
        """The prompt's identifying text, carried by the upper rule.

        The prompt string ("UAGEXE> ", "[BUSY:LLM] > ") loses its
        trailing ">" — what remains names where the user is (the
        working directory at idle), which is all the rule shows.
        The input line itself carries no prompt, just the cursor.
        While a human_ask reply is open, the rule carries the
        ask's prompt ("[REPLY]", "[PASSWORD]", ...) instead, so
        the input row says what it is answering.
        """
        with self._state_lock:
            reply_label = self._reply_label
            text = self._prompt_text
        if reply_label is not None:
            return self._trim_rule_label(reply_label)
        return self._trim_rule_label(text)

    def _upper_rule_fragments(self) -> list[tuple[str, str]]:
        return self._make_rule_fragments(self._rule_label())

    def _lower_rule_fragments(self) -> list[tuple[str, str]]:
        return self._make_rule_fragments("")

    def _make_rule_fragments(self, label: str) -> list[tuple[str, str]]:
        from prompt_toolkit.utils import get_cwidth

        width = 80
        app = self._app
        if app is not None:
            try:
                width = app.output.get_size().columns
            except Exception:
                pass
        if label:
            head = f"── {label} "
            fill = max(0, width - get_cwidth(head))
            return [("class:rule", head + "─" * fill)]
        return [("class:rule", "─" * width)]

    def _make_app(self) -> Any:
        from prompt_toolkit.application import Application, get_app
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import (
            ConditionalContainer,
            Dimension,
            Float,
            FloatContainer,
            HSplit,
            Layout,
            Window,
        )
        from prompt_toolkit.layout.menus import CompletionsMenu
        from prompt_toolkit.layout.controls import (
            BufferControl,
            FormattedTextControl,
        )
        from prompt_toolkit.layout.processors import (
            ConditionalProcessor,
            PasswordProcessor,
        )
        from prompt_toolkit.mouse_events import MouseButton, MouseEventType
        from prompt_toolkit.selection import SelectionType
        from prompt_toolkit.styles import Style

        bindings = KeyBindings()

        def _copy_selection(buffer: Any, clipboard: Any) -> bool:
            selection_state = buffer.selection_state
            if selection_state is None:
                return False
            try:
                data = buffer.copy_selection()
            except Exception:
                return True
            finally:
                # Keep the highlight visible after copying, like a
                # conventional editor.  Ctrl+C can then copy again
                # without turning into the interrupt shortcut.
                buffer.selection_state = selection_state
            try:
                clipboard.set_data(data)
            except Exception:
                pass
            return True

        def _paste_clipboard(buffer: Any, clipboard: Any) -> None:
            if self._confirm_text is not None or self._reset_pending:
                return
            try:
                pasted = _read_system_clipboard()
            except Exception:
                pasted = None
            if pasted is None:
                try:
                    pasted = clipboard.get_data().text
                except Exception:
                    pasted = ""
            pasted = str(pasted).replace("\r\n", "\n").replace("\r", "\n")
            if not pasted:
                return
            if buffer.selection_state is not None:
                buffer.cut_selection()
            buffer.insert_text(pasted)

        @bindings.add("c-v")
        def _paste(event: Any) -> None:
            _paste_clipboard(event.app.current_buffer, event.app.clipboard)

        @bindings.add("enter")
        def _submit(event: Any) -> None:
            if self._reply_label is not None:
                # The input row is answering a human_ask: the line
                # is the reply, never a submission — it is not
                # echoed into the document and never enters the
                # history.  Until the mode is armed the buffer may
                # still hold the pre-ask draft, so an early Enter
                # is ignored rather than submitting the draft as
                # the answer.
                with self._state_lock:
                    armed = self._reply_armed
                if armed:
                    self._finish_reply(event.app.current_buffer.text)
                return
            if self._confirm_text is not None:
                # Enter answers the open confirmation (it means
                # "interrupt"); the filtered binding below normally
                # wins, and this guard keeps the meaning if it does
                # not.
                self._resolve_confirmation(interrupt=True)
                return
            buffer = event.app.current_buffer
            text = buffer.text
            try:
                buffer.append_to_history()
            except Exception:
                pass
            # The busy check and the confirmation installation are
            # one atomic step: if the turn ended in between, the
            # BUSY->IDLE transition would resolve a confirmation
            # that does not exist yet, and the one installed right
            # after would sit at an idle prompt forever — input
            # read-only, the message undispatched.
            with self._state_lock:
                busy = self._status_busy
                confirm = busy and bool(text.strip()) and not text.startswith(":")
                if confirm:
                    # A message submitted during generation first
                    # asks: interrupt the turn for it, or queue it?
                    # The text stays visible in the (now read-only)
                    # input buffer until the question is answered.
                    # Commands skip the question and queue directly.
                    self._confirm_text = text
            if confirm:
                self._invalidate()
                return
            buffer.reset()
            if busy:
                self._queue_line(text)
                return
            self._submissions.put((text, None))
            # The legacy terminal keeps the submitted line in its
            # scrollback; the transcript here is the document, so
            # record the line (with its prompt) or it vanishes.
            if self._document is not None:
                try:
                    self._document.append("user", f"{self._prompt_text}{text}\n")
                except Exception:
                    pass

        @bindings.add("c-j")
        def _newline(event: Any) -> None:
            event.app.current_buffer.insert_text("\n")

        in_reply = Condition(lambda: self._reply_label is not None)

        @bindings.add("c-o", filter=in_reply)
        def _reply_operate_and_get_next(event: Any) -> None:
            # prompt_toolkit's default Ctrl+O (operate-and-get-
            # next) accepts the buffer through validate_and_handle:
            # it appends the text to the history and clears the
            # buffer WITHOUT delivering anything.  In reply mode
            # that would swallow the reply (and, before the history
            # isolation, persist a password to disk), so here it
            # means exactly what Enter means.
            _submit(event)

        @bindings.add("c-c")
        def _ctrl_c(event: Any) -> None:
            if self._reply_label is not None:
                # Ctrl+C cancels the question, not the turn: the
                # reader turns the sentinel into the same
                # KeyboardInterrupt the legacy prompt raises, and
                # the loop's existing handler delivers the
                # cancellation to the waiting tool.
                with self._state_lock:
                    armed = self._reply_armed
                if armed:
                    self._finish_reply(self.reply_cancelled)
                return
            if self._confirm_text is not None:
                # Ctrl+C at the confirmation cancels the question,
                # not the turn: the message queues (the safe side).
                self._resolve_confirmation(interrupt=False)
                return
            # In the ordinary prompt, Ctrl+C copies a selected input
            # range or transcript range.  With no active selection it
            # retains its existing interrupt/stop behavior.
            clipboard = event.app.clipboard
            if _copy_selection(self._input_buffer, clipboard):
                return
            if _copy_selection(self._output_buffer, clipboard):
                return
            if self._on_ctrl_c is not None:
                try:
                    self._on_ctrl_c()
                except Exception:
                    pass

        @bindings.add("f12")
        def _f12(event: Any) -> None:
            # While the view owns the terminal it also owns the
            # interrupt key; the legacy F12 monitor stays out.
            if self._confirm_text is not None:
                # F12 still interrupts the turn; the message whose
                # confirmation was open queues behind it.
                self._resolve_confirmation(interrupt=False)
            if self._on_f12 is not None:
                try:
                    self._on_f12()
                except Exception:
                    pass

        @bindings.add("c-d")
        def _ctrl_d(event: Any) -> None:
            if self._reply_label is not None:
                # EOF at a reply prompt ends the input loop, like
                # the legacy prompt's EOFError — but the view
                # itself stays up; the reader unwinds it.
                if not event.app.current_buffer.text:
                    with self._state_lock:
                        armed = self._reply_armed
                    if armed:
                        self._finish_reply(self.eof_sentinel)
                return
            if not event.app.current_buffer.text:
                self._submissions.put((_EOF, None))
                event.app.exit()

        # Confirmation answers.  These are registered after the
        # plain bindings so they win while a confirmation is open;
        # the guards inside the plain handlers keep the meaning even
        # if one of them is reached first.
        confirming = Condition(lambda: self._confirm_text is not None)

        @bindings.add("y", filter=confirming)
        @bindings.add("Y", filter=confirming)
        @bindings.add("enter", filter=confirming)
        def _confirm_interrupt(event: Any) -> None:
            self._resolve_confirmation(interrupt=True)

        @bindings.add("n", filter=confirming)
        @bindings.add("N", filter=confirming)
        @bindings.add("escape", filter=confirming)
        def _confirm_queue(event: Any) -> None:
            self._resolve_confirmation(interrupt=False)

        @bindings.add("pageup")
        def _page_up(event: Any) -> None:
            self._scroll_output(-1)

        @bindings.add("pagedown")
        def _page_down(event: Any) -> None:
            self._scroll_output(1)

        style = Style.from_dict(
            {
                "rule": "#5f5f5f",
                "confirm": "ansiyellow",
                **_spinner_style(),
                **_status_styles(),
            }
        )

        view = self

        class _OutputControl(BufferControl):
            """Output text with mouse selection and copy.

            The stock BufferControl mouse handler only works on
            the focused control, and this one never takes focus
            (the input keeps it), so selection is handled here
            directly: drag selects, and releasing the button
            copies the selection to the clipboard.  Holding the
            drag at the top or bottom edge auto-scrolls, so a
            selection can extend past what is on screen.
            """

            def _edge_step(self, mouse_event: Any) -> int:
                """-1 at the top edge, +1 at the bottom, else 0.

                The event's position is the document (row, col)
                under the pointer.  A wrapped line spans several
                screen rows, so the row alone cannot tell the
                first or last screen row from the line's other
                segments; the render info's visible_line_to_row_col
                gives each screen row's segment start, and the
                pointer is at an edge only within the first or
                last segment.
                """
                info = getattr(view._output_window, "render_info", None)
                all_rows = getattr(info, "visible_line_to_row_col", None)
                if not all_rows:
                    return 0
                # The mapping also carries segments just outside
                # the viewport (negative keys above, keys past the
                # height below) when the view starts or ends
                # partway through a wrapped line; only the actual
                # screen rows decide the edges.
                height = getattr(info, "window_height", None)
                if not isinstance(height, int) or height <= 0:
                    return 0
                rows = {
                    key: value for key, value in all_rows.items() if 0 <= key < height
                }
                if not rows:
                    return 0
                row = mouse_event.position.y
                col = mouse_event.position.x
                # The mapping's columns are terminal-cell offsets;
                # the event's are character offsets.  Convert
                # before comparing (they differ on wide chars).
                first_key = min(rows)
                first_row, first_cell = rows[first_key]
                first_col = self._cell_to_char_col(first_row, first_cell)
                if row == first_row and col >= first_col:
                    second = rows.get(first_key + 1)
                    if (
                        second is None
                        or second[0] != first_row
                        or col < self._cell_to_char_col(second[0], second[1])
                    ):
                        return -1
                last_row, last_cell = rows[max(rows)]
                if row == last_row and col >= self._cell_to_char_col(
                    last_row, last_cell
                ):
                    return 1
                return 0

            @staticmethod
            def _rendered_width(char: str) -> int:
                """The width the renderer gives one character:
                control characters are drawn as ^X (2 cells),
                everything else follows get_cwidth (which counts
                control characters as 0 and would skew every
                offset past a tab)."""
                from prompt_toolkit.utils import get_cwidth

                code = ord(char)
                if code < 32 or code == 127:
                    return 2
                return get_cwidth(char)

            def _cell_to_char_col(self, row: int, cell_col: int) -> int:
                """Convert a terminal-cell offset within a document
                row to a character offset, by walking the line's
                rendered character widths."""
                if cell_col <= 0:
                    return 0
                total = 0
                for index, char in enumerate(self.buffer.document.lines[row]):
                    if total >= cell_col:
                        return index
                    total += self._rendered_width(char)
                return len(self.buffer.document.lines[row])

            def _cells_to_char_cols(self, row: int, cell_cols: list[int]) -> list[int]:
                """Convert several cell offsets within a row to
                character offsets in one walk over the line."""
                from prompt_toolkit.utils import get_cwidth

                line = self.buffer.document.lines[row]
                converted: list[int] = []
                targets = sorted(cell_cols)
                target_index = 0
                total = 0
                for index, char in enumerate(line):
                    while (
                        target_index < len(targets) and total >= targets[target_index]
                    ):
                        converted.append(index)
                        target_index += 1
                    total += get_cwidth(char)
                while target_index < len(targets):
                    converted.append(len(line))
                    target_index += 1
                return converted

            def _segment_starts(self, row: int) -> list[int]:
                """ALL wrapped segment start columns of a document
                row, in character offsets.  The render map only
                covers the rendered region of a long line, so its
                starts (converted from cell offsets) are completed
                by a walk over the line's text at the terminal
                width; the union keeps the renderer's own break
                points wherever it reported them."""
                info = getattr(view._output_window, "render_info", None)
                mapping = getattr(info, "visible_line_to_row_col", None) or {}
                cells = sorted({c for r, c in mapping.values() if r == row})
                starts = set(self._cells_to_char_cols(row, cells)) if cells else set()
                starts.add(0)
                try:
                    width = int(view._app.output.get_size().columns)
                except Exception:
                    width = 0
                if width > 0:
                    segment = 0
                    for index, char in enumerate(self.buffer.document.lines[row]):
                        char_width = self._rendered_width(char)
                        if segment + char_width > width:
                            starts.add(index)
                            segment = char_width
                        else:
                            segment += char_width
                return sorted(starts)

            def _extend_past_edge(self, step: int) -> bool:
                """Scroll one screen row and step the selection
                endpoint one screen row in the same direction.

                A screen row is one wrapped segment: inside a
                wrapped line the endpoint steps segment by
                segment (the renderer scrolls within the line to
                follow it); at the line's first/last segment it
                steps to the neighbouring line.  False only at
                the document's own beginning or end.
                """
                buffer = self.buffer
                document = buffer.document
                row, col = document.translate_index_to_position(buffer.cursor_position)
                starts = self._segment_starts(row)
                if buffer.selection_state is None:
                    buffer.start_selection(selection_type=SelectionType.CHARACTERS)
                if step < 0:
                    earlier = [s for s in starts if s < col]
                    if earlier:
                        target = document.translate_row_col_to_index(row, max(earlier))
                    elif row == 0:
                        return False
                    else:
                        # Enter the line above at its LAST segment,
                        # not its start: one screen row up.
                        prev = row - 1
                        target = document.translate_row_col_to_index(
                            prev, self._segment_starts(prev)[-1]
                        )
                else:
                    line_end = len(document.lines[row])
                    ends = starts[1:] + [line_end]
                    later = [e for e in ends if e > col]
                    if later:
                        target = document.translate_row_col_to_index(row, min(later))
                    elif row + 1 >= document.line_count:
                        return False
                    else:
                        # Enter the line below at its FIRST
                        # segment's end, not the line's end.
                        nxt = row + 1
                        next_starts = self._segment_starts(nxt)
                        target_col = (
                            next_starts[1]
                            if len(next_starts) > 1
                            else len(document.lines[nxt])
                        )
                        target = document.translate_row_col_to_index(nxt, target_col)
                view._scroll_output_wheel(step)
                buffer.cursor_position = target
                return True

            def _start_edge_scroll(self, step: int) -> None:
                """Keep extending while the drag holds at an edge.

                A stationary pointer sends no mouse events, so the
                extension repeats on a background task (after a
                short initial delay, like key repeat) until it is
                stopped or the document's own edge is reached.
                """
                self._stop_edge_scroll()
                import asyncio

                holder: dict[str, Any] = {}

                async def _repeat() -> None:
                    try:
                        await asyncio.sleep(0.3)
                        while self._extend_past_edge(step):
                            await asyncio.sleep(0.05)
                    except asyncio.CancelledError:
                        pass
                    finally:
                        if getattr(self, "_edge_task", None) is holder.get("task"):
                            self._edge_task = None
                            self._edge_scroll_step = 0

                try:
                    holder["task"] = get_app().create_background_task(_repeat())
                    self._edge_task = holder["task"]
                    self._edge_scroll_step = step
                except Exception:
                    self._edge_task = None
                    self._edge_scroll_step = 0

            def _stop_edge_scroll(self) -> None:
                task = getattr(self, "_edge_task", None)
                self._edge_task = None
                self._edge_scroll_step = 0
                if task is not None:
                    task.cancel()

            def mouse_handler(self, mouse_event: Any) -> Any:
                if mouse_event.event_type in (
                    MouseEventType.SCROLL_UP,
                    MouseEventType.SCROLL_DOWN,
                ):
                    return NotImplemented  # the window scrolls itself
                get_processed_line = getattr(self, "_last_get_processed_line", None)
                if get_processed_line is None:
                    return NotImplemented
                buffer = self.buffer
                processed_line = get_processed_line(mouse_event.position.y)
                xpos = processed_line.display_to_source(mouse_event.position.x)
                index = buffer.document.translate_row_col_to_index(
                    mouse_event.position.y, xpos
                )
                if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                    self._stop_edge_scroll()
                    view._input_buffer.exit_selection()
                    buffer.exit_selection()
                    buffer.cursor_position = index
                elif (
                    mouse_event.event_type == MouseEventType.MOUSE_MOVE
                    and mouse_event.button != MouseButton.NONE
                ):
                    step = self._edge_step(mouse_event)
                    if step and getattr(self, "_edge_scroll_step", 0) == step:
                        # The repeat task is extending for as long
                        # as the drag holds at this edge.
                        return None
                    if step and index == buffer.cursor_position:
                        # The endpoint is pinned at the edge line:
                        # extend once and let the repeat task take
                        # over.  At the document's edge the endpoint
                        # simply stays — falling through to the
                        # mapping below would use the pre-scroll
                        # render and yank the endpoint back.
                        if self._extend_past_edge(step):
                            self._start_edge_scroll(step)
                        return None
                    self._stop_edge_scroll()
                    if (
                        buffer.selection_state is None
                        and abs(buffer.cursor_position - index) > 0
                    ):
                        buffer.start_selection(selection_type=SelectionType.CHARACTERS)
                    buffer.cursor_position = index
                elif mouse_event.event_type == MouseEventType.MOUSE_UP:
                    self._stop_edge_scroll()
                    if buffer.selection_state is not None:
                        try:
                            _copy_selection(buffer, get_app().clipboard)
                        except Exception:
                            pass
                else:
                    return NotImplemented
                return None

        class _InputControl(BufferControl):
            """Input control: the wheel scrolls the output (the
            input itself has nothing to scroll), and releasing a
            drag copies the input's own selection."""

            def mouse_handler(self, mouse_event: Any) -> Any:
                if (
                    mouse_event.button == MouseButton.RIGHT
                    and mouse_event.event_type == MouseEventType.MOUSE_DOWN
                    and self.buffer.selection_state is not None
                ):
                    # A right-click paste should replace the active
                    # selection rather than clearing it on mouse-down.
                    return None
                if (
                    mouse_event.button == MouseButton.RIGHT
                    and mouse_event.event_type == MouseEventType.MOUSE_UP
                ):
                    _paste_clipboard(self.buffer, get_app().clipboard)
                    return None
                if mouse_event.event_type == MouseEventType.SCROLL_UP:
                    view._scroll_output_wheel(-3)
                    return None
                if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
                    view._scroll_output_wheel(3)
                    return None
                if mouse_event.event_type in (
                    MouseEventType.MOUSE_DOWN,
                    MouseEventType.MOUSE_UP,
                ) or (
                    mouse_event.event_type == MouseEventType.MOUSE_MOVE
                    and mouse_event.button != MouseButton.NONE
                ):
                    # A drag that left the output area ends its
                    # edge scroll here, where its events land.
                    view._stop_output_edge_scroll()
                if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                    view._output_buffer.exit_selection()
                result = super().mouse_handler(mouse_event)
                if mouse_event.event_type == MouseEventType.MOUSE_UP:
                    # A password reply is masked on screen; its
                    # selection must not reach the clipboard either.
                    if self.buffer.selection_state is not None and (
                        not view._reply_password_active()
                    ):
                        try:
                            _copy_selection(self.buffer, get_app().clipboard)
                        except Exception:
                            pass
                return result

        class _PassiveControl(FormattedTextControl):
            """A display-only text row (spinner, prompt, status):
            the wheel scrolls the output instead of dying on a
            one-line strip."""

            def mouse_handler(self, mouse_event: Any) -> Any:
                if mouse_event.event_type == MouseEventType.SCROLL_UP:
                    view._scroll_output_wheel(-3)
                    return None
                if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
                    view._scroll_output_wheel(3)
                    return None
                if mouse_event.event_type in (
                    MouseEventType.MOUSE_DOWN,
                    MouseEventType.MOUSE_UP,
                ) or (
                    mouse_event.event_type == MouseEventType.MOUSE_MOVE
                    and mouse_event.button != MouseButton.NONE
                ):
                    # A drag that left the output area ends its
                    # edge scroll here, where its events land.
                    view._stop_output_edge_scroll()
                return super().mouse_handler(mouse_event)

        self._output_control = _OutputControl(
            buffer=self._output_buffer, lexer=self._lexer
        )
        output_window = Window(
            content=self._output_control,
            wrap_lines=True,
        )
        self._output_window = output_window

        layout = Layout(
            FloatContainer(
                content=HSplit(
                    [
                        output_window,
                        Window(
                            content=_PassiveControl(self._spinner_fragments),
                            height=1,
                            style="class:spinner",
                        ),
                        Window(
                            content=_PassiveControl(self._upper_rule_fragments),
                            height=1,
                            style="class:rule",
                        ),
                        # The interrupt confirmation gets its own
                        # line, visible only while it is open, so the
                        # question never has to fight the spinner or
                        # the status line for space.
                        ConditionalContainer(
                            content=Window(
                                content=_PassiveControl(self._confirm_fragments),
                                height=1,
                                style="class:confirm",
                            ),
                            filter=Condition(lambda: self._confirm_text is not None),
                        ),
                        # One input line, no prompt text: the rule
                        # above carries the where-am-I label, and
                        # the blinking cursor marks the input.  A
                        # password reply is masked with the standard
                        # password processor, exactly like the
                        # legacy prompt's is_password.
                        Window(
                            content=_InputControl(
                                buffer=self._input_buffer,
                                input_processors=[
                                    ConditionalProcessor(
                                        PasswordProcessor(),
                                        Condition(
                                            lambda: self._reply_password_active()
                                        ),
                                    )
                                ],
                            ),
                            height=Dimension(min=1, max=1),
                        ),
                        Window(
                            content=_PassiveControl(self._lower_rule_fragments),
                            height=1,
                            style="class:rule",
                        ),
                        Window(
                            content=_PassiveControl(self._status_fragments),
                            height=1,
                        ),
                    ]
                ),
                # Tab fills the input buffer's completion state; the
                # candidates need a renderer or they stay invisible
                # (the legacy PromptSession shows this menu).
                floats=[
                    Float(
                        xcursor=True,
                        ycursor=True,
                        content=CompletionsMenu(max_height=16, scroll_offset=1),
                    )
                ],
            ),
            focused_element=self._input_buffer,
        )

        kwargs: dict[str, Any] = {
            "layout": layout,
            "key_bindings": bindings,
            "full_screen": True,
            "style": style,
            "refresh_interval": 0.12,
            "mouse_support": True,
            "clipboard": _make_clipboard(
                write_guard=lambda: not self._reply_password_active()
            ),
        }
        if self._pt_input is not None:
            kwargs["input"] = self._pt_input
        if self._pt_output is not None:
            kwargs["output"] = self._pt_output
        else:
            try:
                from .prompt_session import _create_prompt_output

                output = _create_prompt_output()
                if output is not None:
                    kwargs["output"] = output
            except Exception:
                pass
        return Application(**kwargs)

    def _scroll_output(self, pages: int) -> None:
        height = 20
        app = self._app
        if app is not None:
            try:
                height = max(5, app.output.get_size().rows - 5)
            except Exception:
                pass
        self._scroll_output_lines(pages * height)

    def _scroll_output_lines(self, delta: int) -> None:
        buffer = self._output_buffer
        text = buffer.text
        if not text:
            return
        lines = text.split("\n")
        # Convert the cursor's byte offset to a line, move by the
        # delta, and convert back; the output window follows the
        # cursor.
        cursor = buffer.cursor_position
        line_no = text[:cursor].count("\n")
        line_no = max(0, min(len(lines) - 1, line_no + delta))
        pos = sum(len(line) + 1 for line in lines[:line_no])
        buffer.set_document(
            self._Document(text, cursor_position=min(pos, len(text))),
            bypass_readonly=True,
        )

    def _stop_output_edge_scroll(self) -> None:
        """Cancel the output's drag edge-scroll repeat, if any.

        Mouse events are dispatched per control, so a drag that
        leaves the output area reports its move/release to the
        row under the pointer instead; those controls call this
        so the repeat does not run on after the drag has left.
        """
        control = self._output_control
        if control is not None:
            control._stop_edge_scroll()

    def _scroll_output_wheel(self, lines: int) -> None:
        """Scroll the output window by a few lines (mouse wheel).

        The renderer persistently honours the window's own scroll
        offset — moving the buffer cursor (the PageUp path) only
        scrolls once the cursor leaves the visible area — so the
        wheel drives the window's scroll directly, with the
        public offset attribute as a fallback.
        """
        window = self._output_window
        if window is None:
            return
        step = getattr(window, "_scroll_up" if lines < 0 else "_scroll_down", None)
        if step is None:
            try:
                info = window.render_info
                if info is None:
                    return
                max_scroll = max(0, info.content_height - info.window_height)
                window.vertical_scroll = max(
                    0, min(max_scroll, window.vertical_scroll + lines)
                )
            except Exception:
                return
        else:
            for _ in range(abs(lines)):
                try:
                    step()
                except Exception:
                    return
        self._invalidate()
