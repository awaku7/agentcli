"""Cached tool-spec manifest for lazy plugin loading (speed-first plan, P0-2).

The plugin loader used to import every module under ``tools/`` on first tool
access (~300 modules, most of which are never called in a session). This
module records, per plugin module, what the loader needs to register it
without importing it, and stores that record in the user cache directory.

The cache is valid only for an exact match of everything that can change the
specs a module produces at import time:

- every ``.py``/``.json`` file under ``tools/`` (relative path, mtime, size),
- the tool-translation locale,
- the Python version and platform,
- the ``UAGENT_*`` environment variables (except a few per-process values)
  and ``PATH`` (some tools look executables up at import time).

Any mismatch means a full rebuild, which costs the same as the old eager load.
A mismatch that was not strictly necessary only costs time; it never produces
a wrong spec. Set ``UAGENT_TOOL_MANIFEST=off`` to always import every plugin.

The manifest holds data only (JSON). Module names read from it are used only
when the same name is also found by scanning the package directory, so a
tampered cache file cannot make the loader import anything new.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Bump when the entry format or the classification rules change.
MANIFEST_FORMAT = 1

# Entry kinds.
KIND_LAZY = "lazy"  # register from cached specs; import on first use
KIND_SKIP = "skip"  # helper module: no TOOL_SPEC/run_tool and no CMD_SPEC(S)

SPEC_ATTRS = ("TOOL_SPEC", "TOOL_SPEC_2", "TOOL_SPEC_3")

# Attributes a lazy module is known not to define (see ``classify_module``).
# A view answers these without importing the real module.
KNOWN_ABSENT_ATTRS = frozenset(
    {
        "CMD_SPEC",
        "CMD_SPECS",
        "LOAD_DISABLED_REASON",
        "LAZY_LOAD",
        "is_loadable",
    }
)

# Environment variables that differ per process without affecting tool specs.
# Leaving one out of this list only causes cache misses, never wrong specs.
_VOLATILE_ENV = frozenset(
    {
        "UAGENT_A2A_HOST",
        "UAGENT_A2A_PORT",
        "UAGENT_SESSION_SECRET",
        "UAGENT_SESSION_STORE_PATH",
    }
)


def manifest_enabled() -> bool:
    value = (os.environ.get("UAGENT_TOOL_MANIFEST", "on") or "on").strip().lower()
    return value not in {"0", "off", "false", "no"}


def _tree_signature(pkg_dir: str) -> list[tuple[str, int, int]]:
    rows: list[tuple[str, int, int]] = []
    # (directory, relative prefix); os.path.relpath per file is ~15x slower.
    stack = [(pkg_dir, "")]
    while stack:
        current, prefix = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name != "__pycache__":
                            stack.append((entry.path, f"{prefix}{entry.name}/"))
                        continue
                    if not entry.name.endswith((".py", ".json")):
                        continue
                    st = entry.stat(follow_symlinks=False)
                    rows.append((prefix + entry.name, st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    rows.sort()
    return rows


def compute_fingerprint(pkg_dir: str, locale: str) -> str:
    """Return a digest of everything that can change import-time tool specs."""
    env_items = sorted(
        (key, value)
        for key, value in os.environ.items()
        if key.startswith("UAGENT_") and key not in _VOLATILE_ENV
    )
    payload = {
        "format": MANIFEST_FORMAT,
        "python": sys.version,
        "platform": sys.platform,
        "os": os.name,
        "locale": locale,
        "path": os.environ.get("PATH", ""),
        "env": env_items,
        "files": _tree_signature(pkg_dir),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=20).hexdigest()


def manifest_path(pkg_dir: str, locale: str) -> Path:
    from ..utils.paths import get_cache_dir

    # One file per package location and locale, so source checkouts and
    # installed copies (or Web rooms with different languages) do not evict
    # each other's cache.
    where = hashlib.blake2b(
        os.path.abspath(pkg_dir).encode("utf-8"), digest_size=6
    ).hexdigest()
    safe_locale = "".join(ch if ch.isalnum() else "_" for ch in (locale or "x"))
    return get_cache_dir() / "tool_manifest" / f"{where}-{safe_locale}.json"


def load_manifest(path: Path, fingerprint: str) -> dict[str, dict[str, Any]] | None:
    """Return the cached entries, or None when missing, stale or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("format") != MANIFEST_FORMAT or data.get("fingerprint") != fingerprint:
        return None
    entries = data.get("modules")
    if not isinstance(entries, dict):
        return None
    return {k: v for k, v in entries.items() if isinstance(v, dict)}


def save_manifest(
    path: Path, fingerprint: str, entries: dict[str, dict[str, Any]]
) -> None:
    """Write the manifest atomically; failures are ignored (cache only)."""
    data = {"format": MANIFEST_FORMAT, "fingerprint": fingerprint, "modules": entries}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        return


def _json_copy(value: Any) -> Any:
    """Return a JSON round-trip copy, or None if it would not be identical."""
    try:
        copied = json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return None
    return copied if copied == value else None


def _tool_level(spec: dict[str, Any]) -> int:
    try:
        return int(spec.get("tool_level", 0))
    except Exception:
        return 0


def classify_module(mod: Any, never_lazy_names: frozenset[str]) -> dict | None:
    """Return the manifest entry for an imported plugin module.

    ``None`` means "always import this module" (eager). A module is lazy only
    when registering it needs nothing but its specs:

    - it has a ``TOOL_SPEC`` dict and a callable ``run_tool``;
    - no spec is visible to the LLM at startup (every ``tool_level`` is 1 or
      -1), so only a runner has to exist until the tool is used;
    - it has no ``CMD_SPEC(S)`` (CLI commands need their handlers), no
      ``is_loadable()`` and no ``LOAD_DISABLED_REASON`` (environment checks);
    - none of its tool names is in ``never_lazy_names`` (e.g. tools excluded in
      embedded mode or loaded individually);
    - its specs are plain JSON data.
    """
    has_commands = isinstance(getattr(mod, "CMD_SPECS", None), list) or isinstance(
        getattr(mod, "CMD_SPEC", None), dict
    )
    spec = getattr(mod, "TOOL_SPEC", None)
    runner = getattr(mod, "run_tool", None)
    if not isinstance(spec, dict) or not callable(runner):
        return None if has_commands else {"kind": KIND_SKIP}
    if has_commands or callable(getattr(mod, "is_loadable", None)):
        return None
    if getattr(mod, "LOAD_DISABLED_REASON", ""):
        return None
    if getattr(mod, "LAZY_LOAD", False):
        return None

    specs: dict[str, Any] = {}
    for attr in SPEC_ATTRS:
        value = getattr(mod, attr, None)
        if value is None:
            continue
        if not isinstance(value, dict):
            return None
        if _tool_level(value) not in (1, -1):
            return None
        fn = value.get("function")
        name = fn.get("name") if isinstance(fn, dict) else None
        if not isinstance(name, str) or not name or name in never_lazy_names:
            return None
        if "x_single_load_seq" in value or "_single_load_seq" in value:
            return None
        copied = _json_copy(value)
        if copied is None:
            return None
        specs[attr] = copied
    return {"kind": KIND_LAZY, "specs": specs}


def tool_names_of(entry: dict[str, Any]) -> list[str]:
    names: list[str] = []
    specs = entry.get("specs")
    if not isinstance(specs, dict):
        return names
    for attr in SPEC_ATTRS:
        spec = specs.get(attr)
        fn = spec.get("function") if isinstance(spec, dict) else None
        name = fn.get("name") if isinstance(fn, dict) else None
        if isinstance(name, str) and name:
            names.append(name)
    return names


class ManifestModuleView:
    """Stand-in for a lazy plugin module that has not been imported yet.

    Exposes the cached ``TOOL_SPEC``/``TOOL_SPEC_2``/``TOOL_SPEC_3`` and
    answers the attributes a lazy module is known not to define. Any other
    attribute imports the real module and is read from it.
    """

    __slots__ = ("__name__", "_specs")

    def __init__(self, module_name: str, specs: dict[str, Any]) -> None:
        object.__setattr__(self, "__name__", module_name)
        object.__setattr__(self, "_specs", specs)

    def __getattr__(self, attr: str) -> Any:
        specs = object.__getattribute__(self, "_specs")
        if attr in specs:
            return specs[attr]
        if attr in SPEC_ATTRS or attr in KNOWN_ABSENT_ATTRS:
            raise AttributeError(attr)
        import importlib

        module = importlib.import_module(object.__getattribute__(self, "__name__"))
        return getattr(module, attr)

    def __dir__(self) -> list[str]:
        return sorted(object.__getattribute__(self, "_specs"))
