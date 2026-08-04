"""Interactive :response command handlers."""

from __future__ import annotations

import json
from typing import Any

from . import core as core_module
from .i18n import _
from .providers.responses_manager import (
    ResponsesManager,
    cancel_active_response,
    get_responses_capabilities,
)


def _t(tr: Any, text: str) -> str:
    """Translate a command message using the session translator when present."""
    fn = tr if callable(tr) else _
    return fn(text)


def _manager(
    client: Any, depname: str, core: Any, *, tr: Any = None
) -> ResponsesManager | None:
    provider = str(
        getattr(core, "responses_state", {}).get("provider")
        or getattr(core, "_responses_provider", "")
        or ""
    ).strip().lower()
    if not provider:
        provider = str(getattr(core, "provider", "") or "").strip().lower()
    if client is None or provider not in ("openai", "azure"):
        print(
            _t(
                tr,
                "[Responses API] Management commands currently support "
                "OpenAI/Azure only.",
            )
        )
        return None
    return ResponsesManager(client, provider=provider, model=depname)


def _response_id(core: Any, explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    state = getattr(core, "responses_state", {})
    if isinstance(state, dict):
        return str(
            state.get("active_response_id")
            or state.get("previous_response_id")
            or ""
        )
    return ""


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _handle_cmd_response(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
    tr: Any = None,
) -> Any:
    """Handle ``:response <status|cancel|tokens|compact|items|delete>``."""
    parts = (arg or "").strip().split()
    sub = (parts[0].lower() if parts else "status")
    explicit_id = parts[1] if len(parts) > 1 else ""
    manager = _manager(client, depname, core, tr=tr)
    if manager is None:
        return True

    rid = _response_id(core, explicit_id)
    if sub in ("help", "?"):
        print(
            _t(
                tr,
                "Usage: :response "
                "[status|cancel|tokens|compact|items|delete] [response_id]",
            )
        )
        return True

    if sub == "status":
        state = getattr(core, "responses_state", {})
        _print_json(
            {
                "provider": manager.provider,
                "model": depname,
                "state": state,
                "capabilities": get_responses_capabilities(manager.provider),
            }
        )
        if rid:
            try:
                _print_json(manager.retrieve(rid))
            except Exception as exc:
                print(_t(tr, "[Responses API] Retrieve failed: %(error)s") % {"error": exc})
        else:
            print(_t(tr, "[Responses API] No response ID is available."))
        return True

    if sub == "cancel":
        if explicit_id:
            if not rid:
                print(_t(tr, "[Responses API] response_id is required."))
                return True
            try:
                _print_json(manager.cancel(rid))
                core_module.clear_responses_continuation()
            except Exception as exc:
                print(_t(tr, "[Responses API] Cancel failed: %(error)s") % {"error": exc})
        elif cancel_active_response(core):
            print(
                _t(tr, "[Responses API] Cancelled %(response)s.")
                % {"response": rid or _t(tr, "active response")}
            )
        else:
            print(_t(tr, "[Responses API] No cancellable active response is available."))
        return True

    if sub == "tokens":
        try:
            result = manager.count_input_tokens(input=messages_ref)
            _print_json(result)
        except Exception as exc:
            print(_t(tr, "[Responses API] Token count failed: %(error)s") % {"error": exc})
        return True

    if sub == "compact":
        if not rid:
            print(_t(tr, "[Responses API] No response ID is available."))
            return True
        try:
            _print_json(manager.compact(rid))
        except Exception as exc:
            print(_t(tr, "[Responses API] Compact failed: %(error)s") % {"error": exc})
        return True

    if sub == "items":
        if not rid:
            print(_t(tr, "[Responses API] No response ID is available."))
            return True
        try:
            _print_json(manager.list_input_items(rid))
        except Exception as exc:
            print(_t(tr, "[Responses API] Input item listing failed: %(error)s") % {"error": exc})
        return True

    if sub == "delete":
        if not rid:
            print(_t(tr, "[Responses API] Usage: :response delete <response_id>"))
            return True
        try:
            _print_json(manager.delete(rid))
            if rid == _response_id(core):
                core_module.clear_responses_continuation()
        except Exception as exc:
            print(_t(tr, "[Responses API] Delete failed: %(error)s") % {"error": exc})
        return True

    print(
        _t(
            tr,
            "Usage: :response "
            "[status|cancel|tokens|compact|items|delete] [response_id]",
        )
    )
    return True
