# -*- coding: utf-8 -*-
"""GUI entry point.

This project historically had two GUI implementations:
- repository-root `scheckgui.py` (launcher)
- `uagent.scheckgui` (full-featured GUI implementation)

The launcher imports `uagent.gui.main`, so this module exposes the real GUI
`main()` and also supports ``python -m uagent.gui`` directly.
"""

from __future__ import annotations

from .scheckgui import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
