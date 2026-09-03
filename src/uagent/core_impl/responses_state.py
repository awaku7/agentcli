"""Responses state persistence (split from core.py)."""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from .. import core as _core
from .logs import latest_responses_state


def _load_responses_state() -> None:
    return


def _check_responses_state_provider(provider: str, depname: str) -> None:
    return


def _save_responses_state() -> None:
    return


def _maybe_ask_resume() -> None:
    return


def _append_responses_state_record() -> None:
    """Append safe Responses metadata to the active conversation JSONL log."""
    rid = str(_core.responses_state.get("previous_response_id") or "").strip()
    provider = str(_core.responses_state.get("provider") or "").strip()
    model = str(_core.responses_state.get("model") or "").strip()
    status = str(_core.responses_state.get("last_response_status") or "").strip()
    if not rid.startswith("resp_") or status != "completed":
        return
    session_store = getattr(_core, "session_store", None)
    session_id = getattr(_core, "_session_store_active_id", None) or getattr(
        _core, "session_id", None
    )
    if session_store is not None and session_id:
        session_store.record_response_state(
            session_id,
            provider=provider,
            model=model,
            response_id=rid,
            status=status,
        )
        return
    previous = latest_responses_state(_core.LOG_FILE)
    if (
        isinstance(previous, dict)
        and str(previous.get("response_id") or "") == rid
        and str(previous.get("provider") or "") == provider
        and str(previous.get("model") or "") == model
        and str(previous.get("status") or "") == status
    ):
        return
    record = {
        "type": "responses_state",
        "schema_version": 1,
        "provider": provider,
        "model": model,
        "response_id": rid,
        "status": status,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        os.makedirs(os.path.dirname(_core.LOG_FILE) or ".", exist_ok=True)
        with open(_core.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    except Exception:
        pass


def set_tool_context(tool_name: str, context: dict) -> None:
    """Store small JSON-safe context owned by a tool and persist it."""
    name = str(tool_name or "").strip()
    if not name or not isinstance(context, dict):
        return
    try:
        safe = json.loads(json.dumps(context, ensure_ascii=False))
    except (TypeError, ValueError):
        return
    if not isinstance(safe, dict):
        return
    _core.tool_context[name] = safe
    session_store = getattr(_core, "session_store", None)
    session_id = getattr(_core, "_session_store_active_id", None) or getattr(
        _core, "session_id", None
    )
    if session_store is not None and session_id:
        try:
            session_store.record_tool_context(session_id, tool_name=name, context=safe)
            return
        except Exception:
            pass
    record = {
        "type": "tool_context",
        "schema_version": 1,
        "tool": name,
        "context": safe,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        os.makedirs(os.path.dirname(_core.LOG_FILE) or ".", exist_ok=True)
        with open(_core.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    except Exception:
        pass


def register_tool_context_names(tool_names: Any) -> None:
    """Ensure known tool names have empty opaque context slots."""
    names = tool_names if isinstance(tool_names, (list, tuple, set, frozenset)) else []
    for tool_name in names:
        name = str(tool_name or "").strip()
        if name:
            _core.tool_context.setdefault(name, {})


def set_active_response(response_id: str, *, status: str = "in_progress") -> None:
    """Track the latest server-side Responses API lifecycle state."""
    if not isinstance(response_id, str) or not response_id.startswith("resp_"):
        return
    if status in {"completed", "cancelled", "failed"}:
        _core.responses_state.pop("active_response_id", None)
    else:
        _core.responses_state["active_response_id"] = response_id
    _core.responses_state["last_response_status"] = status
    try:
        _save_responses_state()
        if status == "completed":
            _append_responses_state_record()
    except Exception:
        pass


def finish_active_response(*, status: str = "completed") -> None:
    """Mark the tracked Response as finished without changing continuation ID."""
    if not isinstance(_core.responses_state, dict):
        return
    _core.responses_state.pop("active_response_id", None)
    _core.responses_state["last_response_status"] = status
    try:
        _save_responses_state()
        if status == "completed":
            _append_responses_state_record()
    except Exception:
        pass


def clear_responses_continuation() -> None:
    """Drop Responses API continuation after interrupt or broken tool chains.

    previous_response_id is only valid when the prior response chain can be
    continued (including any required function_call_output items). A user
    interrupt typically leaves that chain incomplete, so the next turn must
    start without reusing the stale response id.
    """
    if not isinstance(_core.responses_state, dict):
        return
    _core.responses_state.pop("previous_response_id", None)
    _core.responses_state.pop("active_response_id", None)
    _core.responses_state["last_response_status"] = "cancelled"
    _core.responses_state.pop("_stale_rid_occurred", None)
    try:
        _save_responses_state()
    except Exception:
        pass
