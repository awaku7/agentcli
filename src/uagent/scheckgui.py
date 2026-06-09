# -*- coding: utf-8 -*-
"""scheckgui.py - File-Buffered Extreme Stability Version"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil

import re
import sys
import threading
from urllib.parse import unquote
from urllib.request import Request, urlopen
from pathlib import Path
from dataclasses import dataclass
from queue import Empty as QueueEmpty
from typing import Any, Optional

# DPI warnings and crash avoidance
os.environ["QT_LOGGING_RULES"] = (
    "qt.qpa.window=false;qt.text.font.db=false;qt.multimedia.ffmpeg=false"
)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia

from .i18n import _, detect_lang, set_thread_lang

set_thread_lang(detect_lang())

from . import core as core
from . import tools
from .welcome import get_welcome_message
from .runtime import runtime_init as _runtime_init

from .util_tools import (
    image_file_to_data_url,
    build_long_memory_system_message,
    append_result_to_outfile,
    handle_command,
    build_initial_messages,
    get_reasoning_mode,
    get_verbosity_mode,
    apply_reasoning_arg,
    apply_verbosity_arg,
)

from .uagent_llm import run_llm_rounds as util_run_llm_rounds
from .image_session import build_image_session_message
from .providers.util_providers import make_client as util_make_client
from .tools.context import ToolCallbacks, get_callbacks
from .tools.skill_history import make_finish_skill_handler
from .scheduler import start_background_scheduler, stop_background_scheduler

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


THUMB_SIZE_PX = 96
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
AUDIO_EXTS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".wma",
    ".mp4",
    ".webm",
}
LOG_FILE = "gui_worker_session.log"


def _gui_norm_path(p: Any) -> str:
    if not isinstance(p, str):
        return ""
    s = p.strip()
    if not s:
        return ""
    try:
        return str(Path(s).expanduser().resolve())
    except Exception:
        return s


class RedirectToLog:
    def __init__(self, path: str, original_stream):
        self.path = path
        self.original_stream = original_stream

    def write(self, data: str):
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(data)
        except Exception:
            pass

    def flush(self):
        return


@dataclass
class GuiConfig:
    provider: str
    model: str
    initial_file: Optional[str]


@dataclass
class HistoryEntry:
    text: str
    images: list[str]
    files: list[str]


class DropInput(QtWidgets.QPlainTextEdit):
    sig_files_dropped = QtCore.Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setPlaceholderText(_("Drop files/images here"))
        self.setMinimumHeight(120)

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()

    def dropEvent(self, e):
        ps = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if ps:
            self.sig_files_dropped.emit(ps)
            e.acceptProposedAction()


class DropOutput(QtWidgets.QTextBrowser):
    sig_files_dropped = QtCore.Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()

    def dropEvent(self, e):
        ps = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if ps:
            self.sig_files_dropped.emit(ps)
            e.acceptProposedAction()

    def contextMenuEvent(self, e):
        menu = self.createStandardContextMenu()
        try:
            href = self.anchorAt(e.pos())
            if href:
                url = QtCore.QUrl(href)
                scheme = (url.scheme() or "").lower()
                if scheme in ("file", "http", "https", "uag-download"):
                    menu.addSeparator()
                    act = menu.addAction(_("Download"))

                    def _do_download():
                        try:
                            win = self.window()
                            handler = getattr(win, "_handle_output_anchor", None)
                            if handler is None:
                                return
                            if (
                                scheme in ("file", "http", "https")
                                and not url.fragment()
                            ):
                                dl = QtCore.QUrl(url)
                                dl.setFragment("download")
                                handler(dl)
                            else:
                                handler(url)
                        except Exception:
                            pass

                    act.triggered.connect(_do_download)
        except Exception:
            pass
        menu.exec(e.globalPos())
        menu.deleteLater()


class DropThumbs(QtWidgets.QListWidget):
    sig_files_dropped = QtCore.Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        ps = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if ps:
            self.sig_files_dropped.emit(ps)
            e.acceptProposedAction()
        else:
            e.ignore()


class ScheckWorker(QtCore.QObject):
    """Worker that runs the LLM loop."""

    sig_finished = QtCore.Signal()

    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.cfg = cfg
        self.tools = tools
        self.messages: list[dict[str, Any]] = []
        self.image_session: Optional[dict[str, Any]] = None
        self._stop = threading.Event()
        self._provider = ""
        self._client = None
        self._depname = ""

    def _init_callbacks(self):
        cb = ToolCallbacks(
            set_status=core.set_status,
            debug=getattr(core, "debug", None),
            log=getattr(core, "log", None),
            error=getattr(core, "error", None),
            exception=getattr(core, "exception", None),
            rewrite_current_log_from_messages=getattr(
                core, "rewrite_current_log_from_messages", None
            ),
            log_message=getattr(core, "log_message", None),
            get_env=core.get_env,
            truncate_output=core.truncate_output,
            human_ask_lock=core.human_ask_lock,
            human_ask_active_ref=(lambda: core.human_ask_active),
            human_ask_set_active=(lambda v: setattr(core, "human_ask_active", bool(v))),
            human_ask_queue_ref=(lambda: core.human_ask_queue),
            human_ask_set_queue=(lambda q: setattr(core, "human_ask_queue", q)),
            human_ask_lines_ref=(lambda: core.human_ask_lines),
            human_ask_multiline_active_ref=(lambda: core.human_ask_multiline_active),
            human_ask_set_multiline_active=(
                lambda v: setattr(core, "human_ask_multiline_active", bool(v))
            ),
            human_ask_set_password=(
                lambda v: setattr(core, "human_ask_is_password", bool(v))
            ),
            multi_input_sentinel=core.MULTI_INPUT_SENTINEL,
            event_queue=core.event_queue,
            cmd_encoding=core.CMD_ENCODING,
            cmd_exec_timeout_ms=core.CMD_EXEC_TIMEOUT_MS,
            python_exec_timeout_ms=core.PYTHON_EXEC_TIMEOUT_MS,
            url_fetch_timeout_ms=core.URL_FETCH_TIMEOUT_MS,
            url_fetch_max_bytes=core.URL_FETCH_MAX_BYTES,
            read_file_max_bytes=core.READ_FILE_MAX_BYTES,
            is_gui=True,
        )
        self.tools.init_callbacks(cb)

    @QtCore.Slot()
    def run(self):
        try:
            self._init_callbacks()
            start_background_scheduler(core.event_queue)

            # Provider/client/model are decided by util_make_client.
            self._provider, self._client, self._depname = util_make_client(core)
            if (
                self._provider == "openrouter"
                and (self._depname or "").strip() == "openrouter/auto"
            ):
                raw_fb = (
                    os.environ.get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
                ).strip()
                if raw_fb:
                    print("[INFO] " + _("OpenRouter fallback models enabled."))

            self.messages = build_initial_messages(core=core)
            cb = get_callbacks()
            prev_finish_skill = cb.finish_skill
            cb.finish_skill = make_finish_skill_handler(self.messages, core)

            # Long-term memory
            from .tools import long_memory as personal_long_memory
            from .tools import shared_memory

            print("[INFO] " + _("Loaded long-term memory."))

            try:
                before_len = len(self.messages)
                flags = _runtime_init.append_long_memory_system_messages(
                    core=core,
                    messages=self.messages,
                    build_long_memory_system_message_fn=build_long_memory_system_message,
                    personal_long_memory_mod=personal_long_memory,
                    shared_memory_mod=shared_memory,
                )

                if flags.get("shared_enabled"):
                    print("[INFO] " + _("Loaded shared long-term memory."))

                for m in self.messages[before_len:]:
                    core.log_message(m)

            except Exception as e:
                print(
                    "[WARN] "
                    + _(
                        "Exception occurred while loading shared long-term memory: %(err)s"
                    )
                    % {"err": e}
                )

            while not self._stop.is_set():
                try:
                    ev = core.event_queue.get(timeout=0.5)
                    kind = ev.get("kind")

                    if kind == "command":
                        result = handle_command(
                            ev.get("text", ""),
                            self.messages,
                            self._client,
                            self._depname,
                            core=core,
                        )
                        if not result:
                            self._stop.set()
                            break
                        if getattr(result, "run_llm", False):
                            prompt = (
                                getattr(result, "prompt", None)
                                or "Run the loaded skill."
                            )
                            m = {"role": "user", "content": prompt}
                            self.messages.append(m)
                            core.log_message(m)
                            self.image_session = build_image_session_message(
                                self.messages, self._depname
                            )
                            util_run_llm_rounds(
                                self._provider,
                                self._client,
                                self._depname,
                                self.messages,
                                core=core,
                                make_client_fn=util_make_client,
                                append_result_to_outfile_fn=append_result_to_outfile,
                                try_open_images_from_text_fn=lambda _: None,
                            )
                    elif kind == "schedule_notice":
                        notice = (ev.get("text", "") or "").strip()
                        if notice:
                            print("[INFO] " + notice)
                        continue
                    elif kind in ("user", "timer", "gui_user"):
                        text = ev.get("text", "")
                        files = list(ev.get("files", []) or [])

                        if files:
                            file_lines = [
                                _("[Attached File] %(name)s (%(path)s)")
                                % {"name": os.path.basename(p), "path": p}
                                for p in files
                            ]
                            if file_lines:
                                if text.strip():
                                    text = (
                                        text.rstrip() + "\n\n" + "\n".join(file_lines)
                                    )
                                else:
                                    text = "\n".join(file_lines)

                        use_responses_api = (
                            os.environ.get("UAGENT_RESPONSES", "") or ""
                        ).lower() in (
                            "1",
                            "true",
                        )
                        prov = (os.environ.get("UAGENT_PROVIDER") or "").lower()
                        allow_multimodal = use_responses_api and prov in (
                            "azure",
                            "openai",
                            "bedrock",
                        )

                        if allow_multimodal:
                            parts: list[dict[str, Any]] = [
                                {"type": "text", "text": text.strip()}
                            ]

                            for p in ev.get("images", []):
                                if not os.path.isfile(p):
                                    continue
                                try:
                                    data_url = image_file_to_data_url(
                                        p, max_bytes=10_000_000
                                    )
                                    parts.append(
                                        {
                                            "type": "image_url",
                                            "image_url": {"url": data_url},
                                        }
                                    )
                                except Exception as e:
                                    parts.append(
                                        {
                                            "type": "text",
                                            "text": "[WARN] "
                                            + (
                                                _(
                                                    "Failed to attach image: %(path)s (%(etype)s: %(err)s)"
                                                )
                                                % {
                                                    "path": p,
                                                    "etype": type(e).__name__,
                                                    "err": e,
                                                }
                                            ),
                                        }
                                    )

                            m = {"role": "user", "content": parts}
                            self.messages.append(m)
                            core.log_message(m)

                            util_run_llm_rounds(
                                self._provider,
                                self._client,
                                self._depname,
                                self.messages,
                                core=core,
                                make_client_fn=util_make_client,
                                append_result_to_outfile_fn=append_result_to_outfile,
                                try_open_images_from_text_fn=lambda _: None,
                            )
                            continue

                        # Fallback: analyze_image tool -> text injection
                        for p in ev.get("images", []):
                            if os.path.isfile(p):
                                core.set_status(True, "analyze_image")
                                res = self.tools.run_tool(
                                    "analyze_image", {"image_path": p}
                                )
                                text += (
                                    _("[Attached Image] %(path)s") % {"path": p}
                                    + "\n"
                                    + _("[Image Path] %(path)s") % {"path": p}
                                    + "\n"
                                    + str(res)
                                )
                        if text.strip():
                            m = {"role": "user", "content": text.strip()}
                            self.messages.append(m)
                            core.log_message(m)
                            self.image_session = build_image_session_message(
                                self.messages, self._depname
                            )
                            util_run_llm_rounds(
                                self._provider,
                                self._client,
                                self._depname,
                                self.messages,
                                core=core,
                                make_client_fn=util_make_client,
                                append_result_to_outfile_fn=append_result_to_outfile,
                                try_open_images_from_text_fn=lambda _: None,
                            )
                except QueueEmpty:
                    continue
                except Exception:
                    try:
                        with open(
                            LOG_FILE, "a", encoding="utf-8", buffering=1
                        ) as log_f:
                            log_f.write("[ERROR] Worker exception:\n")
                            import traceback

                            traceback.print_exc(file=log_f)
                    except Exception:
                        pass
                    continue
        finally:
            get_callbacks().finish_skill = prev_finish_skill
            self.sig_finished.emit()

    def stop(self):
        self._stop.set()


class MainWindow(QtWidgets.QMainWindow):
    _URL_RE = re.compile(r"\b(https?://[^\s<>\"']+|www\.[^\s<>\"']+)", re.IGNORECASE)

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            (text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    @classmethod
    def _linkify_html(cls, text: str) -> str:
        escaped = cls._escape_html(text or "")

        def _repl(m: re.Match) -> str:
            raw = m.group(0)
            href = raw
            if raw.lower().startswith("www."):
                href = "https://" + raw
            return f'<a href="{href}" style="color:#2563eb; text-decoration: underline;">{raw}</a>'

        linked = cls._URL_RE.sub(_repl, escaped)
        return linked.replace("\n", "<br>")

    @staticmethod
    def _ansi_color(code: int, *, background: bool = False) -> Optional[str]:
        fg = {
            30: "#000000",
            31: "#dc2626",
            32: "#16a34a",
            33: "#ca8a04",
            34: "#2563eb",
            35: "#a855f7",
            36: "#0891b2",
            37: "#d1d5db",
            90: "#6b7280",
            91: "#f87171",
            92: "#4ade80",
            93: "#facc15",
            94: "#60a5fa",
            95: "#d8b4fe",
            96: "#22d3ee",
            97: "#ffffff",
        }
        bg = {
            40: "#000000",
            41: "#dc2626",
            42: "#16a34a",
            43: "#ca8a04",
            44: "#2563eb",
            45: "#a855f7",
            46: "#0891b2",
            47: "#d1d5db",
            100: "#6b7280",
            101: "#f87171",
            102: "#4ade80",
            103: "#facc15",
            104: "#60a5fa",
            105: "#d8b4fe",
            106: "#22d3ee",
            107: "#ffffff",
        }
        return (bg if background else fg).get(code)

    @staticmethod
    def _ansi_256_color(n: int) -> str:
        n = max(0, min(255, int(n)))
        base = [
            "#000000",
            "#800000",
            "#008000",
            "#808000",
            "#000080",
            "#800080",
            "#008080",
            "#c0c0c0",
            "#808080",
            "#ff0000",
            "#00ff00",
            "#ffff00",
            "#0000ff",
            "#ff00ff",
            "#00ffff",
            "#ffffff",
        ]
        if n < 16:
            return base[n]
        if n < 232:
            n -= 16
            r = n // 36
            g = (n % 36) // 6
            b = n % 6

            def _c(v: int) -> int:
                return 0 if v == 0 else 55 + 40 * v

            return f"#{_c(r):02x}{_c(g):02x}{_c(b):02x}"
        v = 8 + (n - 232) * 10
        return f"#{v:02x}{v:02x}{v:02x}"

    def _append_ansi_text(self, text: str) -> None:
        """Append ANSI-colored text without using HTML. SGR underline is ignored."""
        text = text or ""
        cursor = self._output.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self._output.setTextCursor(cursor)

        state: dict[str, Any] = {"fg": None, "bg": None, "bold": False, "italic": False}

        def _format() -> QtGui.QTextCharFormat:
            fmt = QtGui.QTextCharFormat()
            # Reset rich-text/link state that may remain after insertHtml() blocks.
            # This prevents normal log text from inheriting anchor underline/href.
            fmt.setAnchor(False)
            fmt.setAnchorHref("")
            fmt.setFontUnderline(False)
            if state.get("fg"):
                fmt.setForeground(QtGui.QBrush(QtGui.QColor(str(state["fg"]))))
            if state.get("bg"):
                fmt.setBackground(QtGui.QBrush(QtGui.QColor(str(state["bg"]))))
            if state.get("bold"):
                fmt.setFontWeight(QtGui.QFont.Bold)
            else:
                fmt.setFontWeight(QtGui.QFont.Normal)
            fmt.setFontItalic(bool(state.get("italic")))
            return fmt

        def _plain_line_format(line: str) -> QtGui.QTextCharFormat:
            fmt = QtGui.QTextCharFormat()
            fmt.setAnchor(False)
            fmt.setAnchorHref("")
            fmt.setFontUnderline(False)
            fmt.setFontWeight(QtGui.QFont.Normal)
            s = (line or "").lstrip()
            if s.startswith("[ERROR]") or s.startswith("[FATAL]"):
                fmt.setForeground(QtGui.QBrush(QtGui.QColor("#dc2626")))
                fmt.setFontWeight(QtGui.QFont.Bold)
            elif s.startswith("[WARN]") or s.startswith("[TOOL]"):
                fmt.setForeground(QtGui.QBrush(QtGui.QColor("#ca8a04")))
                fmt.setFontWeight(QtGui.QFont.Bold)
            elif s.startswith("[url]"):
                fmt.setForeground(QtGui.QBrush(QtGui.QColor("#0891b2")))
            elif s.startswith("[INFO]"):
                fmt.setForeground(QtGui.QBrush(QtGui.QColor("#2563eb")))
            elif s.startswith("[OK]") or s.startswith("[SUCCESS]"):
                fmt.setForeground(QtGui.QBrush(QtGui.QColor("#16a34a")))
            return fmt

        def _insert_with_links(s: str, base_fmt: QtGui.QTextCharFormat) -> None:
            cur = 0
            for mm in self._URL_RE.finditer(s or ""):
                if mm.start() > cur:
                    cursor.insertText(s[cur : mm.start()], base_fmt)
                raw = mm.group(0)
                href = raw if not raw.lower().startswith("www.") else "https://" + raw
                # Do not construct QTextCharFormat(base_fmt): PySide builds may reject it,
                # which would fall back to plain text for the whole block.
                link_fmt = QtGui.QTextCharFormat()
                link_fmt.setAnchor(True)
                link_fmt.setAnchorHref(href)
                link_fmt.setForeground(QtGui.QBrush(QtGui.QColor("#2563eb")))
                link_fmt.setFontUnderline(True)
                link_fmt.setFontWeight(base_fmt.fontWeight())
                link_fmt.setFontItalic(base_fmt.fontItalic())
                cursor.insertText(raw, link_fmt)
                cur = mm.end()
            if cur < len(s or ""):
                cursor.insertText((s or "")[cur:], base_fmt)

        def _insert_plain_semantic(s: str) -> None:
            for line in (s or "").splitlines(keepends=True):
                _insert_with_links(line, _plain_line_format(line))

        def _apply(params: list[int]) -> None:
            if not params:
                params = [0]
            i = 0
            while i < len(params):
                p = params[i]
                if p == 0:
                    state.update(
                        {"fg": None, "bg": None, "bold": False, "italic": False}
                    )
                elif p == 1:
                    state["bold"] = True
                elif p == 3:
                    state["italic"] = True
                elif p == 22:
                    state["bold"] = False
                elif p == 23:
                    state["italic"] = False
                elif 30 <= p <= 37 or 90 <= p <= 97:
                    state["fg"] = self._ansi_color(p)
                elif p == 39:
                    state["fg"] = None
                elif 40 <= p <= 47 or 100 <= p <= 107:
                    state["bg"] = self._ansi_color(p, background=True)
                elif p == 49:
                    state["bg"] = None
                elif p == 38 and i + 2 < len(params) and params[i + 1] == 5:
                    state["fg"] = self._ansi_256_color(params[i + 2])
                    i += 2
                elif p == 48 and i + 2 < len(params) and params[i + 1] == 5:
                    state["bg"] = self._ansi_256_color(params[i + 2])
                    i += 2
                # SGR 4/24 underline is intentionally ignored.
                i += 1

        if not self._ansi_re.search(text):
            _insert_plain_semantic(text)
            self._output.setTextCursor(cursor)
            self._output.ensureCursorVisible()
            return

        pos = 0
        for m in self._ansi_re.finditer(text):
            chunk = text[pos : m.start()]
            if chunk:
                cursor.insertText(chunk, _format())
            raw = m.group(0)
            params: list[int] = []
            try:
                inner = raw[2:-1]
                if inner.startswith("?"):
                    inner = inner[1:]
                for part in inner.rstrip("m").split(";"):
                    if part.strip():
                        params.append(int(part))
            except Exception:
                params = []
            _apply(params)
            pos = m.end()
        tail = text[pos:]
        if tail:
            cursor.insertText(tail, _format())
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def _set_welcome_text(self) -> None:
        try:
            msg = get_welcome_message()
        except Exception:
            msg = ""
        if not msg:
            return
        html = (
            '<div style="font-family: Consolas, Menlo, Monaco, monospace; white-space: pre;">'
            + self._escape_html(msg)
            + "</div><br>"
        )
        try:
            self._output.moveCursor(QtGui.QTextCursor.End)
            self._output.insertHtml(html)
            self._output.ensureCursorVisible()
        except Exception:
            pass

    def _show_welcome_dialog(self) -> None:
        try:
            msg = get_welcome_message()
        except Exception:
            msg = ""
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle(_("Welcome / Quick Guide"))
        dlg.setIcon(QtWidgets.QMessageBox.Information)
        dlg.setText(msg or "")
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        dlg.exec()

    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.setWindowTitle(_("uag GUI (Extreme Stability)"))
        self.resize(1100, 850)
        self._attached_images: list[str] = []
        self._attached_files: list[str] = []
        self._history: list[HistoryEntry] = []
        self._hist_idx = -1
        self._log_pos = 0
        self._known_image_paths: set[str] = set()
        self._known_image_preview_paths: set[str] = set()
        self._known_file_paths: set[str] = set()
        self._attachment_seq = 0
        self._sent_preview_seq = 0
        self._ansi_re = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
        self._audio_output = QtMultimedia.QAudioOutput(self)
        try:
            self._audio_output.setVolume(0.8)
        except Exception:
            pass
        self._audio_player = QtMultimedia.QMediaPlayer(self)
        try:
            self._audio_player.setAudioOutput(self._audio_output)
        except Exception:
            pass
        self._audio_current_path = ""

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self._output = DropOutput()
        self._output.setReadOnly(True)
        self._output.setOpenExternalLinks(False)
        self._output.setOpenLinks(False)
        self._output.anchorClicked.connect(self._handle_output_anchor)
        self._output.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        )
        layout.addWidget(self._output, 1)

        self._thumbs = DropThumbs()
        self._thumbs.sig_files_dropped.connect(self._on_files_dropped)
        self._thumbs.setViewMode(QtWidgets.QListView.IconMode)
        self._thumbs.setFixedHeight(140)
        self._thumbs.setIconSize(QtCore.QSize(THUMB_SIZE_PX, THUMB_SIZE_PX))
        self._thumbs.itemDoubleClicked.connect(
            lambda it: self._open_image(it.toolTip())
        )
        self._thumbs.setVisible(True)
        layout.addWidget(self._thumbs)

        input_panel = QtWidgets.QWidget()
        input_layout = QtWidgets.QVBoxLayout(input_panel)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self._drop_label = QtWidgets.QLabel(_("↑ You can attach files by drag & drop"))
        self._drop_label.setStyleSheet("font-weight: bold;")
        input_layout.addWidget(self._drop_label)

        self._input = DropInput()
        self._input.setFixedHeight(140)
        self._input.installEventFilter(self)
        self._input.sig_files_dropped.connect(self._on_files_dropped)
        self._output.sig_files_dropped.connect(self._on_files_dropped)
        input_layout.addWidget(self._input)

        pw_row = QtWidgets.QHBoxLayout()
        pw_row.setContentsMargins(0, 0, 0, 0)
        self._pw_input = QtWidgets.QLineEdit()
        self._pw_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self._pw_input.setFixedHeight(40)
        self._pw_input.setVisible(False)
        self._pw_input.returnPressed.connect(self._on_send)
        pw_row.addWidget(self._pw_input, 1)
        pw_row.addStretch(1)

        self._attach_btn = QtWidgets.QPushButton(_("Attach..."))
        self._attach_btn.setFixedWidth(90)
        self._attach_btn.clicked.connect(self._on_choose_files)
        pw_row.addWidget(self._attach_btn)

        self._btn = QtWidgets.QPushButton(_("Send"))
        self._btn.setFixedWidth(80)
        self._btn.clicked.connect(self._on_send)
        pw_row.addWidget(self._btn)
        input_layout.addLayout(pw_row)

        layout.addWidget(input_panel)

        self._status_label = QtWidgets.QLabel(" [STATE] IDLE")
        self.statusBar().addPermanentWidget(self._status_label)

        self._workdir_label = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self._workdir_label)
        self._last_workdir = ""

        self._provider_model_label = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self._provider_model_label)
        self._provider_model_text = ""

        self._mode_label = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self._mode_label)
        self._mode_text = ""

        self._monitor_timer = QtCore.QTimer(self)
        self._monitor_timer.timeout.connect(self._update_ui_from_log)
        self._monitor_timer.start(200)

        # initial mode label
        self._update_mode_label()

        self._thread = QtCore.QThread()
        self._worker = ScheckWorker(cfg)
        self._worker.moveToThread(self._thread)
        self._worker.sig_finished.connect(self._thread.quit)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

        self._set_welcome_text()

        try:
            help_menu = self.menuBar().addMenu(_("Help"))
            act = help_menu.addAction(_("Welcome / Quick Guide"))
            act.triggered.connect(self._show_welcome_dialog)
        except Exception:
            pass

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(
            self._on_send
        )
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Enter"), self).activated.connect(
            self._on_send
        )

        # Mode menu
        try:
            mode_menu = self.menuBar().addMenu(_("Mode"))

            act_r_off = mode_menu.addAction(_("Reasoning: off"))
            act_r_off.triggered.connect(lambda: self._set_reasoning("0"))

            act_r_auto = mode_menu.addAction(_("Reasoning: auto"))
            act_r_auto.triggered.connect(lambda: self._set_reasoning("auto"))
            act_r_min = mode_menu.addAction(_("Reasoning: minimal"))
            act_r_min.triggered.connect(lambda: self._set_reasoning("minimal"))
            act_r_low = mode_menu.addAction(_("Reasoning: low"))
            act_r_low.triggered.connect(lambda: self._set_reasoning("1"))
            act_r_mid = mode_menu.addAction(_("Reasoning: medium"))
            act_r_mid.triggered.connect(lambda: self._set_reasoning("2"))
            act_r_high = mode_menu.addAction(_("Reasoning: high"))
            act_r_high.triggered.connect(lambda: self._set_reasoning("3"))

            act_r_xhigh = mode_menu.addAction(_("Reasoning: xhigh"))
            act_r_xhigh.triggered.connect(lambda: self._set_reasoning("xhigh"))

            mode_menu.addSeparator()

            act_v_off = mode_menu.addAction(_("Verbosity: off"))
            act_v_off.triggered.connect(lambda: self._set_verbosity("0"))
            act_v_low = mode_menu.addAction(_("Verbosity: low"))
            act_v_low.triggered.connect(lambda: self._set_verbosity("1"))
            act_v_mid = mode_menu.addAction(_("Verbosity: medium"))
            act_v_mid.triggered.connect(lambda: self._set_verbosity("2"))
            act_v_high = mode_menu.addAction(_("Verbosity: high"))
            act_v_high.triggered.connect(lambda: self._set_verbosity("3"))

            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self).activated.connect(
                lambda: self._set_reasoning("auto")
            )
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self).activated.connect(
                lambda: self._set_verbosity("2")
            )
        except Exception:
            pass

    def _update_mode_label(self) -> None:
        try:
            r = get_reasoning_mode()
            v = get_verbosity_mode()
            txt = f"reasoning={r} verbosity={v}"
        except Exception:
            txt = ""

        if txt and txt != getattr(self, "_mode_text", ""):
            self._mode_text = txt
            try:
                self._mode_label.setText(" " + txt)
            except Exception:
                pass

    def _set_reasoning(self, arg: str) -> None:
        try:
            new_mode = apply_reasoning_arg(arg)
            print(_("[mode] reasoning=%(mode)s") % {"mode": new_mode})
        except Exception:
            print(
                _(
                    ":r [0|1|2|3|auto|minimal|xhigh]  (0=off, 1=low, 2=medium, 3=high; auto/minimal/xhigh)"
                )
            )
        self._update_mode_label()

    def _set_verbosity(self, arg: str) -> None:
        try:
            new_mode = apply_verbosity_arg(arg)
            print(_("[mode] verbosity=%(mode)s") % {"mode": new_mode})
        except Exception:
            print(_(":v [0|1|2|3]  (0=off, 1=low, 2=medium, 3=high; no arg=keep)"))
        self._update_mode_label()

    def _update_ui_from_log(self):
        if not os.path.exists(LOG_FILE):
            return

        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._log_pos)
                new_data = f.read()
                self._log_pos = f.tell()

            if new_data:
                clean_text = self._ansi_re.sub("", new_data)

                # keep mode label updated even when status doesn't change
                self._update_mode_label()

                if not hasattr(self, "_tty_partial_line"):
                    self._tty_partial_line = ""  # type: ignore[attr-defined]

                def _normalize_stream_chunk(chunk: str) -> str:
                    out_parts: list[str] = []
                    cur = self._tty_partial_line  # type: ignore[attr-defined]
                    for ch in chunk:
                        if ch == "\r":
                            cur = ""
                            continue
                        if ch == "\n":
                            out_parts.append(cur + "\n")
                            cur = ""
                            continue
                        oc = ord(ch)
                        if ch == "\t" or oc >= 0x20:
                            cur += ch
                    self._tty_partial_line = cur  # type: ignore[attr-defined]
                    return "".join(out_parts)

                clean_text = _normalize_stream_chunk(clean_text)

                states = re.findall(r"\[STATE\]\s+(\w+)(?:\s+\[(.*?)\])?", clean_text)
                if states:
                    last_st, last_lb = states[-1]
                    self._status_label.setText(
                        f" [STATE] {last_st}" + (f" [{last_lb}]" if last_lb else "")
                    )

                try:
                    mprov = re.findall(
                        r"^\[INFO\]\s+LLM provider\s*=\s*(.+)$",
                        clean_text,
                        flags=re.MULTILINE,
                    )
                    mdep = re.findall(
                        r"^\[INFO\]\s+model\(deployment\)\s*=\s*(.+)$",
                        clean_text,
                        flags=re.MULTILINE,
                    )
                    if mprov:
                        self._provider_model_text = f"provider={mprov[-1].strip()}"
                    if mdep:
                        ptxt = getattr(self, "_provider_model_text", "")
                        mtxt = f"model={mdep[-1].strip()}"
                        self._provider_model_text = (
                            (ptxt + " " + mtxt).strip() if ptxt else mtxt
                        )
                    if getattr(self, "_provider_model_text", ""):
                        self._provider_model_label.setText(
                            " " + self._provider_model_text
                        )
                except Exception:
                    pass

                items = []
                try:
                    items = self._collect_generated_image_paths()
                except Exception:
                    pass

                for p in items:
                    if p and os.path.exists(p):
                        self._append_image_preview(p, "GEN")

                audio_items = []
                try:
                    audio_items = self._collect_generated_audio_paths()
                except Exception:
                    pass

                for p in audio_items:
                    if p and os.path.exists(p):
                        self._append_audio_preview(p, "GENA")

                display_lines = []
                for line in new_data.splitlines(keepends=True):
                    s = self._ansi_re.sub("", line).strip()
                    if s.startswith("[STATE]"):
                        continue
                    if "multiline" in (s or "").lower():
                        continue
                    display_lines.append(line)
                display_text = "".join(display_lines)

                if display_text:
                    try:
                        self._append_ansi_text(display_text)
                    except Exception:
                        cursor = self._output.textCursor()
                        cursor.movePosition(QtGui.QTextCursor.End)
                        self._output.setTextCursor(cursor)
                        self._output.insertPlainText(display_text)
                        self._output.ensureCursorVisible()

            with core.human_ask_lock:
                active = core.human_ask_active
                is_password = core.human_ask_is_password

            is_pw_mode = bool(active and is_password)
            if is_pw_mode != self._pw_input.isVisible():
                self._pw_input.setVisible(is_pw_mode)
                self._input.setVisible(not is_pw_mode)
                if is_pw_mode:
                    self._pw_input.setFocus()
                else:
                    self._input.setFocus()

            if active:
                msg = (
                    _("Enter password...")
                    if is_password
                    else "Enter response for human_ask..."
                )
                self._input.setPlaceholderText(msg)
                self._pw_input.setPlaceholderText(msg)
            else:
                self._input.setPlaceholderText(_("Enter a message..."))

            try:
                cwd = os.getcwd()
                if cwd != self._last_workdir:
                    self._last_workdir = cwd
                    self._workdir_label.setText(f" workdir: {cwd}")
            except Exception:
                pass

        except Exception:
            pass

    def _on_choose_files(self):
        try:
            paths = QtWidgets.QFileDialog.getOpenFileNames(
                self,
                _("Attach files"),
                os.getcwd(),
                _("All Files (*)"),
            )[0]
            if paths:
                self._on_files_dropped(paths)
        except Exception:
            pass

    def _on_files_dropped(self, ps):
        self._attachment_seq += 1
        for i, p in enumerate(ps):
            if os.path.splitext(p)[1].lower() in IMAGE_EXTS:
                self._attached_images.append(p)
                self._add_thumb(p, f"ATT:{self._attachment_seq}:{i}")
            else:
                self._attached_files.append(p)
                self._add_file_item(p, f"ATT:{self._attachment_seq}:{i}")

    def _collect_generated_image_paths(self) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()

        def _add(candidate: Any) -> None:
            p = _gui_norm_path(candidate)
            if not p or p in seen:
                return
            seen.add(p)
            paths.append(p)

        worker = getattr(self, "_worker", None)
        msgs = getattr(worker, "messages", []) if worker is not None else []

        for msg in reversed(msgs[-20:]):
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "")
            if role not in ("assistant", "tool"):
                continue

            for att in msg.get("attachments") or []:
                if not isinstance(att, dict):
                    continue
                if str(att.get("type") or "").lower() not in (
                    "image",
                    "image/png",
                    "image/jpeg",
                ):
                    continue
                _add(
                    att.get("saved_path")
                    or att.get("path")
                    or att.get("file_path")
                    or att.get("name")
                )

            _add(msg.get("saved_path"))
            for item in msg.get("saved_files") or []:
                _add(item)

        return paths

    def _collect_generated_audio_paths(self) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()

        def _add(candidate: Any) -> None:
            p = _gui_norm_path(candidate)
            if not p or p in seen:
                return
            seen.add(p)
            paths.append(p)

        worker = getattr(self, "_worker", None)
        msgs = getattr(worker, "messages", []) if worker is not None else []

        for msg in reversed(msgs[-20:]):
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "")
            if role not in ("assistant", "tool"):
                continue

            for att in msg.get("attachments") or []:
                if not isinstance(att, dict):
                    continue
                if str(att.get("type") or "").lower() not in (
                    "audio",
                    "audio/mpeg",
                    "audio/mp3",
                    "audio/wav",
                    "audio/x-wav",
                    "audio/mp4",
                    "audio/aac",
                    "audio/flac",
                    "audio/ogg",
                    "audio/opus",
                    "audio/webm",
                ):
                    continue
                _add(
                    att.get("saved_path")
                    or att.get("path")
                    or att.get("file_path")
                    or att.get("name")
                )

            p = _gui_norm_path(msg.get("saved_path"))
            if p and os.path.splitext(p)[1].lower() in AUDIO_EXTS:
                _add(p)

            for item in msg.get("saved_files") or []:
                if os.path.splitext(_gui_norm_path(item))[1].lower() in AUDIO_EXTS:
                    _add(item)

        return paths

    def _collect_generated_image_entries(self):
        entries = []
        worker = getattr(self, "_worker", None)
        msgs = getattr(worker, "messages", []) if worker is not None else []

        for mi, msg in enumerate(reversed(msgs[-20:])):
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "")
            if role not in ("assistant", "tool"):
                continue

            ai = 0
            for att in msg.get("attachments") or []:
                if not isinstance(att, dict):
                    continue
                if str(att.get("type") or "").lower() not in (
                    "image",
                    "image/png",
                    "image/jpeg",
                ):
                    continue
                p = _gui_norm_path(
                    att.get("saved_path")
                    or att.get("path")
                    or att.get("file_path")
                    or att.get("name")
                )
                if p:
                    entries.append((f"m{mi}:a{ai}", p))
                    ai += 1

            p = _gui_norm_path(msg.get("saved_path"))
            if p:
                entries.append((f"m{mi}:s", p))

            for si, item in enumerate(msg.get("saved_files") or []):
                p = _gui_norm_path(item)
                if p:
                    entries.append((f"m{mi}:f{si}", p))

        return entries

    def _find_generated_image_url(self, path: str) -> str:
        worker = getattr(self, "_worker", None)
        msgs = getattr(worker, "messages", []) if worker is not None else []
        target = (path or "").strip()
        if not target:
            return ""
        for msg in reversed(msgs[-20:]):
            if not isinstance(msg, dict):
                continue
            for att in msg.get("attachments") or []:
                if not isinstance(att, dict):
                    continue
                if str(att.get("type") or "").lower() not in (
                    "image",
                    "image/png",
                    "image/jpeg",
                ):
                    continue
                att_path = _gui_norm_path(
                    att.get("saved_path")
                    or att.get("path")
                    or att.get("file_path")
                    or att.get("name")
                    or ""
                )
                if att_path != target:
                    continue
                return str(
                    att.get("url")
                    or att.get("source_url")
                    or att.get("original_url")
                    or ""
                )
        return ""

    def _append_image_preview(self, path, prefix):
        path = _gui_norm_path(path)
        key = f"{prefix}:{path}"
        if key in self._known_image_preview_paths:
            return
        self._known_image_preview_paths.add(key)

        def _load():
            try:
                if not os.path.exists(path):
                    self._known_image_preview_paths.discard(key)
                    return

                try:
                    src = image_file_to_data_url(path, max_bytes=8_000_000)
                except Exception:
                    src = Path(path).resolve().as_uri()

                remote_url = self._find_generated_image_url(path)
                download_href = (
                    f"{remote_url}#download"
                    if remote_url
                    else Path(path).resolve().as_uri() + "#download"
                )
                html_block = (
                    f'<a href="{html.escape(Path(path).resolve().as_uri(), quote=True)}">'
                    f'<img src="{html.escape(src, quote=True)}" '
                    'style="max-width:360px; max-height:280px; border:0; margin:0; padding:0; display:block;"/>'
                    "</a>"
                    f'<div style="font-size:11px; margin-top:2px;">'
                    f'<a href="{html.escape(download_href, quote=True)}" style="color:#2563eb; text-decoration:underline;">Download</a>'
                    "</div>"
                )
                self._output.moveCursor(QtGui.QTextCursor.End)
                self._output.insertHtml(html_block)
                self._output.insertHtml("<br/>")
                self._output.ensureCursorVisible()
            except Exception:
                self._known_image_preview_paths.discard(key)

        QtCore.QTimer.singleShot(1000, _load)

    def _add_thumb(self, path, prefix):
        path = _gui_norm_path(path)
        key = f"{prefix}:{path}"
        if key in self._known_image_paths:
            return
        self._known_image_paths.add(key)

        def _load():
            try:
                if not os.path.exists(path):
                    self._known_image_paths.discard(key)
                    return
                reader = QtGui.QImageReader(path)
                if not reader.canRead():
                    try:
                        print(
                            "[GUI][add_thumb] "
                            + _("cannot read image")
                            + " "
                            + json.dumps(
                                {
                                    "path": path,
                                    "format": (
                                        str(
                                            reader.format()
                                            .data()
                                            .decode(errors="ignore")
                                        )
                                        if reader.format()
                                        else ""
                                    ),
                                },
                                ensure_ascii=False,
                            )
                        )
                    except Exception:
                        pass
                    return
                img = reader.read()
                if img.isNull():
                    return
                pix = QtGui.QPixmap.fromImage(
                    img.scaled(
                        THUMB_SIZE_PX,
                        THUMB_SIZE_PX,
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                )
                it = QtWidgets.QListWidgetItem(
                    QtGui.QIcon(pix), f"{prefix}:{os.path.basename(path)}"
                )
                it.setToolTip(path)
                self._thumbs.addItem(it)
            except Exception:
                pass

        QtCore.QTimer.singleShot(1000, _load)

    def _add_file_item(self, path, prefix):
        path = _gui_norm_path(path)
        key = f"{prefix}:{path}"
        if key in self._known_file_paths:
            return
        self._known_file_paths.add(key)

        def _load():
            try:
                if not os.path.exists(path):
                    self._known_file_paths.discard(key)
                    return
                file_info = QtCore.QFileInfo(path)
                icon_provider = QtWidgets.QFileIconProvider()
                icon = icon_provider.icon(file_info)
                it = QtWidgets.QListWidgetItem(icon, os.path.basename(path))
                it.setToolTip(path)
                self._thumbs.addItem(it)
            except Exception:
                self._known_file_paths.discard(key)

        QtCore.QTimer.singleShot(1000, _load)

    def _open_image(self, p):
        try:
            p = _gui_norm_path(p)
            if sys.platform == "win32":
                os.startfile(p)
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", p])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", p])
        except Exception:
            pass

    def _is_audio_path(self, p):
        p = _gui_norm_path(p).lower()
        return bool(p and os.path.splitext(p)[1] in AUDIO_EXTS)

    def _append_audio_preview(self, path, prefix):
        path = _gui_norm_path(path)
        key = f"{prefix}:{path}"
        if key in self._known_file_paths:
            return
        self._known_file_paths.add(key)

        def _load():
            try:
                if not os.path.exists(path):
                    self._known_file_paths.discard(key)
                    return
                title = html.escape(os.path.basename(path), quote=True)
                file_uri = Path(path).resolve().as_uri()
                html_block = (
                    '<div style="max-width:360px; border:1px solid #ddd; border-radius:6px; padding:6px; margin-top:4px;">'
                    f'<div style="font-size:12px; margin-bottom:4px;">{title}</div>'
                    '<div style="font-size:11px; line-height:1.6;">'
                    f'<a href="audio-play:{html.escape(path, quote=True)}" style="color:#2563eb; text-decoration:underline;">Play</a>'
                    " &nbsp;"
                    f'<a href="audio-stop:" style="color:#2563eb; text-decoration:underline;">Stop</a>'
                    " &nbsp;"
                    f'<a href="{html.escape(file_uri, quote=True)}#download" style="color:#2563eb; text-decoration:underline;">Download</a>'
                    "</div>"
                    "</div>"
                )
                self._output.moveCursor(QtGui.QTextCursor.End)
                self._output.insertHtml(html_block)
                self._output.insertHtml("<br/>")
                self._output.ensureCursorVisible()
            except Exception:
                self._known_file_paths.discard(key)

        QtCore.QTimer.singleShot(1000, _load)

    def _handle_output_anchor(self, url):
        try:
            scheme = (url.scheme() or "").lower()
            if scheme == "file" and url.fragment() == "download":
                src = Path(url.toLocalFile())
                if not src.exists():
                    return

                download_dir = QtCore.QStandardPaths.writableLocation(
                    QtCore.QStandardPaths.DownloadLocation
                ) or str(Path.home() / "Downloads")
                dest_dir = Path(download_dir)
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    dest_dir = Path.home()

                target = dest_dir / src.name
                if target.exists():
                    stem, suffix = src.stem, src.suffix
                    idx = 1
                    while True:
                        candidate = dest_dir / f"{stem}_{idx}{suffix}"
                        if not candidate.exists():
                            target = candidate
                            break
                        idx += 1

                shutil.copy2(str(src), str(target))
                try:
                    self.statusBar().showMessage(
                        _("Downloaded to") + f" {target}",
                        5000,
                    )
                except Exception:
                    pass
                return

            if scheme in ("http", "https") and url.fragment() == "download":
                download_dir = QtCore.QStandardPaths.writableLocation(
                    QtCore.QStandardPaths.DownloadLocation
                ) or str(Path.home() / "Downloads")
                dest_dir = Path(download_dir)
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    dest_dir = Path.home()

                base = Path(unquote(url.path())).name or "download.png"
                if not os.path.splitext(base)[1]:
                    base += ".png"
                target = dest_dir / base
                if target.exists():
                    stem, suffix = target.stem, target.suffix
                    idx = 1
                    while True:
                        candidate = dest_dir / f"{stem}_{idx}{suffix}"
                        if not candidate.exists():
                            target = candidate
                            break
                        idx += 1

                req = Request(
                    url.toString().split("#", 1)[0], headers={"User-Agent": "uag-gui"}
                )
                with urlopen(req) as resp:
                    data = resp.read()
                with open(target, "wb") as f:
                    f.write(data)
                try:
                    self.statusBar().showMessage(
                        _("Downloaded to") + f" {target}",
                        5000,
                    )
                except Exception:
                    pass
                return

            if scheme == "uag-download":
                raw = unquote(url.toString().split(":", 1)[1])
                if raw.startswith("/") and re.match(r"^/[A-Za-z]:[\\/]", raw):
                    raw = raw[1:]
                src = Path(raw)
                if not src.exists():
                    return
                download_dir = QtCore.QStandardPaths.writableLocation(
                    QtCore.QStandardPaths.DownloadLocation
                ) or str(Path.home() / "Downloads")
                dest_dir = Path(download_dir)
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    dest_dir = Path.home()
                target = dest_dir / src.name
                if target.exists():
                    stem, suffix = src.stem, src.suffix
                    idx = 1
                    while True:
                        candidate = dest_dir / f"{stem}_{idx}{suffix}"
                        if not candidate.exists():
                            target = candidate
                            break
                        idx += 1
                shutil.copy2(str(src), str(target))
                try:
                    self.statusBar().showMessage(
                        _("Downloaded to") + f" {target}",
                        5000,
                    )
                except Exception:
                    pass
                return

            if scheme == "audio-play":
                raw = unquote(url.toString().split(":", 1)[1])
                if raw.startswith("/") and re.match(r"^/[A-Za-z]:[\\/]", raw):
                    raw = raw[1:]
                src = Path(raw)
                if not src.exists():
                    return
                try:
                    self._audio_current_path = str(src)
                    self._audio_player.setSource(QtCore.QUrl.fromLocalFile(str(src)))
                    self._audio_player.play()
                    self.statusBar().showMessage(
                        _("Playing") + f" {src.name}",
                        3000,
                    )
                except Exception:
                    pass
                return

            if scheme == "audio-stop":
                try:
                    self._audio_player.stop()
                    self.statusBar().showMessage(_("Stopped"), 2000)
                except Exception:
                    pass
                return

            if scheme in ("http", "https"):
                QtGui.QDesktopServices.openUrl(url)
                return

            p = url.toLocalFile()
            if p:
                self._open_image(p)
        except Exception:
            pass

    def _on_send(self):
        with core.human_ask_lock:
            active, q, is_password = (
                core.human_ask_active,
                core.human_ask_queue,
                core.human_ask_is_password,
            )

        if active and is_password and not self._pw_input.isVisible():
            text = self._input.toPlainText()
            self._input.clear()
            self._pw_input.setText(text)
            self._pw_input.setVisible(True)
            self._input.setVisible(False)
            self._pw_input.setFocus()
            return

        if self._pw_input.isVisible():
            text = self._pw_input.text()
            self._pw_input.clear()
        else:
            text = self._input.toPlainText()
            self._input.clear()

        if not text.strip() and not self._attached_images and not self._attached_files:
            return

        sent_images = list(self._attached_images)
        sent_files = list(self._attached_files)

        if active and q:
            is_pw = bool(is_password)
            try:
                display_log = "[SECRET]" if is_pw else text
                print(_("[REPLY] > %(text)s") % {"text": display_log})
            except Exception:
                pass

            s = core.MULTI_INPUT_SENTINEL
            q.put(text + ("\n" + s + "\n" if s not in text else ""))
        else:
            try:
                print(_("[USER] %(text)s") % {"text": text.strip()})
            except Exception:
                pass

            if (
                text.strip().startswith(":")
                and not self._attached_images
                and not self._attached_files
            ):
                core.event_queue.put({"kind": "command", "text": text.strip()})
            else:
                core.event_queue.put(
                    {
                        "kind": "gui_user",
                        "text": text,
                        "images": sent_images,
                        "files": sent_files,
                    }
                )
                if sent_images:
                    self._sent_preview_seq += 1
                    preview_prefix = f"USER:{self._sent_preview_seq}"
                    for path in sent_images:
                        self._append_image_preview(path, preview_prefix)
            self._history.append(HistoryEntry(text, sent_images, sent_files))

        self._attached_images.clear()
        self._attached_files.clear()
        self._thumbs.clear()
        self._hist_idx = -1

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QtCore.QEvent.KeyPress:
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                if event.key() == QtCore.Qt.Key_Up and self._history:
                    self._hist_idx = (
                        (self._hist_idx - 1)
                        if self._hist_idx != -1
                        else (len(self._history) - 1)
                    )
                    self._restore_history()
                    return True
                elif event.key() == QtCore.Qt.Key_Down and self._hist_idx != -1:
                    self._hist_idx = (
                        (self._hist_idx + 1)
                        if self._hist_idx < len(self._history) - 1
                        else -1
                    )
                    self._restore_history()
                    return True
        return super().eventFilter(obj, event)

    def _restore_history(self):
        self._thumbs.clear()
        self._known_image_paths.clear()
        self._known_image_preview_paths.clear()
        self._known_file_paths.clear()
        if self._hist_idx == -1:
            self._input.clear()
            self._attached_images = []
            self._attached_files = []
        else:
            ent = self._history[self._hist_idx]
            self._input.setPlainText(ent.text)
            self._attached_images = list(ent.images)
            self._attached_files = list(ent.files)
            for i, p in enumerate(ent.images):
                if p and os.path.exists(p):
                    self._add_thumb(p, f"HIST:{self._hist_idx}:{i}")
            for i, p in enumerate(ent.files):
                if p and os.path.exists(p):
                    self._add_file_item(p, f"HIST:{self._hist_idx}:{i}")

    def closeEvent(self, event):
        self._worker.stop()
        try:
            stop_background_scheduler()
        except Exception:
            pass
        self._thread.quit()
        self._thread.wait(2000)
        if os.path.exists(LOG_FILE):
            try:
                os.remove(LOG_FILE)
            except Exception:
                pass
        super().closeEvent(event)


def main():
    try:
        from .readme_util import (
            maybe_print_quickstart_on_first_run,
            maybe_print_readme_on_first_run,
        )

        maybe_print_readme_on_first_run(open_with_os=True)
        maybe_print_quickstart_on_first_run(open_with_os=True)
    except Exception:
        pass

    print(get_welcome_message())
    ensure_mcp_config_template()

    with open(LOG_FILE, "w", encoding="utf-8"):
        pass
    sys.stdout = RedirectToLog(LOG_FILE, sys.stdout)
    sys.stderr = RedirectToLog(LOG_FILE, sys.stderr)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--workdir",
        "-C",
        dest="workdir",
        help="Specify the working directory. If omitted, use the UAGENT_WORKDIR environment variable or the current directory.",
    )
    args, unknown = parser.parse_known_args()

    decision = _runtime_init.decide_workdir(
        cli_workdir=getattr(args, "workdir", None),
        env_workdir=os.environ.get("UAGENT_WORKDIR"),
    )
    _runtime_init.apply_workdir(decision)
    _runtime_init.reload_dotenv_custom()

    _runtime_init.validate_or_exit_startup_env(context="gui")

    prov = (os.environ.get("UAGENT_PROVIDER") or "azure").lower()
    model = ""

    app = QtWidgets.QApplication(sys.argv)
    try:
        if detect_lang() == "ar":
            app.setLayoutDirection(QtCore.Qt.RightToLeft)
    except Exception:
        pass
    win = MainWindow(GuiConfig(prov, model, unknown[0] if unknown else None))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
