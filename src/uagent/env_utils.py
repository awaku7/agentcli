# -*- coding: utf-8 -*-
"""env_utils.py

Small, dependency-free helpers for reading environment variables.

Purpose:
- Allow users to wrap env values with matching quotes, e.g.:
    set UAGENT_OPENAI_BASE_URL="https://api.openai.com/v1"
    set UAGENT_DEPNAME='gpt-4o'

Policy:
- Only strip *one* outer pair of matching quotes after whitespace stripping.
- Never attempt shell-like unescaping.
"""

from __future__ import annotations

from typing import Optional


def strip_outer_quotes(value: str) -> str:
    """Strip one pair of matching outer quotes ("..." or '...')."""

    if value is None:
        return ""

    s = str(value).strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s


def env_get(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get env var as a normalized string (strip whitespace + outer quotes).

    Returns:
      - None if missing and default is None
      - Otherwise a (possibly empty) string
    """

    import os

    v = os.environ.get(name, default)
    if v is None:
        return None
    return strip_outer_quotes(v)
