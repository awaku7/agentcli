from __future__ import annotations

import json
from typing import Any

from ..runtime.local_messaging import local_endpoint_is_active
from .arg_util import get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _json_ok(**values: Any) -> str:
    return json.dumps({"ok": True, **values}, ensure_ascii=False)


def _json_error(code: str, message: str, **values: Any) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}, **values},
        ensure_ascii=False,
    )


def _store_for_active_endpoint() -> tuple[Any | None, Any | None, str]:
    """Resolve the host's participating endpoint and its mailbox."""
    callbacks = get_callbacks()
    runtime_ref = callbacks.local_messaging_runtime_ref
    runtime = runtime_ref() if callable(runtime_ref) else None
    endpoint_id = str(getattr(runtime, "endpoint_id", "") or "")
    store = getattr(runtime, "store", None)
    if not endpoint_id or store is None or not local_endpoint_is_active(endpoint_id):
        return None, None, endpoint_id
    if store.active_endpoint(endpoint_id) is None:
        return None, None, endpoint_id
    return runtime, store, endpoint_id


TOOL_SPEC: dict[str, Any] = {
    "load_order": 9000,
    # Keep the natural-language peer/send capability directly visible to the
    # model rather than requiring an on-demand tool-load step.
    "tool_level": 0,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "local_messaging",
        "description": _(
            "tool.description",
            default=(
                "List participating local UAG peers or send a targeted text message. "
                "The current endpoint must be participating. "
                "Explicit inbox retrieval is supported only by an enabled A2A task."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "local UAG peers",
                "local agent messaging",
                "send message to another UAG",
                "list local agents",
            ],
        ),
        "x_search_terms_en": [
            "local UAG peers",
            "local agent messaging",
            "send message to another UAG",
            "list local agents",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "send", "inbox"],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Action: %(action_list)s participating peers, %(action_send)s a "
                            "message, or (A2A only) %(action_inbox)s to explicitly retrieve "
                            "messages from this endpoint's inbox."
                        ),
                        action_list="list",
                        action_send="send",
                        action_inbox="inbox",
                    ),
                },
                "recipient": {
                    "type": "string",
                    "description": _(
                        "param.recipient.description",
                        default=(
                            "Recipient endpoint_id from the peer list; required for "
                            "%(action_send)s."
                        ),
                        action_send="send",
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default=(
                            "Text to send to the selected peer; required for "
                            "%(action_send)s."
                        ),
                        action_send="send",
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    callbacks = get_callbacks()
    if callbacks.set_status:
        callbacks.set_status(True, "tool:local_messaging")
    try:
        runtime, store, endpoint_id = _store_for_active_endpoint()
        if store is None:
            return _json_error(
                "LOCAL_MESSAGING_DISABLED",
                _(
                    "err.disabled",
                    default=(
                        "This endpoint is not participating. Check the "
                        "UAGENT_LOCAL_MESSAGING setting and restart the process."
                    ),
                ),
            )
        try:
            action = get_str(args, "action", "").strip().lower()
            if action == "list":
                peers = runtime.list_peers()
                return _json_ok(
                    peers=[
                        {
                            "endpoint_id": str(peer["endpoint_id"]),
                            "entrypoint": str(peer["entrypoint"]),
                            "pid": int(peer["pid"]),
                            "started_at": float(peer["create_time"]),
                        }
                        for peer in peers
                    ]
                )
            if action == "send":
                recipient = get_str(args, "recipient", "").strip()
                message = get_str(args, "message", "")
                if not recipient:
                    return _json_error(
                        "MISSING_RECIPIENT",
                        _(
                            "err.missing_recipient",
                            default="Select a peer endpoint_id from the list.",
                        ),
                    )
                message_id = store.send_message(endpoint_id, recipient, message)
                return _json_ok(
                    status="pending", message_id=message_id, recipient=recipient
                )
            if action == "inbox":
                if str(getattr(runtime, "entrypoint", "")) != "a2a":
                    return _json_error(
                        "INBOX_UNAVAILABLE",
                        _(
                            "err.inbox_unavailable",
                            default=(
                                "Inbox retrieval is available only to explicitly enabled A2A tasks."
                            ),
                        ),
                    )
                from ..runtime.identity_context import get_current_turn_context
                from ..runtime.local_messaging import external_message_text

                turn = get_current_turn_context()
                if turn is None or str(getattr(turn, "entry_point", "")) != "a2a":
                    return _json_error(
                        "A2A_TASK_REQUIRED",
                        _(
                            "err.a2a_task_required",
                            default=(
                                "Inbox retrieval requires an authenticated A2A task context."
                            ),
                        ),
                    )
                messages = store.claim_messages(endpoint_id)
                items = []
                for message in messages:
                    message_id = str(message.get("message_id") or "")
                    if not message_id:
                        continue
                    if not store.decide_message(endpoint_id, message_id, accepted=True):
                        continue
                    sender = str(message.get("sender_endpoint_id") or "")
                    items.append(
                        {
                            "message_id": message_id,
                            "sender_endpoint_id": sender,
                            "created_at": float(message.get("created_at") or 0),
                            "message": external_message_text(
                                sender, str(message.get("body") or "")
                            ),
                        }
                    )
                return _json_ok(messages=items)
            return _json_error(
                "INVALID_ACTION",
                _(
                    "err.invalid_action",
                    default=(
                        "Action must be %(action_list)s, %(action_send)s, or "
                        "%(action_inbox)s (A2A only)."
                    ),
                    action_list="list",
                    action_send="send",
                    action_inbox="inbox",
                ),
            )
        finally:
            store.close()
    except ValueError as exc:
        return _json_error("INVALID_REQUEST", str(exc))
    except Exception as exc:
        return _json_error(
            "LOCAL_MESSAGING_FAILED",
            _("err.failed", default="Local message operation failed."),
            exception=type(exc).__name__,
        )
    finally:
        if callbacks.set_status:
            callbacks.set_status(False, "tool:local_messaging")


def describe(args: dict[str, Any]) -> str:
    action = str((args or {}).get("action") or "list").strip().lower()
    recipient = str((args or {}).get("recipient") or "").strip()
    purpose = str(
        _(
            "tool.description",
            default="Use the local UAG messaging endpoint.",
        )
    )
    details = [f"action={action}"]
    if recipient:
        details.append(f"recipient={recipient}")
    return f"{purpose} ({'; '.join(details)})."


TOOL_DESCRIBER = describe
