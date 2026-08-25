"""Web I/O: status hooks, server log, stdout/stderr shims (split from web.py)."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from typing import Any

from .. import core
from ..env_utils import env_get
from ..gui_ansi import ansi_to_html, wrap_pre
from .helpers import ANSI_ESCAPE, _strip_state_markers
from .rooms import WebRoom, _thread_ctx, web_manager


def web_human_ask(room: WebRoom, args: dict[str, Any]) -> str:
    message = args.get("message", "")
    is_password = bool(args.get("is_password", False))
    allow_empty = bool(args.get("allow_empty", False))

    # Fresh event per ask so a stale set() cannot complete immediately.
    sync_event = threading.Event()
    room.human_ask_sync_event = sync_event
    room.human_ask_is_password = is_password
    room.human_ask_message = str(message or "")
    room.human_ask_result = None  # None = no answer yet
    room.human_ask_cancelled = False
    room.human_ask_pending = True
    room.human_ask_allow_empty = allow_empty

    try:
        _web_server_log(
            f"[web-ask] start room={str(room.room_id)[:8]} "
            f"loop={bool(room.loop)} conns={len(room.active_connections)} "
            f"msg_len={len(str(message or ''))}"
        )
    except Exception:
        pass

    # notify only this room (retry a few times; browser may still be mounting)
    sent = False
    if room.loop:
        payload = {
            "type": "human_ask",
            "message": str(message or ""),
            "is_password": is_password,
        }
        for attempt in range(5):
            try:
                # Also surface in chat so the user notices even if modal CSS fails.
                if attempt == 0:
                    try:
                        room.add_message(
                            {
                                "role": "assistant",
                                "content": str(message or ""),
                            }
                        )
                    except Exception:
                        pass
                fut = asyncio.run_coroutine_threadsafe(
                    room.broadcast(payload),
                    room.loop,
                )
                fut.result(timeout=2.0)
                sent = True
                try:
                    _web_server_log(
                        f"[web-ask] broadcast ok room={str(room.room_id)[:8]} "
                        f"attempt={attempt+1} conns={len(room.active_connections)}"
                    )
                except Exception:
                    pass
                break
            except Exception as e:
                try:
                    _web_server_log(
                        f"[web-ask] broadcast retry room={str(room.room_id)[:8]} "
                        f"attempt={attempt+1} err={e!r}"
                    )
                except Exception:
                    pass
                time.sleep(0.2)
        if not sent:
            try:
                _web_server_log(
                    f"[web-ask] broadcast failed room={str(room.room_id)[:8]}"
                )
            except Exception:
                pass
    else:
        try:
            _web_server_log("[web-ask] no room.loop; client will not see modal")
        except Exception:
            pass

    cancelled = False
    try:
        # Poll so Stop/interrupt can unblock without a reply.
        while True:
            if sync_event.wait(0.2):
                # Answer or cancel signaled.
                if getattr(room, "human_ask_cancelled", False):
                    cancelled = True
                    break
                result = room.human_ask_result
                if result is None:
                    # Spurious wake; keep waiting.
                    sync_event.clear()
                    continue
                if (not allow_empty) and str(result).strip() == "":
                    # Empty submit is ignored (common UI accident).
                    try:
                        _web_server_log(
                            f"[web-ask] ignore empty reply room={str(room.room_id)[:8]}"
                        )
                    except Exception:
                        pass
                    room.human_ask_result = None
                    sync_event.clear()
                    # Re-show modal in case UI closed itself.
                    if room.loop:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                room.broadcast(
                                    {
                                        "type": "human_ask",
                                        "message": message,
                                        "is_password": is_password,
                                    }
                                ),
                                room.loop,
                            )
                        except Exception:
                            pass
                    continue
                break
            try:
                with core.interrupt_lock:
                    if core.interrupt_requested:
                        cancelled = True
                        room.human_ask_cancelled = True
                        room.human_ask_result = ""
                        break
            except Exception:
                pass
            if getattr(room, "human_ask_cancelled", False):
                cancelled = True
                room.human_ask_result = ""
                break
            if not room.active_connections:
                # Browser gone; do not hang the worker forever.
                cancelled = True
                room.human_ask_cancelled = True
                room.human_ask_result = ""
                try:
                    _web_server_log(
                        f"[web-ask] no connections; cancel room={str(room.room_id)[:8]}"
                    )
                except Exception:
                    pass
                break
    finally:
        room.human_ask_pending = False

    if getattr(room, "human_ask_cancelled", False):
        cancelled = True

    user_reply = "" if cancelled else str(room.human_ask_result or "")
    display_reply = "[SECRET]" if is_password else user_reply

    try:
        _web_server_log(
            f"[web-ask] end room={str(room.room_id)[:8]} "
            f"cancelled={cancelled} reply_len={len(user_reply)}"
        )
    except Exception:
        pass

    return json.dumps(
        {
            "user_reply": user_reply,
            "display_reply": display_reply,
            "cancelled": cancelled,
        }
    )


def web_set_status(busy: bool, label: str = ""):
    # Keep original behavior for CLI/server console (if any)
    if web_manager.original_set_status:
        web_manager.original_set_status(busy, label)

    # Web UI: prefer thread-local room; fall back to active worker room so
    # parallel tool threads still update the correct room status.
    room = None
    try:
        room = getattr(_thread_ctx, "room", None)
    except Exception:
        room = None
    if room is None:
        try:
            with web_manager.active_room_lock:
                room = web_manager.active_room
        except Exception:
            room = None

    if room is not None:
        try:
            room.set_status(busy, label)
        except Exception:
            pass

    return


def _web_console_log_enabled() -> bool:
    """Mirror captured stdout/stderr to the real server console.

    Default OFF. Set UAGENT_WEB_CONSOLE_LOG=1 to enable.
    """
    v = (env_get("UAGENT_WEB_CONSOLE_LOG") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _web_debug_enabled() -> bool:
    """Lifecycle/debug lines ([web-ask], [web-init], ...).

    Default OFF. Set UAGENT_WEB_DEBUG=1 (or UAGENT_WEB_CONSOLE_LOG=1) to enable.
    """
    v = (env_get("UAGENT_WEB_DEBUG") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return _web_console_log_enabled()


def _web_server_log(msg: str) -> None:
    """Write a compact line to the real server console when debug is on."""
    if not _web_debug_enabled():
        return
    try:
        line = str(msg or "").rstrip() + chr(10)
        sys.__stderr__.write(line)
        sys.__stderr__.flush()
    except Exception:
        try:
            sys.__stdout__.write(str(msg or "").rstrip() + chr(10))
            sys.__stdout__.flush()
        except Exception:
            pass


class WebStdout:
    """Capture stdout and stream it to the *currently running room*.

    NOTE: This is inherently process-global. We only stream logs during a worker run,
    by setting a thread-local 'room' (see _thread_ctx).
    """

    def __init__(self):
        self.buffer = ""
        self.lock = threading.Lock()

    def write(self, text):
        if _web_console_log_enabled():
            sys.__stdout__.write(text)

        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = ANSI_ESCAPE.sub("", line)
                content_html = wrap_pre(ansi_to_html(line))

                # Suppress CLI-only multiline input mode guidance in Web UI
                if "multiline" in (clean_line or "").lower():
                    continue
                # Status is delivered via type=status; drop [STATE] log noise
                # (including mid-line injections mixed into assistant/tool text).
                clean_line = _strip_state_markers(clean_line or "")
                if not clean_line.strip():
                    continue

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast(
                            {
                                "type": "log",
                                "content": clean_line,
                                "content_html": content_html,
                            }
                        ),
                        room.loop,
                    )

    def flush(self):
        with self.lock:
            if self.buffer:
                clean_line = ANSI_ESCAPE.sub("", self.buffer)
                content_html = wrap_pre(ansi_to_html(self.buffer))
                try:
                    filtered_lines: list[str] = []
                    for ln in clean_line.splitlines():
                        if "multiline" in (ln or "").lower():
                            continue
                        ln2 = _strip_state_markers(ln or "")
                        if not ln2.strip():
                            continue
                        filtered_lines.append(ln2)
                    clean_line = "\n".join(filtered_lines)
                except Exception:
                    pass

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast(
                            {
                                "type": "log",
                                "content": clean_line,
                                "content_html": content_html,
                            }
                        ),
                        room.loop,
                    )
                self.buffer = ""

        if _web_console_log_enabled():
            sys.__stdout__.flush()

    def isatty(self):
        return sys.__stdout__.isatty()


class WebStderr(WebStdout):
    def write(self, text):
        if _web_console_log_enabled():
            sys.__stderr__.write(text)

        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = ANSI_ESCAPE.sub("", line)
                content_html = wrap_pre(ansi_to_html(line))
                if "multiline" in (clean_line or "").lower():
                    continue
                clean_line = _strip_state_markers(clean_line or "")
                if not clean_line.strip():
                    continue

                room = getattr(_thread_ctx, "room", None)
                if clean_line.strip() and room and room.loop:
                    asyncio.run_coroutine_threadsafe(
                        room.broadcast(
                            {
                                "type": "log",
                                "content": clean_line,
                                "content_html": content_html,
                            }
                        ),
                        room.loop,
                    )

    def flush(self):
        super().flush()
        if _web_console_log_enabled():
            sys.__stderr__.flush()

    def isatty(self):
        return sys.__stderr__.isatty()


sys.stdout = WebStdout()
sys.stderr = WebStderr()
