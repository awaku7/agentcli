"""Interactive :response command handlers."""

from __future__ import annotations

import json
from typing import Any

from . import core as core_module
from .providers.responses_manager import (
    ResponsesManager,
    cancel_active_response,
    get_responses_capabilities,
)


def _manager(client: Any, depname: str, core: Any) -> ResponsesManager | None:
    provider = str(
        getattr(core, "responses_state", {}).get("provider")
        or getattr(core, "_responses_provider", "")
        or ""
    ).strip().lower()
    if not provider:
        provider = str(getattr(core, "provider", "") or "").strip().lower()
    if client is None or provider not in ("openai", "azure"):
        print(
            "[Responses API] Management commands currently support "
            "OpenAI/Azure only."
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
    manager = _manager(client, depname, core)
    if manager is None:
        return True

    rid = _response_id(core, explicit_id)
    if sub in ("help", "?"):
        print(
            "Usage: :response "
            "[status|cancel|tokens|compact|items|delete] [response_id]"
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
                print(f"[Responses API] Retrieve failed: {exc}")
        else:
            print("[Responses API] No response ID is available.")
        return True

    if sub == "cancel":
        if explicit_id:
            if not rid:
                print("[Responses API] response_id is required.")
                return True
            try:
                _print_json(manager.cancel(rid))
                core_module.clear_responses_continuation()
            except Exception as exc:
                print(f"[Responses API] Cancel failed: {exc}")
        elif cancel_active_response(core):
            print(f"[Responses API] Cancelled {rid or 'active response'}.")
        else:
            print("[Responses API] No cancellable active response is available.")
        return True

    if sub == "tokens":
        try:
            result = manager.count_input_tokens(input=messages_ref)
            _print_json(result)
        except Exception as exc:
            print(f"[Responses API] Token count failed: {exc}")
        return True

    if sub == "compact":
        if not rid:
            print("[Responses API] No response ID is available.")
            return True
        try:
            _print_json(manager.compact(rid))
        except Exception as exc:
            print(f"[Responses API] Compact failed: {exc}")
        return True

    if sub == "items":
        if not rid:
            print("[Responses API] No response ID is available.")
            return True
        try:
            _print_json(manager.list_input_items(rid))
        except Exception as exc:
            print(f"[Responses API] Input item listing failed: {exc}")
        return True

    if sub == "delete":
        if not rid:
            print("[Responses API] Usage: :response delete <response_id>")
            return True
        try:
            _print_json(manager.delete(rid))
            if rid == _response_id(core):
                core_module.clear_responses_continuation()
        except Exception as exc:
            print(f"[Responses API] Delete failed: {exc}")
        return True

    print(
        "Usage: :response "
        "[status|cancel|tokens|compact|items|delete] [response_id]"
    )
    return True
