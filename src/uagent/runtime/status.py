"""Pure status-label normalization shared by frontends."""

from __future__ import annotations

import os


_FOUNDRY_LOCAL_STATUS_PREFIX = "LLM:Foundry:"


def normalize_status_label(busy: bool, label: str = "") -> str:
    """Return the display label shared by CLI, GUI, and Web status views."""
    # Foundry Local emits provider-specific phase labels from its progress
    # observer. Keep those phases internal and expose the same provider-neutral
    # LLM status used by other providers. Provider diagnostics remain available
    # through UAGENT_DEBUG_FOUNDRY_LOCAL.
    is_foundry_local_status = label.startswith(_FOUNDRY_LOCAL_STATUS_PREFIX)
    if is_foundry_local_status:
        label = "LLM"

    if busy and label == "LLM":
        reasoning = (os.environ.get("UAGENT_REASONING") or "").strip().lower()
        if reasoning in {"auto", "minimal", "low", "medium", "high", "xhigh", "max"}:
            return f"LLM:{reasoning}"
    return label
