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

# DPI警告とクラッシュ防止
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6 import QtCore, QtGui, QtWidgets

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
LOG_FILE = "gui_worker_session.log"



class RedirectToLog:
    def __init__(self, path: str, original_stream):
        self.path = path
        self.original_stream = original_stream

    def write(self, data: str):
        # Write to file (append)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(data)
        except Exception:
            pass
        # Write to original stream (console)
        try:
            self.original_stream.write(data)
            self.original_stream.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass

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
        # GUIへの通知は行わず、coreの状態のみ更新（ログファイルに書かれる）
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
        """メインループ。出力は既にグローバルにファイルへリダイレクトされている。"""
        try:
            # 既にグローバルでリダイレクトされているが、個別のスレッドでも
            # sys.stdout / sys.stderr を明示的に参照して処理を継続する
            self._init_callbacks()

            # Provider/client/model は util_make_client 側で一貫して決める。
            self._provider, self._client, self._depname = util_make_client(core)
            print(f"[INFO] LLM provider = {self._provider}")
            print(f"[INFO] model(deployment) = {self._depname}")
            if (
                self._provider == "openrouter"
                and (self._depname or "").strip() == "openrouter/auto"
            ):
                raw_fb = (
                    os.environ.get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
                ).strip()
                if raw_fb:
                    print("[INFO] open router fallback models enabled")
            # NOTE(Mode A): base_url/api_version and Responses/ChatCompletions mode
            # are already shown by runtime_init.build_startup_banner() in gui.main().

            self.messages = build_initial_messages(core=core)

            # 長期記憶の読み込み (unified)
            from .tools import long_memory as personal_long_memory
            from .tools import shared_memory

            print("[INFO] 長期記憶を読み込みました。")

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
                    print("[INFO] 共有長期記憶を読み込みました。")

                # 互換: 追加された system message をすべて log に残す
                for m in self.messages[before_len:]:
                    core.log_message(m)

            except Exception as e:
                print(f"[WARN] 共有長期記憶の読み込み中に例外が発生しました: {e}")

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
                            use_responses_api = os.environ.get(
                                "UAGENT_RESPONSES", ""
                            ).lower() in (
                                "1",
                                "true",
                            )
                            prov = (os.environ.get("UAGENT_PROVIDER") or "").lower()
                            allow_multimodal = use_responses_api and prov in (
                                "azure",
                                "openai",
                            )

                            if allow_multimodal:
                                # Build a multimodal user message (text + image_url(data URL)).
                                # Safety: enforce max 10MB per image.
                                parts: List[Dict[str, Any]] = [
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
                                        # If an image can't be embedded, fall back to text note.
                                        parts.append(
                                            {
                                                "type": "text",
                                                "text": f"[WARN] 画像添付に失敗しました: {p} ({type(e).__name__}: {e})",
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

                            # Fallback: previous behavior (analyze_image tool -> text injection)
                            for p in ev.get("images", []):
                                if os.path.isfile(p):
                                    core.set_status(True, "analyze_image")
                                    res = self.tools.run_tool(
                                        "analyze_image", {"image_path": p}
                                    )
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
                        # 既にリダイレクト下にあるため、ここでの print_exc は log_stream に行くが、
                        # 念のためファイルに直接書く。
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
            self.sig_finished.emit()

    def stop(self):
        self._stop.set()


class MainWindow(QtWidgets.QMainWindow):

    _URL_RE = re.compile(r"\b(https?://[^\s<>\"']+|www\.[^\s<>\"']+)", re.IGNORECASE)

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    @classmethod
    def _linkify_html(cls, text: str) -> str:
        """Convert plain text to safe HTML with clickable links.

        - Escapes HTML first.
        - Replaces URLs with <a href=...>.
        - Preserves newlines (using <br>).
        """

        escaped = cls._escape_html(text or "")

        def _repl(m: re.Match) -> str:
            raw = m.group(0)
            href = raw
            if raw.lower().startswith("www."):
                href = "https://" + raw
            return f'<a href="{href}" style="color:#2563eb; text-decoration: underline;">{raw}</a>'

        linked = cls._URL_RE.sub(_repl, escaped)
        return linked.replace("\n", "<br>")

    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.setWindowTitle("uag GUI (Extreme Stability)")
        self.resize(1100, 850)
        self._attached_images = []
        self._history = []
        self._hist_idx = -1
        self._log_pos = 0
        self._known_image_paths = set()
        self._ansi_re = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

        # UI Layout
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self._output = QtWidgets.QTextBrowser()
        self._output.setReadOnly(True)
        self._output.setOpenExternalLinks(True)
        self._output.setOpenLinks(True)
        self._output.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        )
        layout.addWidget(self._output, 1)

        self._thumbs = QtWidgets.QListWidget()
        self._thumbs.setViewMode(QtWidgets.QListView.IconMode)
        self._thumbs.setFixedHeight(140)
        self._thumbs.setIconSize(QtCore.QSize(THUMB_SIZE_PX, THUMB_SIZE_PX))
        self._thumbs.itemDoubleClicked.connect(
            lambda it: self._open_image(it.toolTip())
        )
        layout.addWidget(self._thumbs)

        input_row = QtWidgets.QHBoxLayout()
        self._input = DropInput()
        self._input.setFixedHeight(100)
        self._input.installEventFilter(self)
        self._input.sig_files_dropped.connect(self._on_files_dropped)
        input_row.addWidget(self._input, 1)

        self._pw_input = QtWidgets.QLineEdit()
        self._pw_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self._pw_input.setFixedHeight(100)
        self._pw_input.setVisible(False)
        self._pw_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._pw_input, 1)

        self._btn = QtWidgets.QPushButton("Send")
        self._btn.setFixedWidth(80)
        self._btn.clicked.connect(self._on_send)
        input_row.addWidget(self._btn)
        layout.addLayout(input_row)

        self._status_label = QtWidgets.QLabel(" [STATE] IDLE")
        self.statusBar().addPermanentWidget(self._status_label)

        # workdir display (updated periodically to follow os.chdir())
        self._workdir_label = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self._workdir_label)
        self._last_workdir = ""

        # Log Monitor Timer
        self._monitor_timer = QtCore.QTimer(self)
        self._monitor_timer.timeout.connect(self._update_ui_from_log)
        self._monitor_timer.start(200)

        # Worker Thread
        self._thread = QtCore.QThread()
        self._worker = ScheckWorker(cfg)
        self._worker.moveToThread(self._thread)
        self._worker.sig_finished.connect(self._thread.quit)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

        # Shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(
            self._on_send
        )
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Enter"), self).activated.connect(
            self._on_send
        )

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

                # 状態情報を抽出
                states = re.findall(r"\[STATE\]\s+(\w+)(?:\s+\[(.*?)\])?", clean_text)
                if states:
                    last_st, last_lb = states[-1]
                    self._status_label.setText(
                        f" [STATE] {last_st}" + (f" [{last_lb}]" if last_lb else "")
                    )

                # 画像パス抽出
                paths = extract_image_paths(clean_text)
                for p in paths:
                    if p and os.path.exists(p):
                        self._add_thumb(p, "GEN")

                # [STATE] 行などをフィルタリングして表示用テキストを作成
                display_lines = []
                for line in clean_text.splitlines(keepends=True):
                    s = line.strip()
                    if s.startswith("[STATE]"):
                        continue
                    # Suppress CLI-only multiline guidance in GUI
                    if "複数行" in line:
                        continue
                    display_lines.append(line)
                display_text = "".join(display_lines)

                if display_text:
                    self._output.moveCursor(QtGui.QTextCursor.End)
                    self._output.insertHtml(self._linkify_html(display_text))
                    self._output.ensureCursorVisible()

            # human_ask 状態の同期
            with core.human_ask_lock:
                active = core.human_ask_active
                is_password = core.human_ask_is_password

            # パスワードモードなら QLineEdit を表示、それ以外は QPlainTextEdit を表示
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
                    "パスワードを入力..."
                    if is_password
                    else "human_ask への回答を入力..."
                )
                self._input.setPlaceholderText(msg)
                self._pw_input.setPlaceholderText(msg)
            else:
                self._input.setPlaceholderText("メッセージを入力...")

            # workdir display update (follow os.chdir())
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
                    it = QtWidgets.QListWidgetItem(
                        QtGui.QIcon(pix), f"{prefix}:{os.path.basename(path)}"
                    )
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
            active, q, is_password = (
                core.human_ask_active,
                core.human_ask_queue,
                core.human_ask_is_password,
            )

        # パスワード要求中なのに通常の入力欄で送信しようとした場合、安全のため入力を移し替えて中断する
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
            # human_ask への回答時
            is_pw = bool(is_password)
            try:
                # 画面上のログ(履歴)に表示されるテキスト
                display_log = "[SECRET]" if is_pw else text
                print(f"[REPLY] > {display_log}")
            except Exception:
                pass

            s = core.MULTI_INPUT_SENTINEL
            # 内部キュー(LLM)には生のテキストを渡すが、画面表示には使われない
            # センチネル自体の改行は維持
            q.put(text + ("\n" + s + "\n" if s not in text else ""))
        else:
            try:
                print(f"[USER] {text.strip()}")
            except Exception:
                pass

            core.event_queue.put(
                {
                    "kind": "gui_user",
                    "text": text,
                    "images": list(self._attached_images),
                }
            )
            self._history.append(HistoryEntry(text, list(self._attached_images)))

        self._attached_images.clear()
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
    # 初回だけ README / QUICKSTART を表示（pip/wheel には post-install フックが無いので起動時に表示する）
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
    # Redirect stdout/stderr to LOG_FILE
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        pass  # clear log file
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

    # Workdir init (unified)
    decision = _runtime_init.decide_workdir(
        cli_workdir=getattr(args, "workdir", None),
        env_workdir=os.environ.get("UAGENT_WORKDIR"),
    )
    _runtime_init.apply_workdir(decision)
    banner = _runtime_init.build_startup_banner(
        core=core,
        workdir=decision.chosen_expanded,
        workdir_source=decision.chosen_source,
    )
    print(banner, end="")

    prov = (os.environ.get("UAGENT_PROVIDER") or "azure").lower()
    model = ""

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(GuiConfig(prov, model, unknown[0] if unknown else None))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
