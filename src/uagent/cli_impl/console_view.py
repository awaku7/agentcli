"""Full-screen console view for the interactive CLI (single-writer 2b).

The view is the terminal renderer decided for stage 2b: a scrolling
output area above a fixed bottom region — spinner line, rule, the
3-line input area, rule, and the status line on the very bottom line,
in the style of Claude Code's CLI.  The output area is a projection
of the shared output document (``runtime.display_channel``): the
view subscribes to the document and re-projects its tail as new
segments arrive, colouring each segment by its kind — colour is
this renderer's decision, and the document itself holds none.  The
status/spinner setters mirror ``core.set_status`` state, and
submitted input lines are handed to ``stdin_loop`` through a queue
so every existing post-processing path (commands, human_ask
routing, chat-mode forwarding) is unchanged.

The view is a replaceable renderer: while it is suspended (a human_ask
reply or password prompt owns stdin through the legacy paths) or not
started, :func:`active_view` returns None and every producer falls
back to the legacy terminal writers.

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
"""

from __future__ import annotations

import io
import queue
import sys
import threading
import time
from typing import Any, Callable


from ..env_utils import env_get

_EOF = object()
_PREFIX_WIDTH = 24

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
        pt_input: Any = None,
        pt_output: Any = None,
        document: Any = None,
    ) -> None:
        from prompt_toolkit.buffer import Buffer
        from prompt_toolkit.document import Document

        self._Document = Document
        self._output_buffer = Buffer(read_only=True)
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
        self._input_buffer = Buffer(
            completer=completer,
            history=history,
            multiline=True,
            complete_while_typing=False,
        )
        self._submissions: queue.Queue[Any] = queue.Queue()
        self._on_ctrl_c = on_ctrl_c
        self._on_f12 = on_f12
        self._pt_input = pt_input
        self._pt_output = pt_output
        self._prompt_text = ""
        self._spinner_label: str | None = None
        self._spinner_started = time.monotonic()
        self._status_text = ""
        self._status_busy = False
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
        with self._state_lock:
            if self._thread is thread:
                self._thread = None
            if self._app is app:
                self._app = None

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
            if sys.stdout is self._proxy_stdout and self._orig_stdout is not None:
                sys.stdout = self._orig_stdout
            if sys.stderr is self._proxy_stderr and self._orig_stderr is not None:
                sys.stderr = self._orig_stderr
            self._proxy_stdout = None
            self._proxy_stderr = None

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
            self._status_text = text
            self._status_busy = busy
        self._invalidate()

    def set_prompt_text(self, text: str) -> None:
        with self._state_lock:
            self._prompt_text = text
        self._invalidate()

    # -- input ----------------------------------------------------------

    def wait_line(self, *, abort: Callable[[], bool]) -> Any:
        """Return the next submitted line, the EOF sentinel, or None.

        ``abort`` is polled while waiting; when it turns true the wait
        ends with None (the caller decides why: human_ask took stdin,
        shutdown, ...).  Submitted text is returned as ``str``.
        """
        while True:
            try:
                item = self._submissions.get(timeout=0.05)
                return item
            except queue.Empty:
                if abort():
                    return None

    @property
    def eof_sentinel(self) -> object:
        return _EOF

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
        style = "class:status.busy" if busy else "class:status.idle"
        return [(style, text)]

    def _prompt_fragments(self) -> list[tuple[str, str]]:
        with self._state_lock:
            text = self._prompt_text
        if len(text) > _PREFIX_WIDTH:
            text = text[: _PREFIX_WIDTH - 1] + "…"
        return [("class:prompt", text.ljust(_PREFIX_WIDTH))]

    def _make_app(self) -> Any:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import (
            Dimension,
            HSplit,
            Layout,
            VSplit,
            Window,
        )
        from prompt_toolkit.layout.controls import (
            BufferControl,
            FormattedTextControl,
        )
        from prompt_toolkit.styles import Style

        bindings = KeyBindings()

        @bindings.add("enter")
        def _submit(event: Any) -> None:
            buffer = event.app.current_buffer
            text = buffer.text
            try:
                buffer.append_to_history()
            except Exception:
                pass
            buffer.reset()
            self._submissions.put(text)
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

        @bindings.add("c-c")
        def _ctrl_c(event: Any) -> None:
            if self._on_ctrl_c is not None:
                try:
                    self._on_ctrl_c()
                except Exception:
                    pass

        @bindings.add("f12")
        def _f12(event: Any) -> None:
            # While the view owns the terminal it also owns the
            # interrupt key; the legacy F12 monitor stays out.
            if self._on_f12 is not None:
                try:
                    self._on_f12()
                except Exception:
                    pass

        @bindings.add("c-d")
        def _ctrl_d(event: Any) -> None:
            if not event.app.current_buffer.text:
                self._submissions.put(_EOF)
                event.app.exit()

        @bindings.add("pageup")
        def _page_up(event: Any) -> None:
            self._scroll_output(-1)

        @bindings.add("pagedown")
        def _page_down(event: Any) -> None:
            self._scroll_output(1)

        style = Style.from_dict(
            {
                "rule": "#5f5f5f",
                "prompt": "",
                **_spinner_style(),
                **_status_styles(),
            }
        )

        layout = Layout(
            HSplit(
                [
                    Window(
                        content=BufferControl(
                            buffer=self._output_buffer, lexer=self._lexer
                        ),
                        wrap_lines=True,
                    ),
                    Window(
                        content=FormattedTextControl(self._spinner_fragments),
                        height=1,
                        style="class:spinner",
                    ),
                    Window(char="─", height=1, style="class:rule"),
                    VSplit(
                        [
                            Window(
                                content=FormattedTextControl(self._prompt_fragments),
                                width=_PREFIX_WIDTH,
                                height=Dimension(min=3, max=3),
                            ),
                            Window(
                                content=BufferControl(buffer=self._input_buffer),
                                height=Dimension(min=3, max=3),
                            ),
                        ]
                    ),
                    Window(char="─", height=1, style="class:rule"),
                    Window(
                        content=FormattedTextControl(self._status_fragments),
                        height=1,
                    ),
                ]
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
        buffer = self._output_buffer
        text = buffer.text
        if not text:
            return
        lines = text.split("\n")
        height = 20
        app = self._app
        if app is not None:
            try:
                height = max(5, app.output.get_size().rows - 7)
            except Exception:
                pass
        # Convert the cursor's byte offset to a line, move by pages,
        # and convert back; the output window follows the cursor.
        cursor = buffer.cursor_position
        line_no = text[:cursor].count("\n")
        line_no = max(0, min(len(lines) - 1, line_no + pages * height))
        pos = sum(len(line) + 1 for line in lines[:line_no])
        buffer.set_document(
            self._Document(text, cursor_position=min(pos, len(text))),
            bypass_readonly=True,
        )
