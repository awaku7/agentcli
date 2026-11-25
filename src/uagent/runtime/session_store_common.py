"""Shared definitions for the SQLite session store (split out of
session_store.py): exceptions, schema constants and helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
import json
import ntpath
import os
import re
import shutil
import uuid

from ..utils.paths import get_state_dir
from ..utils.secret_mask import SECRET_MASK
from ..utils.secret_mask import _mask_inline_secrets
from .tool_result_persistence import redact_persistent_secrets
from .tool_result_persistence import sanitize_persistent_value


class SessionStoreError(RuntimeError):
    """Raised when session persistence cannot complete safely."""


class SessionRevisionConflict(SessionStoreError):
    """Raised when an expected AgentState revision is no longer current."""


class SessionComparisonUnavailable(SessionStoreError):
    """Raised when comparison-only needs an AgentState snapshot we did not retain."""


_SESSION_ITEM_KINDS = {
    "message",
    "tool_call",
    "tool_result",
    "runtime_event",
    "execution",
    "artifact_link",
    "checkpoint",
    "handoff",
    "subagent_result",
}


_SESSION_ITEM_ORDERING_QUALITIES = {
    "exact",
    "legacy_message_order",
    "legacy_approximate",
}


_REVIEW_REGISTRY_OWNER = "uag.runtime.sub_agent.review_registry.v1"


def _is_owned_sub_agent_review_registry(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("owner") == _REVIEW_REGISTRY_OWNER
        and value.get("schema_version") == 1
        and isinstance(value.get("entries"), dict)
    )


# Structural schema version stored in ``PRAGMA user_version``. Version 1
# scoped tool-call/tool-result identity to their owning session.
_SCHEMA_VERSION = 1


_TOOL_RESULT_MAX_RECORD_BYTES = 512 * 1024


_TOOL_RESULT_MAX_METADATA_BYTES = 8 * 1024


_TOOL_RESULT_MAX_SUMMARY_BYTES = 4 * 1024


# Tool-call and tool-result identities come from providers and imported
# conversations, so they are only unique inside one session. Keeping them in
# the primary key alongside ``session_id`` matches the session-scoped key that
# ``session_items`` already uses, and stops two sessions that reuse an ID from
# aborting each other's LLM round.
_TOOL_CALLS_DDL = """
    CREATE TABLE IF NOT EXISTS tool_calls (
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        call_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        args_json TEXT NOT NULL,
        result TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(session_id, call_id)
    )
"""


_TOOL_RESULTS_DDL = """
    CREATE TABLE IF NOT EXISTS tool_results (
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        result_id TEXT NOT NULL,
        task_id TEXT,
        tool_name TEXT NOT NULL,
        result_class TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        summary TEXT NOT NULL,
        artifact_ref TEXT,
        importance TEXT NOT NULL,
        evictable INTEGER NOT NULL,
        metadata_json TEXT NOT NULL,
        persistent_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(session_id, result_id)
    )
"""


# ``tool_calls`` and ``tool_results`` are created outside the main schema script
# so the migration can rebuild them without drifting from these definitions.
_TOOL_IDENTITY_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_tool_calls_session_created "
    "ON tool_calls(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tool_results_session_created "
    "ON tool_results(session_id, created_at)",
)


_TOOL_IDENTITY_DDL = (_TOOL_CALLS_DDL, _TOOL_RESULTS_DDL) + _TOOL_IDENTITY_INDEX_DDL


_TOOL_CALLS_COLUMNS = (
    "call_id",
    "session_id",
    "tool_name",
    "args_json",
    "result",
    "status",
    "created_at",
)


_TOOL_RESULTS_COLUMNS = (
    "result_id",
    "session_id",
    "task_id",
    "tool_name",
    "result_class",
    "size_bytes",
    "summary",
    "artifact_ref",
    "importance",
    "evictable",
    "metadata_json",
    "persistent_json",
    "created_at",
)


# One entry per identity table: table, identity column, index name, DDL and the
# column order used to copy rows into the rebuilt table.
_TOOL_IDENTITY_REBUILD_SPECS = (
    (
        "tool_calls",
        "call_id",
        "idx_tool_calls_session_created",
        _TOOL_CALLS_DDL,
        _TOOL_CALLS_COLUMNS,
    ),
    (
        "tool_results",
        "result_id",
        "idx_tool_results_session_created",
        _TOOL_RESULTS_DDL,
        _TOOL_RESULTS_COLUMNS,
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_locked(method):
    """Serialize access to the shared SQLite connection."""

    def wrapper(self, *args, **kwargs):
        with self._db_lock:
            return method(self, *args, **kwargs)

    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


@dataclass(frozen=True)
class Session:
    session_id: str
    project: str | None
    entry_point: str
    project_key: str = ""
    project_path: str | None = None


def project_id_from_path(path: str | Path) -> str:
    """Return a stable, human-friendly workspace name from a path."""
    raw = str(path).rstrip("\\/")
    name = ntpath.basename(raw) or os.path.basename(raw)
    return name or raw or "workspace"


def normalize_tool_call(call: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Normalize OpenAI-style and flat tool-call payloads for persistence."""
    call_id = str(call.get("id") or call.get("tool_call_id") or "")
    function = call.get("function")
    if isinstance(function, dict):
        name = str(function.get("name") or call.get("name") or "tool")
        raw_args = function.get("arguments", {})
    else:
        name = str(call.get("name") or "tool")
        raw_args = call.get("arguments", call.get("args", {}))
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except (TypeError, ValueError):
            raw_args = {"_raw": raw_args}
    if not isinstance(raw_args, dict):
        raw_args = {"_raw": raw_args}
    return call_id, name, raw_args


def redact_sensitive(text: str, *, strip_binary: bool = False) -> str:
    """Mask secrets in text, optionally stripping binaries for tool messages."""
    original_value = str(text or "")
    literal_mask_marker = f"__uagent_literal_mask_{uuid.uuid4().hex}__"
    while literal_mask_marker in original_value:
        literal_mask_marker = f"__uagent_literal_mask_{uuid.uuid4().hex}__"
    value = original_value.replace(SECRET_MASK, literal_mask_marker)
    try:
        if value.lstrip()[:1] not in {"{", "["}:
            sanitized = _mask_inline_secrets(value)
        else:
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                sanitized = _mask_inline_secrets(value)
            else:
                safe_value = (
                    sanitize_persistent_value(parsed)
                    if strip_binary
                    else redact_persistent_secrets(parsed)
                )
                if safe_value == parsed:
                    return original_value
                sanitized = json.dumps(safe_value, ensure_ascii=False)
        sanitized = sanitized.replace(SECRET_MASK, "[REDACTED]")
        return sanitized.replace(literal_mask_marker, SECRET_MASK)
    except Exception:
        # Do not persist the original text if parsing or masking fails.
        return "[persisted message omitted after sanitization error]"


def _sanitize_text(value: Any) -> Any:
    """Return a SQLite-safe string (fold surrogate pairs, drop lone surrogates).

    Windows console/clipboard input and broken UTF-16 decodes can produce
    lone surrogates (U+D800..U+DFFF). CPython's sqlite3 driver encodes
    parameters as UTF-8 with strict errors, so such strings raise
    ``UnicodeEncodeError: surrogates not allowed`` and crash the CLI
    (see ``append_message`` INSERT). Folding via UTF-16 keeps valid pairs
    (e.g. emoji split into two surrogates) intact and replaces lone
    surrogates with U+FFFD.
    """
    if not isinstance(value, str):
        return value
    if not value:
        return value
    # Fast path: no surrogates present.
    has_surrogate = False
    for ch in value:
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            has_surrogate = True
            break
    if not has_surrogate:
        return value
    try:
        return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    except Exception:
        return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in value)


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize str keys/values so JSON dumps stay UTF-8 safe."""
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        return {
            _sanitize_value(key) if isinstance(key, str) else key: _sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        cleaned = [_sanitize_value(item) for item in value]
        return type(value)(cleaned) if isinstance(value, tuple) else cleaned
    return value


def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """json.dumps with surrogate sanitization (input and output)."""
    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("sort_keys", True)
    try:
        text = json.dumps(_sanitize_value(obj), **kwargs)
    except (TypeError, ValueError):
        raise
    return _sanitize_text(text)


def _truncate_utf8_field(value: str, max_bytes: int) -> str:
    """Bound one stored text field without splitting a UTF-8 character."""
    value = _sanitize_text(str(value or ""))
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return value
    marker = "...[truncated]"
    marker_size = len(marker.encode("utf-8"))
    if max_bytes <= marker_size:
        return encoded[:max_bytes].decode("utf-8", errors="ignore")
    prefix_budget = max_bytes - marker_size
    prefix: list[str] = []
    used = 0
    for char in value:
        size = len(char.encode("utf-8", errors="replace"))
        if used + size > prefix_budget:
            break
        prefix.append(char)
        used += size
    return "".join(prefix) + marker


def _bounded_tool_result_metadata(value: Any) -> str:
    """Serialize sanitized metadata while preserving call/status identifiers."""
    cleaned = sanitize_persistent_value(_sanitize_value(value or {}))
    if not isinstance(cleaned, dict):
        cleaned = {"value": cleaned}
    encoded = _safe_json_dumps(cleaned, ensure_ascii=False, sort_keys=True)
    if (
        len(encoded.encode("utf-8", errors="replace"))
        <= _TOOL_RESULT_MAX_METADATA_BYTES
    ):
        return encoded

    compact: dict[str, Any] = {"_uagent_metadata_truncated": True}
    for key in ("tool_call_id", "status"):
        if key not in cleaned:
            continue
        item = cleaned[key]
        compact[key] = (
            _truncate_utf8_field(str(item), 256) if isinstance(item, str) else item
        )
    encoded = _safe_json_dumps(compact, ensure_ascii=False, sort_keys=True)
    if len(encoded.encode("utf-8", errors="replace")) > _TOOL_RESULT_MAX_METADATA_BYTES:
        return _safe_json_dumps({"_uagent_metadata_truncated": True})
    return encoded


def _migrate_legacy_session_store(path: Path) -> None:
    """Move the legacy default store to the current ``.uag`` location."""
    current = Path(".uag/sessions.sqlite3").absolute()
    if path.absolute() != current:
        return

    legacy = Path(".uagent/sessions.sqlite3")
    if not legacy.exists():
        _remove_empty_legacy_dir(legacy)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        # The current database wins when both locations exist.
        legacy.unlink()
        for suffix in ("-wal", "-shm"):
            legacy.with_name(legacy.name + suffix).unlink(missing_ok=True)
        _remove_empty_legacy_dir(legacy)
        return

    os.replace(legacy, path)
    # Keep SQLite sidecar files together with the database when present.
    for suffix in ("-wal", "-shm"):
        old_sidecar = legacy.with_name(legacy.name + suffix)
        if old_sidecar.exists():
            os.replace(old_sidecar, path.with_name(path.name + suffix))
    _remove_empty_legacy_dir(legacy)


def _remove_empty_legacy_dir(legacy: Path) -> None:
    """Remove the legacy directory when migration left it empty."""
    try:
        legacy.parent.rmdir()
    except OSError:
        pass


def _remove_global_artifact_dirs(stored_paths: list[str]) -> None:
    """Best-effort cleanup for new global artifacts after session deletion.

    Only the current global artifact layout (``<id>/<name>``) is eligible.
    Legacy workdir-relative paths and absolute paths are intentionally left
    untouched because this module cannot safely determine their owner root.
    """
    root = (get_state_dir() / "artifacts").expanduser().absolute().resolve()
    for stored_path in stored_paths:
        path = Path(str(stored_path))
        if path.is_absolute() or len(path.parts) < 2:
            continue
        artifact_id = path.parts[0]
        if re.fullmatch(r"[0-9a-f]{32}", artifact_id) is None:
            continue
        artifact_dir = (root / artifact_id).resolve()
        try:
            artifact_dir.relative_to(root)
        except ValueError:
            continue
        if artifact_dir == root or not artifact_dir.is_dir():
            continue
        shutil.rmtree(artifact_dir, ignore_errors=True)
