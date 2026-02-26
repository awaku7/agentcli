"""Utility for standardizing tool responses."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def make_response(
    ok: bool, message: str, data: Optional[Dict[str, Any]] = None
) -> str:
    """Create a standardized JSON response string.

    Format:
    {
        "ok": bool,
        "message": str,
        "data": dict | None
    }
    """
    res = {
        "ok": ok,
        "message": message,
    }
    if data is not None:
        res["data"] = data

    return json.dumps(res, ensure_ascii=False)
