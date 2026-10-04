"""Pure prompt formatting helpers shared by CLI/Web/GUI frontends."""

from __future__ import annotations


def format_prompt(
    *,
    busy: bool,
    label: str,
    cwd_name: str,
    reasoning_label: str = "",
    background_jobs: int = 0,
) -> str:
    if busy:
        return f"[BUSY:{label}] > " if label else "[BUSY] > "
    badge = f"[bg:{background_jobs}]" if background_jobs > 0 else ""
    if reasoning_label:
        return f"{cwd_name}[{reasoning_label}]{badge}> "
    return f"{cwd_name}{badge}> "
