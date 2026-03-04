# -*- coding: utf-8 -*-
"""gui.py - File-Buffered Extreme Stability Version"""

from __future__ import annotations

import argparse
import os
import re
import sys
import threading
from dataclasses import dataclass
from queue import Empty as QueueEmpty
from typing import Any, Dict, List, Optional

# DPI警告とクラッシュ防止
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


class ScheckWorker(QtCore.QObject):
    """LLM実行を担当するワーカー。GUIとの直接通信を最小限にする。"""

    sig_finished = QtCore.Signal()

    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.cfg = cfg
        self.tools = tools
        self.messages = []
        self._stop = threading.Event()
        self._provider = ""
        self._client = None
        self._depname = ""

    def _init_callbacks(self):
        # GUIへの通知は行わず、coreの状態のみ更新
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
        """メインループ。出力は標準の stdout/stderr に出す。"""
        try:
            self._init_callbacks()

            # Provider/client/model は util_make_client 側で一貫して決める。
            self._provider, self._client, self._depname = util_make_client(core)
            print(
                "[INFO] "
                + _("LLM provider = %(provider)s") % {"provider": self._provider}
            )
            print(
                "[INFO] "
                + _("model(deployment) = %(depname)s") % {"depname": self._depname}
            )
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

            # 長期記憶の読み込み (unified)
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

                # 互換: 共有メモが有効な場合のみ INFO を出す
                if flags.get("shared_enabled"):
                    print("[INFO] " + _("Loaded shared long-term memory."))

                # 互換: 追加された system message をすべて log に残す
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
                        handle_command(
                            ev.get("text", ""),
                            core=core,
                            tools=tools,
                            messages=self.messages,
                            run_llm_rounds_fn=util_run_llm_rounds,
                            client=self._client,
                            depname=self._depname,
                        )

                    elif kind == "exit":
                        break

                except QueueEmpty:
                    continue

        finally:
            self.sig_finished.emit()

    def stop(self):
        self._stop.set()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.cfg = cfg

        self.setWindowTitle("uagent")

        # Layout
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self.history = QtWidgets.QTextBrowser()
        self.history.setOpenExternalLinks(True)
        layout.addWidget(self.history)

        self.input = DropInput()
        layout.addWidget(self.input)

        bottom = QtWidgets.QHBoxLayout()
        layout.addLayout(bottom)

        self.btn_send = QtWidgets.QPushButton(_("Send"))
        self.btn_stop = QtWidgets.QPushButton(_("Stop"))
        bottom.addWidget(self.btn_send)
        bottom.addWidget(self.btn_stop)

        self.btn_send.clicked.connect(self.on_send)
        self.btn_stop.clicked.connect(self.on_stop)
        self.input.sig_files_dropped.connect(self.on_files_dropped)

        # Worker thread
        self.thread = QtCore.QThread()
        self.worker = ScheckWorker(cfg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.sig_finished.connect(self.thread.quit)
        self.worker.sig_finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start
        self.thread.start()

    def closeEvent(self, e):
        try:
            self.worker.stop()
        finally:
            return super().closeEvent(e)

    def _append_history(self, text: str):
        # minimal, robust
        self.history.append(text)

    def on_files_dropped(self, paths: List[str]):
        # Show dropped files in input
        self.input.appendPlainText("\n".join(paths))

    def on_send(self):
        text = (self.input.toPlainText() or "").strip()
        if not text:
            return
        # enqueue command
        core.event_queue.put({"kind": "command", "text": text})
        self._append_history(f"<b>You:</b> {QtGui.QGuiApplication.escape(text)}")
        self.input.clear()

    def on_stop(self):
        core.event_queue.put({"kind": "exit"})


def _parse_args(argv: List[str]) -> GuiConfig:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="", help="override provider")
    p.add_argument("--model", default="", help="override model")
    p.add_argument("--file", default=None, help="initial file")
    ns = p.parse_args(argv)
    return GuiConfig(provider=ns.provider, model=ns.model, initial_file=ns.file)


def main(argv: Optional[List[str]] = None):
    argv = list(sys.argv[1:] if argv is None else argv)

    ensure_mcp_config_template()

    # Resolve workdir / init
    _runtime_init.init_workdir(core)

    # Startup env validation (aggregated)
    _runtime_init.validate_or_exit_startup_env(context="gui")

    banner = _runtime_init.build_startup_banner(core)
    print(banner)

    cfg = _parse_args(argv)

    app = QtWidgets.QApplication([])
    w = MainWindow(cfg)
    w.resize(960, 720)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
