# -*- coding: utf-8 -*-
"""scheckgui.py - GUI implementation (split into scheckgui_impl package).

This module preserves the ``uagent.scheckgui`` import surface used by
``uagent.gui`` and the ``uagg`` entry point.  PySide6 availability is checked
here at import time (same behavior as the original single-file module); the
implementation lives in ``scheckgui_impl/``.
"""

from __future__ import annotations

import os
import sys

# DPI warnings and crash avoidance (must run before importing PySide6)
os.environ["QT_LOGGING_RULES"] = (
    "qt.qpa.window=false;qt.text.font.db=false;qt.multimedia.ffmpeg=false"
)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Auto-install / reinstall PySide6 if missing or broken
from ._pip_auto import install_with_status as _install_pyside

if not _install_pyside("PySide6", "PySide6", verify_submodule="PySide6.QtCore"):
    from .i18n import _ as _i18n_early

    print(_i18n_early("PySide6 is required for GUI mode."), file=sys.stderr)
    sys.exit(1)

from .scheckgui_impl.state import (
    _FONT_SIZE_CONFIG_FILE,
    _FONT_SIZE_LEVEL,
    _FONT_SIZE_NAMES,
    _MONO_FONT_SIZES,
    _UI_FONT_SIZES,
    _UI_FONT_SIZES_MAC,
    _log_buffer,
    _log_lock,
)
from .scheckgui_impl.icons import (
    _make_attach_icon,
    _make_close_icon,
    _make_detail_icon,
    _make_font_icon,
    _make_genre_icon,
    _make_help_icon,
    _make_mode_icon,
    _make_reasoning_icon,
    _make_send_icon,
    _make_stop_icon,
    _make_tools_icon,
    _make_view_icon,
    _menu_icon_color,
    _paint_icon_attach,
    _paint_icon_send,
)
from .scheckgui_impl.config import (
    GuiConfig,
    HistoryEntry,
    _load_font_size_config,
    _save_font_size_config,
)
from .scheckgui_impl.widgets import (
    DropInput,
    DropOutput,
    DropThumbs,
    RedirectToLog,
    _gui_norm_path,
)
from .scheckgui_impl.worker import ScheckWorker, _run_lifecycle
from .scheckgui_impl.mainwindow import MainWindow
from .scheckgui_impl.theme import _GUI_STYLESHEET, _is_high_contrast
from .scheckgui_impl.main import main

__all__ = [
    "DropInput",
    "DropOutput",
    "DropThumbs",
    "GuiConfig",
    "HistoryEntry",
    "MainWindow",
    "RedirectToLog",
    "ScheckWorker",
    "_FONT_SIZE_CONFIG_FILE",
    "_FONT_SIZE_LEVEL",
    "_FONT_SIZE_NAMES",
    "_GUI_STYLESHEET",
    "_MONO_FONT_SIZES",
    "_UI_FONT_SIZES",
    "_UI_FONT_SIZES_MAC",
    "_is_high_contrast",
    "_load_font_size_config",
    "_log_buffer",
    "_log_lock",
    "_make_attach_icon",
    "_make_close_icon",
    "_make_detail_icon",
    "_make_font_icon",
    "_make_genre_icon",
    "_make_help_icon",
    "_make_mode_icon",
    "_make_reasoning_icon",
    "_make_send_icon",
    "_make_stop_icon",
    "_make_tools_icon",
    "_make_view_icon",
    "_menu_icon_color",
    "_paint_icon_attach",
    "_paint_icon_send",
    "_run_lifecycle",
    "_save_font_size_config",
    "main",
    "_gui_norm_path",
]


if __name__ == "__main__":
    main()
