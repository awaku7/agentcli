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
from .runtime.responses_command_mutation import ResponsesCommandMutationService
from .runtime.responses_command_service import ResponsesCommandService
from .runtime.responses_command_state import ResponsesCommandState


def _manager(
    client: Any, depname: str, core: Any, *, tr: Any = None
) -> ResponsesManager | None:
    tr = tr if callable(tr) else _
    state = ResponsesCommandState.from_core(core)
    provider = state.provider
    if client is None or provider not in ("openai", "azure"):
        print(
            tr(
                "[Responses API] Management commands currently support "
                "OpenAI/Azure only."
            )
        )
        return None
    return ResponsesManager(client, provider=provider, model=depname)


def _response_id(core: Any, explicit: str = "") -> str:
    return ResponsesCommandState.from_core(core).resolve_id(explicit)


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _responses_token_count_payload(
    messages: list[dict[str, Any]], provider: str
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]] | None]:
    """Compatibility wrapper for the Responses command service."""
    return ResponsesCommandService.build_token_count_payload(messages, provider)


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
    tr = tr if callable(tr) else _
    parts = (arg or "").strip().split()
    sub = parts[0].lower() if parts else "status"
    explicit_id = parts[1] if len(parts) > 1 else ""
    manager = _manager(client, depname, core, tr=tr)
    if manager is None:
        return True

    state_view = ResponsesCommandState.from_core(core)
    mutation_service = ResponsesCommandMutationService(state_view)
    rid = state_view.resolve_id(explicit_id)
    if sub in ("help", "?"):
        print(
            tr(
                "Usage: :response "
                "[status|cancel|tokens|compact|items|delete] [response_id]"
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
                print(tr("[Responses API] Retrieve failed: %(error)s") % {"error": exc})
        else:
            print(tr("[Responses API] No response ID is available."))
        return True

    if sub == "cancel":
        if explicit_id:
            if not rid:
                print(tr("[Responses API] response_id is required."))
                return True
            try:
                _print_json(manager.cancel(rid))
                plan = mutation_service.after_cancel(rid, explicit_id=bool(explicit_id))
                if plan.clear_continuation:
                    core_module.clear_responses_continuation()
            except Exception as exc:
                print(tr("[Responses API] Cancel failed: %(error)s") % {"error": exc})
        elif cancel_active_response(core):
            print(
                tr("[Responses API] Cancelled %(response)s.")
                % {"response": rid or tr("active response")}
            )
        else:
            print(tr("[Responses API] No cancellable active response is available."))
        return True

    if sub == "tokens":
        try:
            state = ResponsesCommandState.from_core(core)
            result = ResponsesCommandService.count_tokens(
                manager,
                messages_ref,
                provider=manager.provider,
                previous_response_id=state.previous_response_id,
                last_usage=getattr(core, "_last_responses_usage", None),
            )
            _print_json(result)
        except Exception as exc:
            print(tr("[Responses API] Token count failed: %(error)s") % {"error": exc})
        return True

    if sub == "compact":
        if not rid:
            print(tr("[Responses API] No response ID is available."))
            return True
        try:
            _print_json(ResponsesCommandService.compact(manager, rid))
        except Exception as exc:
            print(tr("[Responses API] Compact failed: %(error)s") % {"error": exc})
        return True

    if sub == "items":
        if not rid:
            print(tr("[Responses API] No response ID is available."))
            return True
        try:
            _print_json(ResponsesCommandService.list_items(manager, rid))
        except Exception as exc:
            print(
                tr("[Responses API] Input item listing failed: %(error)s")
                % {"error": exc}
            )
        return True

    if sub == "delete":
        if not rid:
            print(tr("[Responses API] Usage: :response delete <response_id>"))
            return True
        try:
            _print_json(manager.delete(rid))
            plan = mutation_service.after_delete(rid)
            if plan.clear_continuation:
                core_module.clear_responses_continuation()
        except Exception as exc:
            print(tr("[Responses API] Delete failed: %(error)s") % {"error": exc})
        return True

    print(
        tr(
            "Usage: :response "
            "[status|cancel|tokens|compact|items|delete] [response_id]"
        )
    )
    return True
