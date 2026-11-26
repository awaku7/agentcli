"""Shared display channel for the interactive CLI terminal.

First step of the CLI single-writer refactor (see
``docs/plans/CLI_SINGLE_WRITER_REFACTOR.md``): background producers post
typed display events instead of writing to the terminal themselves, and a
single pump thread renders them.  The producers migrated so far are the
notice paths: BitChat incoming messages (previously a private display
worker thread in ``tools/pybitchat_shared.py``) and the Nostr tool's
relay notices (previously a bare ``print()`` from listener threads) now
post here.  Nostr remote-control notifications (``nostr_remote_runtime``)
render through this module's shared renderer synchronously, because that
path renders against a caller-supplied core object; it switches to
posting when the stage-2 UI owner exists.

Queue policies (decided 2026-11-25):

- Stream deltas: unbounded FIFO.  A delta must never be dropped; the
  volume is bounded by the generation itself.  (Producers arrive with a
  later stage; the channel support is here from the start.)
- Notices: bounded FIFO (``NOTICE_LIMIT``).  When full, the oldest
  notice is dropped and counted in ``DisplayChannel.dropped_notices``.
- Status redraws: latest-only.  A pending redraw is replaced by the next
  request; the rendered status reflects the newest state anyway.

The two notice renderers below preserve the insertion behaviour each
surface had before the move: ``wait_for_stream`` notices (BitChat, Nostr
tool) wait out an open stream line before inserting, while immediate
notices (Nostr remote control) stop/restore the spinner around the
insertion exactly as the previous direct implementation did.

Stage 2a adds the stream relay: while a CLI round runs on its worker
thread, ``bind_stream_relay`` is bound in that thread's context and
``core.print_stream_delta`` / ``core.print_reasoning_delta`` post
``StreamDelta`` events here instead of printing; the pump renders them
in order.  The channel counts unrendered stream deltas so the worker
can wait for the drain before the turn is considered finished (the
caller's own post-turn output must not overtake the stream tail).

Stage 2b adds the output document: every piece of output the pump
renders — and, while the full-screen console view runs, every piece
captured from the process streams — is recorded in the channel's
``OutputDocument`` as a segment tagged with the kind of content it is
(``answer`` / ``reasoning`` / ``notice`` / ``output`` / ``debug``).
The document is renderer-independent and holds no colour: how a kind
is coloured is each renderer's own decision.  The console view
renders the document; the legacy terminal path renders the events
directly, exactly as before.
"""

from __future__ import annotations

import collections
import re
import threading
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterator

NOTICE_LIMIT = 200

# Grace period for wait_for_stream notices: after a reasoning stream
# closes, give ordinary streamed answer text this long to finish before
# inserting the notice anyway.  Matches the previous BitChat display
# worker's _DISPLAY_WAIT_STREAM_SEC.
STREAM_GRACE_SEC = 2.0


@dataclass(frozen=True)
class StreamDelta:
    """One piece of streamed model output."""

    text: str
    source: str = ""
    turn: int = 0
    # "answer" for assistant text, "reasoning" for reasoning output;
    # the pump renders each through its matching core printer.
    kind: str = "answer"


@dataclass(frozen=True)
class Notice:
    """A one-shot notification line from a background producer."""

    text: str
    source: str
    wait_for_stream: bool = False


@dataclass(frozen=True)
class StatusRedraw:
    """A request to redraw the status line; only the latest is kept."""

    reason: str = ""


DisplayEvent = StreamDelta | Notice | StatusRedraw

# ---------------------------------------------------------------------------
# Output document (stage 2b)
# ---------------------------------------------------------------------------

#: The kinds of content a document segment can hold.  Kinds name what
#: the content IS, never how it was captured or how it is coloured.
SEGMENT_KINDS = (
    "answer",
    "reasoning",
    "notice",
    "tool",
    "user",
    "output",
    "debug",
)

_MAX_DOCUMENT_CHARS = 200_000

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.")
_INCOMPLETE_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-9;?]*|\][^\x07\x1b]*)?$")

# The Inception host renderer redraws a diffusion snapshot in place:
# CR, optional cursor-up, one ESC[2K per previous line (ESC[1B CR
# between lines), optional cursor-up + CR, then the new snapshot.
_SNAPSHOT_PREFIX_RE = re.compile(
    r"^\r(?:\x1b\[\d+A)?((?:\x1b\[2K(?:\x1b\[1B\r)?)+)(?:\x1b\[\d+A\r)?"
)


def split_snapshot_prefix(text: str) -> tuple[int, str] | None:
    """Split an in-place snapshot redraw into (previous lines, payload).

    Returns None when ``text`` does not start with the snapshot
    redraw prefix emitted by the Inception stream host.
    """
    match = _SNAPSHOT_PREFIX_RE.match(text)
    if match is None:
        return None
    return match.group(1).count("\x1b[2K"), text[match.end() :]


@dataclass(frozen=True)
class Segment:
    """One typed piece of the output document."""

    kind: str
    text: str


class OutputDocument:
    """The session's output as typed segments, in arrival order.

    Every producer's output gathers here exactly once, tagged with
    its kind.  The document holds plain text only — never colour
    codes: UAG's own coloured output is classified into kinds at its
    source, and any stray escape sequences in captured text are
    removed on the way in (the text itself is kept).  How a kind is
    coloured is each renderer's decision.

    ``version`` bumps on every change; ``epoch`` bumps when text a
    renderer may already have shown changes (snapshot replacement,
    trimming), telling renderers to rebuild instead of appending.
    """

    def __init__(self, max_chars: int = _MAX_DOCUMENT_CHARS) -> None:
        self._lock = threading.Lock()
        self._segments: list[Segment] = []
        self._total = 0
        self._version = 0
        self._epoch = 0
        self._max_chars = max_chars
        self._pending_escape = ""
        self._subscribers: list[Callable[[], None]] = []

    # -- reading --------------------------------------------------------

    def snapshot(self) -> tuple[tuple[Segment, ...], int, int]:
        """(segments, version, epoch) as one consistent view."""
        with self._lock:
            return tuple(self._segments), self._version, self._epoch

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def subscribe(self, fn: Callable[[], None]) -> None:
        """Call ``fn`` after every change (never under the lock)."""
        with self._lock:
            if fn not in self._subscribers:
                self._subscribers.append(fn)

    # -- writing --------------------------------------------------------

    def append(self, kind: str, text: str) -> None:
        """Append ``text`` as a segment of ``kind``.

        Contiguous segments of the same kind merge.  Escape sequences
        are removed, CRLF becomes LF, and a line redrawn with a lone
        CR keeps only its final form.
        """
        if not text:
            return
        with self._lock:
            text = self._pending_escape + text
            self._pending_escape = ""
            hold = _INCOMPLETE_ESCAPE_RE.search(text)
            if hold is not None and hold.start() > 0:
                self._pending_escape = hold.group(0)
                text = text[: hold.start()]
            text = _ANSI_RE.sub("", text)
            # A redraw of the current line arriving as its own piece
            # (progress output flushed per update) starts with a lone
            # CR; the document's current last line goes away first.
            redraw = text.startswith("\r") and not text.startswith("\r\n")
            if redraw:
                text = text[1:]
            text = self._normalize_lines(text)
            if not text:
                return
            if redraw:
                self._truncate_last_line_locked()
            if self._segments and self._segments[-1].kind == kind:
                last = self._segments[-1]
                self._segments[-1] = Segment(kind, last.text + text)
            else:
                self._segments.append(Segment(kind, text))
            self._total += len(text)
            self._version += 1
            self._trim_locked()
            subscribers = list(self._subscribers)
        for fn in subscribers:
            try:
                fn()
            except Exception:
                pass

    def replace_last_lines(
        self, count: int, text: str, *, kind: str = "answer"
    ) -> None:
        """Replace the last ``count`` lines with ``text``.

        The document-side equivalent of the terminal's in-place
        snapshot redraw (see :func:`split_snapshot_prefix`).
        """
        if count > 0:
            with self._lock:
                full = "".join(segment.text for segment in self._segments)
                lines = full.split("\n")
                keep = lines[: max(0, len(lines) - count)]
                kept_len = len("\n".join(keep)) + (1 if keep else 0)
                self._truncate_to_locked(kept_len)
                self._epoch += 1
        # Reuse append for the payload (normalization + notify).
        self.append(kind, text)

    # -- internals ------------------------------------------------------

    @staticmethod
    def _normalize_lines(text: str) -> str:
        text = text.replace("\r\n", "\n")
        if "\r" not in text:
            return text
        parts = text.split("\n")
        for index, part in enumerate(parts):
            if "\r" in part:
                parts[index] = part.rsplit("\r", 1)[-1]
        return "\n".join(parts)

    def _truncate_to_locked(self, length: int) -> None:
        """Drop everything at or after ``length`` characters."""
        remaining = length
        kept: list[Segment] = []
        for segment in self._segments:
            if remaining <= 0:
                break
            if len(segment.text) <= remaining:
                kept.append(segment)
                remaining -= len(segment.text)
            else:
                kept.append(Segment(segment.kind, segment.text[:remaining]))
                remaining = 0
        self._segments = kept
        self._total = length

    def _truncate_last_line_locked(self) -> None:
        full = "".join(segment.text for segment in self._segments)
        start = full.rfind("\n") + 1
        if start < len(full):
            self._truncate_to_locked(start)
            self._epoch += 1

    def _trim_locked(self) -> None:
        if self._total <= self._max_chars:
            return
        full = "".join(segment.text for segment in self._segments)
        cut = len(full) - self._max_chars
        newline = full.find("\n", cut)
        drop = newline + 1 if newline >= 0 else len(full)
        # Rebuild from the surviving suffix, preserving kinds: walk
        # the segments and clip the one the drop point falls in.
        remaining_drop = drop
        segments: list[Segment] = []
        for segment in self._segments:
            if remaining_drop >= len(segment.text):
                remaining_drop -= len(segment.text)
                continue
            if remaining_drop:
                segment = Segment(segment.kind, segment.text[remaining_drop:])
                remaining_drop = 0
            segments.append(segment)
        self._segments = segments
        self._total = len(full) - drop
        self._epoch += 1


class DisplayChannel:
    """Thread-safe display-event channel with per-class queue policies."""

    def __init__(self, notice_limit: int = NOTICE_LIMIT) -> None:
        self._cond = threading.Condition()
        self._stream: collections.deque[StreamDelta] = collections.deque()
        self._notices: collections.deque[Notice] = collections.deque()
        self._notice_limit = max(1, int(notice_limit))
        self._status: StatusRedraw | None = None
        self._stream_pending = 0
        self.dropped_notices = 0
        # The output document this channel's rendered events gather
        # into (see OutputDocument).  The process-wide channel's
        # document is the session's document.
        self.document = OutputDocument()

    def post_stream(self, event: StreamDelta) -> None:
        with self._cond:
            self._stream.append(event)
            self._stream_pending += 1
            self._cond.notify()

    def note_stream_rendered(self) -> None:
        """Mark one taken stream delta as rendered (pump side)."""
        with self._cond:
            if self._stream_pending > 0:
                self._stream_pending -= 1
            self._cond.notify_all()

    def take_stream_nowait(self) -> StreamDelta | None:
        """Pop one pending stream delta without waiting, or None."""
        with self._cond:
            if self._stream:
                return self._stream.popleft()
            return None

    def wait_for_stream_drain(self, timeout: float | None = None) -> bool:
        """Wait until every posted stream delta has been rendered.

        Returns False on timeout.  Only meaningful while a single
        producer turn is relaying; other producers' deltas count too,
        which can only make the wait longer, never shorter.
        """
        with self._cond:
            deadline = None if timeout is None else time.monotonic() + timeout
            while self._stream_pending > 0:
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                else:
                    self._cond.wait()
            return True

    def post_notice(self, event: Notice) -> None:
        with self._cond:
            while len(self._notices) >= self._notice_limit:
                self._notices.popleft()
                self.dropped_notices += 1
            self._notices.append(event)
            self._cond.notify()

    def post_status(self, event: StatusRedraw) -> None:
        with self._cond:
            self._status = event
            self._cond.notify()

    def take(self, timeout: float | None = None) -> DisplayEvent | None:
        """Return the next event for the pump, or None on timeout.

        Pending stream deltas drain first (FIFO), then notices (FIFO),
        then the latest status redraw.
        """
        with self._cond:
            deadline = None if timeout is None else time.monotonic() + timeout
            while True:
                if self._stream:
                    return self._stream.popleft()
                if self._notices:
                    return self._notices.popleft()
                if self._status is not None:
                    event, self._status = self._status, None
                    return event
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    self._cond.wait(remaining)
                else:
                    self._cond.wait()


# ---------------------------------------------------------------------------
# Notice rendering (ported from the previous per-surface implementations)
# ---------------------------------------------------------------------------


def _render_notice_after_stream(
    core: Any, text: str, *, stream_drain: Any = None
) -> None:
    """Insert a notice without splitting an open stream (BitChat style).

    Never interrupts a reasoning stream; gives ordinary streamed answer
    text a short grace period to finish before inserting anyway.

    Lock order: the insertion stays atomic under ``print_lock`` (the
    previous BitChat worker's guarantee, so a foreground delta cannot
    land between the line close and the notice), but nothing called
    under that lock may stop the spinner — ``spinner.stop()`` holds the
    spinner lifecycle lock while waiting for ``print_lock``, so a
    spinner-stopping writer under ``print_lock`` deadlocks against it.
    The spinner is therefore stopped before the lock, and the writes
    use ``print_stream_delta_locked``, which never touches the spinner.
    A spinner that was active before the notice is restored afterwards
    under the same rule as ``_render_notice_now``.

    ``stream_drain`` (pump only): the pump is the thread that renders
    the stream this function waits on, so waiting without draining
    would stall the stream behind the notice.  When given, each wait
    iteration first renders one queued stream delta, which is what
    advances the flags being waited on.
    """
    _wait_for_stream_line(core, stream_drain=stream_drain)
    # Stop the spinner before acquiring print_lock (see the lock-order
    # note above), remembering whether it was active so it can be
    # restored afterwards.  Best-effort: a spinner failure must not
    # lose the notice.
    was_spinning = False
    stream_was_open = bool(
        getattr(core, "_stream_line_open", False)
        or getattr(core, "_reasoning_stream_open", False)
    )
    try:
        from . import spinner

        # Do not resume a spinner that had already stopped for streaming.
        was_spinning = spinner.is_running()
        spinner.stop_quietly()
    except Exception:
        pass
    try:
        with core.print_lock:
            # When a prompt_toolkit prompt owns the input line, print
            # through the shared helper instead: it hands the text to
            # the prompt's own event loop, which erases the prompt,
            # prints above it and redraws with the edit buffer intact.
            printed_above = False
            try:
                from ..cli_impl.prompt_session import (
                    print_text_above_toolkit_prompt,
                )

                printed_above = print_text_above_toolkit_prompt(core, text)
            except Exception:
                printed_above = False
            if not printed_above:
                if getattr(core, "_stream_line_open", False):
                    core.print_stream_delta_locked(chr(10))
                if getattr(core, "_prompt_line_open", False):
                    # Close the prompt line first so the notice does
                    # not land on the same line as the prompt text.
                    core.print_stream_delta_locked(chr(10))
                    core._prompt_line_open = False
                    try:
                        core.prompt_needs_redraw = True
                    except Exception:
                        pass
                core.print_stream_delta_locked(text + chr(10))
    except Exception:
        try:
            print(text, flush=True)
        except Exception:
            pass
    finally:
        # Restore the progress indicator only if it was active before
        # this notice and the foreground is still waiting for work
        # (same rule as _render_notice_now).  Outside print_lock:
        # spinner.start() must never run under it.
        if (
            was_spinning
            and not stream_was_open
            and getattr(core, "status_busy", False)
            and not getattr(core, "_prompt_line_open", False)
        ):
            try:
                from . import spinner

                spinner.start()
            except Exception:
                pass


def _render_notice_now(core: Any, text: str) -> None:
    """Insert a notice immediately (Nostr remote-control style).

    Stops the spinner before printing and restores it afterwards if it
    was active and the foreground is still busy.
    """
    was_spinning = False
    stream_was_open = False
    try:
        from . import spinner

        # Do not resume a spinner that had already stopped for streaming.
        was_spinning = spinner.is_running()
        stream_was_open = bool(
            getattr(core, "_stream_line_open", False)
            or getattr(core, "_reasoning_stream_open", False)
        )
        # Stop before taking print_lock: spinner.stop() acquires that lock.
        spinner.stop_quietly()
        lock = getattr(core, "print_lock", None)
        with lock if lock is not None else nullcontext():
            toolkit_prompt = bool(getattr(core, "_cli_prompt_toolkit_active", False))
            above_prompt = False
            if toolkit_prompt:
                # The toolkit prompt is not wrapped in patch_stdout, so a
                # bare print would land inside the line being edited.  Let
                # the prompt application print it above itself and redraw;
                # only fall back to a direct print if it refuses.
                from ..cli_impl.prompt_session import (
                    print_text_above_toolkit_prompt,
                )

                above_prompt = print_text_above_toolkit_prompt(core, text)
            if not above_prompt:
                if not toolkit_prompt:
                    if getattr(core, "_stream_line_open", False) or getattr(
                        core, "_prompt_line_open", False
                    ):
                        print(flush=True)
                    core._stream_line_open = False
                    core._reasoning_stream_open = False
                    core._prompt_line_open = False
                print(text, flush=True)
                if not toolkit_prompt:
                    core.prompt_needs_redraw = True
    except (OSError, UnicodeError):
        pass
    finally:
        # Restore the progress indicator only if it was active before
        # this notification and the foreground is still waiting for work.
        if (
            was_spinning
            and not stream_was_open
            and getattr(core, "status_busy", False)
            and not getattr(core, "_prompt_line_open", False)
        ):
            try:
                from . import spinner

                spinner.start()
            except Exception:
                pass


def _wait_for_stream_line(core: Any, *, stream_drain: Any = None) -> None:
    """Wait for the stream's current line to close before a notice.

    Reasoning deltas are written without a trailing newline, so wait
    for the reasoning stream to close completely; ordinary streamed
    answer text gets a short grace period before the notice inserts
    anyway.  ``stream_drain`` is the pump's callback that renders one
    queued stream delta per call — the pump is the thread that renders
    the stream being waited on, so waiting without draining would
    stall the stream behind the notice.
    """
    deadline = time.time() + STREAM_GRACE_SEC
    while getattr(core, "_reasoning_stream_open", False):
        if stream_drain is not None and stream_drain():
            continue
        time.sleep(0.02)
    while getattr(core, "_stream_line_open", False) and time.time() < deadline:
        if stream_drain is not None and stream_drain():
            continue
        time.sleep(0.02)


def render_notice(
    core: Any,
    notice: Notice,
    *,
    stream_drain: Any = None,
    document: OutputDocument | None = None,
) -> None:
    doc = document or default_channel().document
    text = notice.text if notice.text.endswith("\n") else notice.text + "\n"
    if _active_console_view() is not None:
        # The view renders the document; the notice only has to land
        # in it — but at a line boundary, with the same stream-wait
        # discipline as the legacy insertion.  Appending immediately
        # would split the line an answer is still writing, gluing the
        # notice into the middle of that line when projected.
        if notice.wait_for_stream:
            _wait_for_stream_line(core, stream_drain=stream_drain)
        segments, _version, _epoch = doc.snapshot()
        if segments and not segments[-1].text.endswith("\n"):
            # Close the open line as a continuation of its own
            # segment, like the legacy insertion's bare newline.
            doc.append(segments[-1].kind, "\n")
        doc.append("notice", text)
        return
    # Every notice gathers into the output document; the channel's
    # take order (stream before notices) already keeps a notice
    # behind the stream deltas queued ahead of it.
    doc.append("notice", text)
    if notice.wait_for_stream:
        _render_notice_after_stream(core, notice.text, stream_drain=stream_drain)
    else:
        _render_notice_now(core, notice.text)


# ---------------------------------------------------------------------------
# Process-wide channel and pump thread
# ---------------------------------------------------------------------------

_default_channel = DisplayChannel()
_pump_lock = threading.Lock()
_pump_thread: threading.Thread | None = None


def default_channel() -> DisplayChannel:
    return _default_channel


def default_document() -> OutputDocument:
    """The session's output document (the default channel's)."""
    return _default_channel.document


def post_segment(kind: str, text: str) -> None:
    """Append output that bypasses the event queues to the document.

    For producers whose output is gathered only while the console
    view captures it (process-stream prints, the spinner's done
    line, text printed above the legacy prompt): they all land in
    the one document, under their content kind.
    """
    _default_channel.document.append(kind, text)


def _active_console_view() -> Any:
    """The full-screen console view rendering the terminal, if any."""
    try:
        from ..cli_impl.console_view import active_view

        return active_view()
    except Exception:
        return None


def _render_stream_event(
    core: Any, channel: DisplayChannel, event: StreamDelta
) -> None:
    """Record one stream delta in the document; render it if legacy.

    The document append and the core line-state bookkeeping are the
    same in both modes, so the document reads identically whichever
    renderer shows it.  With the console view active the view
    renders the document and the legacy printers stay silent;
    otherwise the printers render (and re-derive the same flags).
    """
    document = channel.document
    try:
        view_active = _active_console_view() is not None
        if event.kind == "reasoning":
            document.append("reasoning", event.text)
            open_ = not event.text.endswith("\n")
            core._stream_line_open = open_
            core._reasoning_stream_open = open_
            if not view_active:
                core.print_reasoning_delta(event.text)
            return
        snapshot = split_snapshot_prefix(event.text)
        if snapshot is not None:
            # In-place snapshot redraw (Inception diffusion): the
            # document replaces the previous snapshot's lines; the
            # legacy terminal redraws via the raw prefix text.
            count, payload = snapshot
            core._reasoning_stream_open = False
            document.replace_last_lines(count, payload, kind="answer")
            core._stream_line_open = not payload.endswith("\n")
            if not view_active:
                core.print_stream_delta(event.text)
            return
        if getattr(core, "_reasoning_stream_open", False):
            if event.text != "\n":
                document.append("answer", "\n")
                if not view_active:
                    core.print_stream_delta("\n")
            core._reasoning_stream_open = False
        document.append("answer", event.text)
        core._stream_line_open = not event.text.endswith("\n")
        if not view_active:
            core.print_stream_delta(event.text)
    finally:
        channel.note_stream_rendered()


def _pump_loop(channel: DisplayChannel) -> None:
    while True:
        event = channel.take()
        if event is None:
            continue
        try:
            from .. import core as _core
        except Exception:
            if isinstance(event, StreamDelta):
                channel.note_stream_rendered()
            continue
        try:
            if isinstance(event, Notice):

                def _drain_one() -> bool:
                    pending = channel.take_stream_nowait()
                    if pending is None:
                        return False
                    _render_stream_event(_core, channel, pending)
                    return True

                render_notice(_core, event, stream_drain=_drain_one)
            elif isinstance(event, StatusRedraw):
                _core.print_status_line()
            elif isinstance(event, StreamDelta):
                _render_stream_event(_core, channel, event)
        except Exception:
            continue


def ensure_pump() -> None:
    """Start the render pump thread if it is not already running."""
    global _pump_thread
    with _pump_lock:
        if _pump_thread is not None and _pump_thread.is_alive():
            return
        _pump_thread = threading.Thread(
            target=_pump_loop,
            args=(_default_channel,),
            name="uagent-display",
            daemon=True,
        )
        _pump_thread.start()


def post_notice(text: str, *, source: str, wait_for_stream: bool = False) -> None:
    """Post a notice to the shared display channel and start the pump."""
    _default_channel.post_notice(
        Notice(text=text, source=source, wait_for_stream=wait_for_stream)
    )
    ensure_pump()


# ---------------------------------------------------------------------------
# Stream relay binding (stage 2a)
# ---------------------------------------------------------------------------

_STREAM_RELAY: ContextVar[DisplayChannel | None] = ContextVar(
    "uagent_stream_relay", default=None
)


def stream_relay() -> DisplayChannel | None:
    """The channel stream output is relayed to in this context, if any."""
    return _STREAM_RELAY.get()


@contextmanager
def bind_stream_relay(channel: DisplayChannel) -> Iterator[None]:
    """Relay this context's stream output to ``channel``.

    Bound on the CLI round worker thread; provider call threads inherit
    it through their context copies.  While bound, the core stream
    printers post StreamDelta events instead of printing.
    """
    token = _STREAM_RELAY.set(channel)
    try:
        yield
    finally:
        _STREAM_RELAY.reset(token)
