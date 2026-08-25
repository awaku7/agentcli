"""GUI theme constants (split from scheckgui.py)."""

from __future__ import annotations

import sys

from PySide6 import QtGui, QtWidgets


def _is_high_contrast() -> bool:
    """Detect Windows high contrast mode (or equivalent accessibility setting)."""
    # Windows: use SystemParametersInfo SPI_GETHIGHCONTRAST
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class HIGHCONTRASTW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("dwFlags", wintypes.DWORD),
                    ("lpszDefaultScheme", wintypes.LPWSTR),
                ]

            hc = HIGHCONTRASTW()
            hc.cbSize = ctypes.sizeof(HIGHCONTRASTW)
            SPI_GETHIGHCONTRAST = 0x0042
            if ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETHIGHCONTRAST,
                ctypes.sizeof(HIGHCONTRASTW),
                ctypes.byref(hc),
                0,
            ):
                HCF_HIGHCONTRASTON = 0x00000001
                if (hc.dwFlags & HCF_HIGHCONTRASTON) != 0:
                    return True
        except Exception:
            pass

    # Cross-platform fallback: check palette contrast
    try:
        palette = QtWidgets.QApplication.palette()
        win = palette.color(QtGui.QPalette.Window)
        win_text = palette.color(QtGui.QPalette.WindowText)

        def _lum(c):
            return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()

        diff = abs(_lum(win) - _lum(win_text))
        # Normal themes ~50-120, high contrast >200 (pure black/white = 255)
        return diff > 200
    except Exception:
        pass

    return False


_GUI_STYLESHEET = """
    QMainWindow {
        background-color: #f8f9fa;
    }
    QPlainTextEdit, QTextBrowser {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 8px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QPlainTextEdit:focus, QTextBrowser:focus {
        border-color: #2563eb;
    }
    QPushButton {
        background-color: #2563eb;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 6px 16px;
        font-weight: 600;
        min-height: 24px;
    }
    QPushButton:hover {
        background-color: #1d4ed8;
    }
    QPushButton:pressed {
        background-color: #1e40af;
    }
    QPushButton:disabled {
        background-color: #93c5fd;
        color: #dbeafe;
    }
    QLineEdit {
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 6px 10px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QLineEdit:focus {
        border-color: #2563eb;
    }
    QListWidget {
        background-color: #f8f9fa;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 4px;
    }
    QStatusBar {
        background-color: #f1f5f9;
        border-top: 1px solid #e2e8f0;
        padding: 2px 8px;
        font-size: 11px;
        color: #475569;
    }
    QMenuBar {
        background-color: #f8f9fa;
        border-bottom: 1px solid #e5e7eb;
        padding: 2px;
    }
    QMenuBar::item {
        padding: 6px 16px;
        border-radius: 4px;
    }
    QMenuBar::item:selected {
        background-color: #e2e8f0;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 4px;
    }
    QMenu::item {
        padding: 6px 24px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #2563eb;
        color: white;
    }
    QLabel {
        color: #374151;
    }
"""
