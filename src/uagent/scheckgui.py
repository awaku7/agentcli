# -*- coding: utf-8 -*-
"""scheckgui.py - File-Buffered Extreme Stability Version"""

from __future__ import annotations

import argparse
import os
import re
import sys
import threading
from dataclasses import dataclass
from queue import Empty as QueueEmpty
from typing import Any, Dict, List, Optional

# DPI warnings and crash avoidance
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6 import QtCore, QtGui, QtWidgets

from .i18n import _

from . import core as core
from . import tools
from .welcome import get_welcome_message
from . import runtime_init as _runtime_init

from .util_tools import (
    extract_image_paths,
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
from .util_providers import make_client as util_make_client
from .tools.context import ToolCallbacks

try:
    from .tools.mcp_servers_shared import ensure_mcp_config_template
except ImportError:

    def ensure_mcp_config_template():
        pass  # type: ignore


THUMB_SIZE_PX = 96
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
LOG_FILE = "gui_worker_session.log"


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
    images: List[str]


class DropInput(QtWidgets.QPlainTextEdit):
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


class ScheckWorker(QtCore.QObject):
    """Worker that runs the LLM loop."""

    sig_finished = QtCore.Signal()

    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.cfg = cfg
        self.tools = tools
        self.messages: List[Dict[str, Any]] = []
        self._stop = threading.Event()
        self._provider = ""
        self._client = None
        self._depname = ""

    def _init_callbacks(self):
        cb = ToolCallbacks(
            set_status=core.set_status,
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

            # Provider/client/model are decided by util_make_client.
            self._provider, self._client, self._depname = util_make_client(core)
            print("[INFO] " + _("LLM provider = %(provider)s") % {"provider": self._provider})
            print("[INFO] " + _("model(deployment) = %(depname)s") % {"depname": self._depname})
            if (
                self._provider == "openrouter"
                and (self._depname or "").strip() == "openrouter/auto"
            ):
                raw_fb = (os.environ.get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or "").strip()
                if raw_fb:
                    print("[INFO] " + _("OpenRouter fallback models enabled."))

            self.messages = build_initial_messages(core=core)

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
                    + _("Exception occurred while loading shared long-term memory: %(err)s")
                    % {"err": e}
                )

            while not self._stop.is_set():
                try:
                    ev = core.event_queue.get(timeout=0.5)
                    kind = ev.get("kind")

                    if kind == "command":
                        handle_command(
                            ev.get("text", ""),
                            self.messages,
                            self._client,
                            self._depname,
                            core=core,
                        )
                    elif kind in ("user", "timer", "gui_user"):
                        text = ev.get("text", "")

                        if kind == "gui_user":
                            use_responses_api = (os.environ.get("UAGENT_RESPONSES", "") or "").lower() in (
                                "1",
                                "true",
                            )
                            prov = (os.environ.get("UAGENT_PROVIDER") or "").lower()
                            allow_multimodal = use_responses_api and prov in ("azure", "openai")

                            if allow_multimodal:
                                parts: List[Dict[str, Any]] = [
                                    {"type": "text", "text": text.strip()}
                                ]

                                for p in ev.get("images", []):
                                    if not os.path.isfile(p):
                                        continue
                                    try:
                                        data_url = image_file_to_data_url(p, max_bytes=10_000_000)
                                        parts.append({"type": "image_url", "image_url": {"url": data_url}})
                                    except Exception as e:
                                        parts.append(
                                            {
                                                "type": "text",
                                                "text": "[WARN] "
                                                + (
                                                    _("Failed to attach image: %(path)s (%(etype)s: %(err)s)")
                                                    % {"path": p, "etype": type(e).__name__, "err": e}
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
                                    res = self.tools.run_tool("analyze_image", {"image_path": p})
                                    text += f"\n[Attached Image] {p}\n{res}"

                        if text.strip():
                            m = {"role": "user", "content": text.strip()}
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

                except QueueEmpty:
                    continue
                except Exception:
                    try:
                        with open(LOG_FILE, "a", encoding="utf-8", buffering=1) as log_f:
                            log_f.write("[ERROR] Worker exception:\n")
                            import traceback

                            traceback.print_exc(file=log_f)
                    except Exception:
                        pass
                    continue
        finally:
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
            + "</div><hr>"
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
        self._attached_images: List[str] = []
        self._history: List[HistoryEntry] = []
        self._hist_idx = -1
        self._log_pos = 0
        self._known_image_paths: set[str] = set()
        self._ansi_re = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self._output = DropOutput()
        self._output.setReadOnly(True)
        self._output.setOpenExternalLinks(True)
        self._output.setOpenLinks(True)
        self._output.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        layout.addWidget(self._output, 1)

        self._thumbs = QtWidgets.QListWidget()
        self._thumbs.setViewMode(QtWidgets.QListView.IconMode)
        self._thumbs.setFixedHeight(140)
        self._thumbs.setIconSize(QtCore.QSize(THUMB_SIZE_PX, THUMB_SIZE_PX))
        self._thumbs.itemDoubleClicked.connect(lambda it: self._open_image(it.toolTip()))
        layout.addWidget(self._thumbs)

        input_row = QtWidgets.QHBoxLayout()
        self._input = DropInput()
        self._input.setFixedHeight(100)
        self._input.installEventFilter(self)
        self._input.sig_files_dropped.connect(self._on_files_dropped)
        self._output.sig_files_dropped.connect(self._on_files_dropped)
        input_row.addWidget(self._input, 1)

        self._pw_input = QtWidgets.QLineEdit()
        self._pw_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self._pw_input.setFixedHeight(100)
        self._pw_input.setVisible(False)
        self._pw_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._pw_input, 1)

        self._btn = QtWidgets.QPushButton(_("Send"))
        self._btn.setFixedWidth(80)
        self._btn.clicked.connect(self._on_send)
        input_row.addWidget(self._btn)
        layout.addLayout(input_row)

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

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(self._on_send)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Enter"), self).activated.connect(self._on_send)

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

            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self).activated.connect(lambda: self._set_reasoning("auto"))
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self).activated.connect(lambda: self._set_verbosity("2"))
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
            print(f"[mode] reasoning={new_mode}")
        except Exception:
            print(":r [0|1|2|3|auto|minimal|xhigh]  (0=off, 1=low, 2=medium, 3=high; auto/minimal/xhigh)")
        self._update_mode_label()

    def _set_verbosity(self, arg: str) -> None:
        try:
            new_mode = apply_verbosity_arg(arg)
            print(f"[mode] verbosity={new_mode}")
        except Exception:
            print(":v [0|1|2|3]  (0=off, 1=low, 2=medium, 3=high; no arg=cycle)")
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
                    out_parts: List[str] = []
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
                    self._status_label.setText(f" [STATE] {last_st}" + (f" [{last_lb}]" if last_lb else ""))

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
                        self._provider_model_text = ((ptxt + " " + mtxt).strip() if ptxt else mtxt)
                    if getattr(self, "_provider_model_text", ""):
                        self._provider_model_label.setText(" " + self._provider_model_text)
                except Exception:
                    pass

                paths = extract_image_paths(clean_text)
                for p in paths:
                    if p and os.path.exists(p):
                        self._add_thumb(p, "GEN")

                display_lines = []
                for line in clean_text.splitlines(keepends=True):
                    s = line.strip()
                    if s.startswith("[STATE]"):
                        continue
                    if "multiline" in (line or "").lower():
                        continue
                    display_lines.append(line)
                display_text = "".join(display_lines)

                if display_text:
                    self._output.moveCursor(QtGui.QTextCursor.End)
                    self._output.insertHtml(self._linkify_html(display_text))
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
                msg = _("Enter password...") if is_password else _("Enter response for human_ask...")
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

    def _on_files_dropped(self, ps):
        for p in ps:
            if os.path.splitext(p)[1].lower() in IMAGE_EXTS:
                self._attached_images.append(p)
                self._add_thumb(p, "ATT")

    def _add_thumb(self, path, prefix):
        if path in self._known_image_paths:
            return
        self._known_image_paths.add(path)

        def _load():
            try:
                if not os.path.exists(path):
                    self._known_image_paths.discard(path)
                    return
                reader = QtGui.QImageReader(path)
                if not reader.canRead():
                    return
                img = reader.read()
                if not img.isNull():
                    pix = QtGui.QPixmap.fromImage(
                        img.scaled(
                            THUMB_SIZE_PX,
                            THUMB_SIZE_PX,
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation,
                        )
                    )
                    it = QtWidgets.QListWidgetItem(QtGui.QIcon(pix), f"{prefix}:{os.path.basename(path)}")
                    it.setToolTip(path)
                    self._thumbs.addItem(it)
            except Exception:
                pass

        QtCore.QTimer.singleShot(1000, _load)

    def _open_image(self, p):
        try:
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

    def _on_send(self):
        with core.human_ask_lock:
            active, q, is_password = (core.human_ask_active, core.human_ask_queue, core.human_ask_is_password)

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

        if not text.strip() and not self._attached_images:
            return

        if active and q:
            is_pw = bool(is_password)
            try:
                display_log = "[SECRET]" if is_pw else text
                print(f"[REPLY] > {display_log}")
            except Exception:
                pass

            s = core.MULTI_INPUT_SENTINEL
            q.put(text + ("\n" + s + "\n" if s not in text else ""))
        else:
            try:
                print(f"[USER] {text.strip()}")
            except Exception:
                pass

            if text.strip().startswith(":") and not self._attached_images:
                core.event_queue.put({"kind": "command", "text": text.strip()})
            else:
                core.event_queue.put({"kind": "gui_user", "text": text, "images": list(self._attached_images)})
            self._history.append(HistoryEntry(text, list(self._attached_images)))

        self._attached_images.clear()
        self._thumbs.clear()
        self._hist_idx = -1

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QtCore.QEvent.KeyPress:
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                if event.key() == QtCore.Qt.Key_Up and self._history:
                    self._hist_idx = (self._hist_idx - 1) if self._hist_idx != -1 else (len(self._history) - 1)
                    self._restore_history()
                    return True
                elif event.key() == QtCore.Qt.Key_Down and self._hist_idx != -1:
                    self._hist_idx = (self._hist_idx + 1) if self._hist_idx < len(self._history) - 1 else -1
                    self._restore_history()
                    return True
        return super().eventFilter(obj, event)

    def _restore_history(self):
        self._thumbs.clear()
        if self._hist_idx == -1:
            self._input.clear()
            self._attached_images = []
        else:
            ent = self._history[self._hist_idx]
            self._input.setPlainText(ent.text)
            self._attached_images = list(ent.images)
            for p in ent.images:
                self._add_thumb(p, "ATT")

    def closeEvent(self, event):
        self._worker.stop()
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
        from .readme_util import maybe_print_quickstart_on_first_run, maybe_print_readme_on_first_run

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
        help="動作ディレクトリを指定します。指定しない場合は UAGENT_WORKDIR 環境変数、またはカレントディレクトリを使用します。",
    )
    args, unknown = parser.parse_known_args()

    decision = _runtime_init.decide_workdir(cli_workdir=getattr(args, "workdir", None), env_workdir=os.environ.get("UAGENT_WORKDIR"))
    _runtime_init.apply_workdir(decision)

    _runtime_init.validate_or_exit_startup_env(context="gui")

    banner = _runtime_init.build_startup_banner(core=core, workdir=decision.chosen_expanded, workdir_source=decision.chosen_source)
    print(banner, end="")

    prov = (os.environ.get("UAGENT_PROVIDER") or "azure").lower()
    model = ""

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(GuiConfig(prov, model, unknown[0] if unknown else None))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
