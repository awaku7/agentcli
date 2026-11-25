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
"""

from __future__ import annotations

import collections
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

NOTICE_LIMIT = 200

# Grace period for wait_for_stream notices: after a reasoning stream
# closes, give ordinary streamed answer text this long to finish before
# inserting the notice anyway.  Matches the previous BitChat display
# worker's _DISPLAY_WAIT_STREAM_SEC.
STREAM_GRACE_SEC = 2.0


@dataclass(frozen=True)
class StreamDelta:
    """One piece of streamed model output (stage-3 producer)."""

    text: str
    source: str = ""
    turn: int = 0


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


class DisplayChannel:
    """Thread-safe display-event channel with per-class queue policies."""

    def __init__(self, notice_limit: int = NOTICE_LIMIT) -> None:
        self._cond = threading.Condition()
        self._stream: collections.deque[StreamDelta] = collections.deque()
        self._notices: collections.deque[Notice] = collections.deque()
        self._notice_limit = max(1, int(notice_limit))
        self._status: StatusRedraw | None = None
        self.dropped_notices = 0

    def post_stream(self, event: StreamDelta) -> None:
        with self._cond:
            self._stream.append(event)
            self._cond.notify()

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


def _render_notice_after_stream(core: Any, text: str) -> None:
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
    """
    deadline = time.time() + STREAM_GRACE_SEC
    # Reasoning deltas are written without a trailing newline, so wait
    # for the reasoning stream to close completely.
    while getattr(core, "_reasoning_stream_open", False):
        time.sleep(0.02)
    while getattr(core, "_stream_line_open", False) and time.time() < deadline:
        time.sleep(0.02)
    # Stop the spinner before acquiring print_lock (see the lock-order
    # note above).  Best-effort: a spinner failure must not lose the
    # notice.
    try:
        from . import spinner

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


def render_notice(core: Any, notice: Notice) -> None:
    if notice.wait_for_stream:
        _render_notice_after_stream(core, notice.text)
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


def _pump_loop(channel: DisplayChannel) -> None:
    while True:
        event = channel.take()
        if event is None:
            continue
        try:
            from .. import core as _core
        except Exception:
            continue
        try:
            if isinstance(event, Notice):
                render_notice(_core, event)
            elif isinstance(event, StatusRedraw):
                _core.print_status_line()
            # StreamDelta rendering arrives with the stream migration.
        except Exception:
            continue


def _ensure_pump() -> None:
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
    _ensure_pump()
