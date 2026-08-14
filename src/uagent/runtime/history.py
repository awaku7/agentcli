"""Pure history/output helpers extracted from core."""

from __future__ import annotations


import json
import os
from typing import Any, Callable


def rewrite_jsonl_log(
    log_path: str,
    messages: list[dict[str, Any]],
    response_records: list[dict[str, Any]],
    mask_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> str:
    """Rewrite a masked conversation log with preserved metadata."""
    log_dir = os.path.dirname(log_path) or "."
    backup_dir = os.path.join(log_dir, ".backup")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, os.path.basename(log_path) + ".org")
    try:
        if os.path.exists(log_path):
            with open(log_path, "rb") as source, open(backup_path, "wb") as target:
                target.write(source.read())
    except Exception:
        pass
    tmp_path = log_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as stream:
        for item in messages:
            try:
                stream.write(json.dumps(mask_fn(item), ensure_ascii=False) + "\n")
            except Exception:
                continue
        for record in response_records:
            try:
                stream.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
            except Exception:
                continue
    os.replace(tmp_path, log_path)
    return log_path


def truncate_output(label: str, text: str, limit: int = 400_000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n[{label} truncated: {omitted} chars omitted]"
