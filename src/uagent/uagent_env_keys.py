from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_UAGENT_RE = re.compile(r"\bUAGENT_[A-Z0-9_]+\b")
_PACKAGE_DIR = Path(__file__).resolve().parent


def _is_placeholder_uagent_key(key: str) -> bool:
    if key == "UAGENT_XXX":
        return True
    if key.endswith("_"):
        return True
    return bool(re.fullmatch(r"UAGENT_X+", key))


@lru_cache(maxsize=1)
def get_known_uagent_env_keys(prefix: str = "UAGENT_") -> list[str]:
    keys: set[str] = set()
    for path in _PACKAGE_DIR.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        keys.update(_UAGENT_RE.findall(text))

    if prefix:
        keys = {k for k in keys if k.startswith(prefix)}

    keys = {k for k in keys if not _is_placeholder_uagent_key(k)}

    return sorted(keys, key=str.lower)
