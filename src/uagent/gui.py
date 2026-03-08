# -*- coding: utf-8 -*-
"""gui.py

GUI entry point.

This project historically had two GUI implementations:
- repository-root `scheckgui.py` (launcher)
- `uagent.scheckgui` (full-featured GUI implementation)

The launcher imports `uagent.gui.main`, so this module should simply expose the
real GUI `main()`.

"""

from __future__ import annotations

from .scheckgui import main

__all__ = ["main"]
