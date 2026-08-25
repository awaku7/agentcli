"""GUI widgets (split from scheckgui.py)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets
from ..i18n import _
from .state import _log_lock


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
    def __init__(self, buffer: "io.StringIO", original_stream):
        self.buffer = buffer
        self.original_stream = original_stream

    def write(self, data: str):
        try:
            with _log_lock:
                self.buffer.write(data)
        except Exception:
            pass

    def flush(self):
        return


class DropInput(QtWidgets.QPlainTextEdit):
    sig_files_dropped = QtCore.Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QtGui.QTextOption.WordWrap)
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
        self.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.setWordWrapMode(QtGui.QTextOption.WordWrap)

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
