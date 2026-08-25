"""GUI configuration helpers (split from scheckgui.py)."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from . import state


def _load_font_size_config() -> int:
    """Load font size level from config file. Returns 0/1/2."""
    if state._FONT_SIZE_CONFIG_FILE:
        try:
            p = Path(state._FONT_SIZE_CONFIG_FILE)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                level = int(data.get("font_size", 1))
                if level in (0, 1, 2):
                    return level
        except Exception:
            pass
    return 1


def _save_font_size_config(level: int) -> None:
    if state._FONT_SIZE_CONFIG_FILE:
        try:
            p = Path(state._FONT_SIZE_CONFIG_FILE)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {"font_size": level}
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
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
    images: list[str]
    files: list[str]
