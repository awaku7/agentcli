"""Shared safety and text-loading helpers for *2idx tools."""

from __future__ import annotations

import os
from pathlib import Path

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

DEFAULT_INDEX_MAX_BYTES = 20_000_000
_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc_jp")


def resolve_index_path(path: str) -> str:
    """Resolve and validate an index-tool input path under the workdir."""
    return ensure_within_workdir(path)


def read_index_source(path: str, max_bytes: int = DEFAULT_INDEX_MAX_BYTES) -> str:
    """Read an index-tool source file as normalized Unicode text.

    UTF-8/BOM and common Japanese encodings are tried in deterministic order.
    CRLF/CR are normalized to LF.  The size check prevents accidental large
    whole-file loads by the parser tools.
    """
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(
            _(
                "err.file_too_large",
                default="file is too large: {size} > {max_bytes} bytes",
            ).format(size=size, max_bytes=max_bytes)
        )

    data = Path(path).read_bytes()
    for encoding in _ENCODING_CANDIDATES:
        try:
            text = data.decode(encoding, errors="strict")
            return text.replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
