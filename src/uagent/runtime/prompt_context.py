"""Pure prompt formatting helpers shared by CLI/Web/GUI frontends."""

from __future__ import annotations


def format_prompt(*, busy: bool, label: str, cwd_name: str, reasoning_label: str = "") -> str:
    if busy:
        return f"[BUSY:{label}] > " if label else "[BUSY] > "
    if reasoning_label:
        return f"{cwd_name}[{reasoning_label}]> "
    return f"{cwd_name}> "
