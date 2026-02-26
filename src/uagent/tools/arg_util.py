"""Utility for parsing and validating tool arguments."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T")


def get_str(
    args: Dict[str, Any], key: str, default: str = "", *, strip: bool = True
) -> str:
    """Get a string argument with optional stripping."""
    val = args.get(key)
    if val is None:
        return default
    s = str(val)
    return s.strip() if strip else s


def get_int(args: Dict[str, Any], key: str, default: int = 0) -> int:
    """Get an integer argument safely."""
    val = args.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_bool(args: Dict[str, Any], key: str, default: bool = False) -> bool:
    """Get a boolean argument safely."""
    val = args.get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).lower()
    return s in ("true", "1", "t", "y", "yes")


def get_list(
    args: Dict[str, Any], key: str, default: Optional[List[Any]] = None
) -> List[Any]:
    """Get a list argument safely."""
    val = args.get(key)
    if val is None:
        return default if default is not None else []
    if isinstance(val, list):
        return val
    return [val]


def get_path(
    args: Dict[str, Any], key: str, default: str = "", *, expand: bool = True
) -> str:
    """Get a path string argument, optionally expanded."""
    p = get_str(args, key, default)
    if not p:
        return default
    return os.path.expanduser(p) if expand else p
