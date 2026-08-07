"""Shared attachment normalization for local CLI/GUI clients.

Web and A2A have their own transport-specific handling and intentionally do
not use this module. This helper is for a client that needs a real local path.
"""
from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path
from typing import Any


def materialize_attachment(att: dict[str, Any], output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Ensure a Base64 attachment has a local path, without changing the source."""
    item = dict(att)
    path = item.get("path") or item.get("saved_path") or item.get("file_path")
    if isinstance(path, str) and path and os.path.isfile(path):
        return item
    encoded = item.get("data_base64") or item.get("base64")
    if not isinstance(encoded, str) or not encoded:
        return item
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return item
    mime = str(item.get("mime") or "application/octet-stream").lower()
    ext = {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "image/gif": ".gif", "application/pdf": ".pdf", "audio/mpeg": ".mp3",
        "audio/wav": ".wav", "audio/x-wav": ".wav",
    }.get(mime, "")
    name = Path(str(item.get("name") or "attachment")).name
    if not Path(name).suffix and ext:
        name += ext
    dest = Path(output_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / name
    if target.exists():
        target = dest / f"{target.stem}_{abs(hash(encoded)) & 0xfffffff}{target.suffix}"
    target.write_bytes(raw)
    item["path"] = str(target)
    item["saved_path"] = str(target)
    return item


def materialize_attachments(attachments: Any, output_dir: str | os.PathLike[str]) -> list[Any]:
    if not isinstance(attachments, list):
        return []
    return [materialize_attachment(a, output_dir) if isinstance(a, dict) else a for a in attachments]
