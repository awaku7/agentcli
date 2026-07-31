"""Shared safety and text-loading helpers for *2idx tools."""

from __future__ import annotations

import os
from pathlib import Path

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

DEFAULT_INDEX_MAX_BYTES = 20_000_000
_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc_jp")
# IBM mainframe / IBM i source sometimes arrives as EBCDIC (practical subset).
# Tried only after primary encodings fail strict decode.
_EBCDIC_CANDIDATES = ("cp037", "cp500")


def resolve_index_path(path: str) -> str:
    """Resolve and validate an index-tool input path under the workdir."""
    return ensure_within_workdir(path)


def _looks_like_source_text(text: str) -> bool:
    """True when decoded text looks like RPG/DDS/CL/source rather than binary noise."""
    if not text:
        return False
    sample = text[:4000]
    if "\x00" in sample:
        return False
    printable = sum(1 for ch in sample if ch.isprintable() or ch in "\r\n\t")
    if printable / max(len(sample), 1) < 0.85:
        return False
    low = sample.lower()
    markers = (
        "dcl-",
        "ctl-opt",
        "**free",
        "begsr",
        "exec sql",
        "/copy",
        "     f",
        "     d",
        "     c",
        "     a",
        "     h",
        "pgm ",
        "endpgm",
        "dcl ",
        "dclf",
    )
    if any(m in low for m in markers):
        return True
    # Generic: enough ASCII letters and newlines
    letters = sum(1 for ch in sample if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    newlines = sample.count("\n")
    return letters >= 40 and newlines >= 1


def read_index_source(path: str, max_bytes: int = DEFAULT_INDEX_MAX_BYTES) -> str:
    """Read an index-tool source file as normalized Unicode text.

    UTF-8/BOM and common Japanese encodings are tried in deterministic order.
    If all fail strict decode, a practical EBCDIC fallback (cp037/cp500) is
    attempted when the result looks like source text.
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

    # EBCDIC practical fallback -- only when primary encodings all failed
    best = None
    for encoding in _EBCDIC_CANDIDATES:
        try:
            text = data.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        if _looks_like_source_text(text):
            best = text
            break
    if best is not None:
        return best.replace("\r\n", "\n").replace("\r", "\n")

    return (
        data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    )
