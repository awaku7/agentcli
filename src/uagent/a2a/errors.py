from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class A2AHttpError(Exception):
    status_code: int
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


def aip193_error(
    *, code: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    # AIP-193 style error object.
    # NOTE: This is a best-effort mapping. Fields may be extended later.
    err: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        err["error"]["details"] = details
    return err
