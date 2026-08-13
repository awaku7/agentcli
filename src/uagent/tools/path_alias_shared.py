from __future__ import annotations

"""Persistent short path aliases used by the central tool dispatcher."""

import json
import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

_ALIAS_RE = re.compile(r"^@A\{([0-9])\}(?:[\\/](.*))?$")
_STORE_LOCK = RLock()
_URL_ALIAS_RE = re.compile(r"^@B\{([0-9])\}(.*)$")


def _url_store_path() -> Path:
    return Path(os.environ.get("UAGENT_URL_ALIAS_FILE", "~/.uag/url_aliases.json")).expanduser()


def load_url_aliases() -> dict[int, str]:
    path = _url_store_path()
    with _STORE_LOCK:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
    if not isinstance(data, dict):
        return {}
    result: dict[int, str] = {}
    for key, value in data.items():
        try:
            slot = int(key)
        except (TypeError, ValueError):
            continue
        if 0 <= slot <= 9 and isinstance(value, str) and value:
            result[slot] = value
    return result


def save_url_aliases(aliases: dict[int, str]) -> None:
    path = _url_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(slot): value for slot, value in sorted(aliases.items())}
    with _STORE_LOCK:
        fd, tmp_name = tempfile.mkstemp(prefix="url_aliases.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(tmp_name, path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def resolve_url_alias(value: str) -> str:
    match = _URL_ALIAS_RE.match(value)
    if not match:
        return value
    slot = int(match.group(1))
    aliases = load_url_aliases()
    base = aliases.get(slot)
    if base is None:
        raise ValueError(f"unknown URL alias: @B{{{slot}}}")
    suffix = match.group(2)
    if suffix and not suffix.startswith(("/", "?", "#")):
        raise ValueError("URL alias suffix must start with '/', '?' or '#'")
    return base.rstrip("/") + suffix


def url_alias_label(slot: int) -> str:
    return f"@B{{{slot}}}"


def _store_path() -> Path:
    return Path(os.environ.get("UAGENT_PATH_ALIAS_FILE", "~/.uag/path_aliases.json")).expanduser()


def load_aliases() -> dict[int, Path]:
    path = _store_path()
    with _STORE_LOCK:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
    if not isinstance(data, dict):
        return {}
    result: dict[int, Path] = {}
    for key, value in data.items():
        try:
            slot = int(key)
        except (TypeError, ValueError):
            continue
        if 0 <= slot <= 9 and isinstance(value, str) and value:
            result[slot] = Path(value)
    return result


def save_aliases(aliases: dict[int, Path]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(slot): str(root) for slot, root in sorted(aliases.items())}
    with _STORE_LOCK:
        fd, tmp_name = tempfile.mkstemp(prefix="path_aliases.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(tmp_name, path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def resolve_alias(value: str) -> str:
    match = _ALIAS_RE.match(value)
    if not match:
        return value
    slot = int(match.group(1))
    aliases = load_aliases()
    root = aliases.get(slot)
    if root is None and slot == 0:
        # @A{0} is a dynamic default alias for the current workdir until
        # explicitly overridden with path_alias(set).
        root = Path.cwd()
    if root is None:
        raise ValueError(f"unknown path alias: @A{{{slot}}}")
    relative = match.group(2) or ""
    resolved_root = root.expanduser().resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("path escapes alias root")
    return str(resolved)


# Only fields conventionally containing paths are rewritten at the common entry point.
_URL_FIELD_NAMES = {
    "url", "url_pattern", "url_contains", "base_url", "business_url",
    "location", "redirect_uri",
}

_PATH_FIELD_NAMES = {
    "path", "paths", "filename", "filenames", "file", "file_path", "filepath",
    "current_file", "output_path", "input_path", "db_path", "json_path", "log_path",
    "pcap_path", "img", "image", "mask_path", "zip_path", "dest_dir", "destination",
    "output_dir", "outdir", "root", "root_path", "root_dir", "cwd", "new_dir",
    "source", "sources", "relative_path", "file_pattern", "download_dir", "trace_path",
    "record_video_dir", "storage_state", "skill_dir", "sheets_dir", "print_areas_dir",
    "auto_page_breaks_dir", "exclude_dirs", "path1", "path2", "render_path",
}


def resolve_tool_aliases(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, str):
        if field_name in _PATH_FIELD_NAMES:
            return resolve_alias(value)
        if field_name in _URL_FIELD_NAMES:
            return resolve_url_alias(value)
        return value
    if isinstance(value, list):
        if field_name in _PATH_FIELD_NAMES:
            return [resolve_alias(item) if isinstance(item, str) else item for item in value]
        if field_name in _URL_FIELD_NAMES:
            return [resolve_url_alias(item) if isinstance(item, str) else item for item in value]
        return [resolve_tool_aliases(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_tool_aliases(item, str(key)) for key, item in value.items()}
    return value


def resolve_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    return resolve_tool_aliases(args)


def alias_label(slot: int) -> str:
    return f"@A{{{slot}}}"
