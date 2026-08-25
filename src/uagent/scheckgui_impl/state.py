"""Shared mutable state for the uagent GUI (split from scheckgui.py)."""

from __future__ import annotations

import io
import threading
from typing import Optional

# In-memory log buffer (thread-safe via _log_lock)
_log_buffer: "io.StringIO" = io.StringIO()
_log_lock = threading.Lock()

# Font size level: 0=small, 1=medium, 2=large
_FONT_SIZE_LEVEL = 1
_UI_FONT_SIZES = {0: 9, 1: 10, 2: 12}
_MONO_FONT_SIZES = {0: 9, 1: 10, 2: 12}
_UI_FONT_SIZES_MAC = {0: 11, 1: 13, 2: 15}
_FONT_SIZE_NAMES = {0: "small", 1: "medium", 2: "large"}
_FONT_SIZE_CONFIG_FILE: Optional[str] = None
