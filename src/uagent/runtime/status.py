"""Pure status-label normalization shared by frontends."""

from __future__ import annotations

import os


def normalize_status_label(busy: bool, label: str = "") -> str:
    """Return the display label shared by CLI, GUI, and Web status views."""
    if busy and label == "LLM":
        reasoning = (os.environ.get("UAGENT_REASONING") or "").strip().lower()
        if reasoning in {"auto", "minimal", "low", "medium", "high", "xhigh", "max"}:
            return f"LLM:{reasoning}"
    return label
