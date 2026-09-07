"""Dependency-light token estimation for context telemetry and budgeting."""

from __future__ import annotations

import re
from typing import Any

_WORD_RE = re.compile(r"\s+|[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def estimate_tokens(value: Any, *, provider: str = "", model: str = "") -> int:
    """Estimate tokens without requiring a tokenizer package.

    The estimator is deliberately conservative: whitespace-delimited text is
    approximated at four characters per token, while CJK characters are
    counted more densely. Provider/model are accepted so a tokenizer-backed
    implementation can be introduced later without changing call sites.
    """
    del provider, model
    text = str(value or "")
    if not text:
        return 0
    cjk = len(_WORD_RE.findall(text))
    non_cjk = max(0, len(text) - cjk)
    return max(1, int(round(cjk + non_cjk / 4.0)))


__all__ = ["estimate_tokens"]
