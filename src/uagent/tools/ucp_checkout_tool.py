"""ucp_checkout_tool

Manage checkout sessions via UCP — create, get, update, and complete.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
from typing import Any

from .ucp_shared import (
    discover_business,
    ucp_request,
    UCPBuyerInputError,
    UCPError,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:ucp_checkout"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_checkout",
        "description": _(
            "tool.description",
            default=(
                "Manage a UCP checkout session. "
                "Use mode='create' to start a checkout, mode='get' to fetch status, "
                "mode='update' to modify, or mode='complete' to finalize the order. "
                "When complete returns requires_escalation with a continue_url, "
                "the user must open that URL in a browser to complete payment."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["create", "get", "update", "complete"],
                    "description": _(
                        "param.mode.description",
                        default="'create' / 'get' / 'update' / 'complete'.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business.",
                    ),
                },
                "checkout_id": {
                    "type": "string",
                    "description": _(
                        "param.checkout_id.description",
                        default="Checkout session ID (required for get/update/complete).",
                    ),
                },
                "cart_id": {
                    "type": "string",
                    "description": _(
                        "param.cart_id.description",
                        default="Cart ID to create checkout from (optional, alternative to line_items).",
                    ),
                },
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                    },
                    "description": _(
                        "param.line_items.description",
                        default="Line items for direct checkout (alternative to cart_id).",
                    ),
                },
                "ap2_token": {
                    "type": "string",
                    "description": _(
                        "param.ap2_token.description",
                        default="AP2 payment token for autonomous completion (mode='complete' only).",
                    ),
                },
                "currency": {
                    "type": "string",
                    "description": _(
                        "param.currency.description",
                        default="ISO 4217 currency code. Optional.",
                    ),
                },
            },
            "required": ["mode", "business_url"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    mode = str(args.get("mode") or "create").strip()
    business_url = str(args.get("business_url") or "").strip()
    checkout_id = str(args.get("checkout_id") or "").strip()
    cart_id = str(args.get("cart_id") or "").strip()
    line_items = args.get("line_items")
    ap2_token = str(args.get("ap2_token") or "").strip() or None
    currency = str(args.get("currency") or "").strip() or None

    if not business_url:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "business_url is required."},
        }, ensure_ascii=False)

    if mode in ("get", "update", "complete") and not checkout_id:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument",
                       "message": "checkout_id is required for mode='{mode}'.".format(mode=mode)},
        }, ensure_ascii=False)

    try:
        profile = discover_business(business_url)
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "error": {"code": "discovery_failed", "message": str(exc)},
        }, ensure_ascii=False)

    try:
        if mode == "create":
            body: dict[str, Any] = {}
            if cart_id:
                body["cart_id"] = cart_id
            if line_items:
                body["line_items"] = line_items
            if currency:
                body["currency"] = currency
            resp = ucp_request(
                business_url, "checkout-sessions",
                method="POST", body=body if body else None,
                profile=profile, idempotent=True,
            )

        elif mode == "get":
            resp = ucp_request(
                business_url,
                "checkout-sessions/{id}".format(id=checkout_id),
                method="GET", profile=profile,
            )

        elif mode == "update":
            body = {}
            if line_items is not None:
                body["line_items"] = line_items
            resp = ucp_request(
                business_url,
                "checkout-sessions/{id}".format(id=checkout_id),
                method="PATCH", body=body if body else None,
                profile=profile,
            )

        elif mode == "complete":
            body: dict[str, Any] = {}
            if ap2_token:
                body["ap2_token"] = ap2_token
            try:
                resp = ucp_request(
                    business_url,
                    "checkout-sessions/{id}/complete".format(id=checkout_id),
                    method="POST", body=body if body else None,
                    profile=profile, idempotent=True,
                )
            except UCPBuyerInputError as exc:
                # Business requires buyer handoff - this is expected for continue_url flow
                return json.dumps({
                    "ok": True,
                    "requires_escalation": True,
                    "message": "Payment requires user action in browser.",
                    "continue_url": _extract_continue_url(exc),
                    "checkout_id": checkout_id,
                }, ensure_ascii=False, indent=2)

        else:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_mode", "message": "Unknown mode: {mode}".format(mode=mode)},
            }, ensure_ascii=False)

    except UCPBuyerInputError as exc:
        return json.dumps({
            "ok": True,
            "requires_escalation": True,
            "message": "Payment requires user action in browser.",
            "continue_url": _extract_continue_url(exc),
            "checkout_id": checkout_id,
        }, ensure_ascii=False, indent=2)
    except UCPError as exc:
        return json.dumps({
            "ok": False,
            "error": {"code": "ucp_error", "message": str(exc)},
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "error": {"code": "request_failed", "message": str(exc)},
        }, ensure_ascii=False)

    # Extract status info for the response summary
    status = None
    continue_url = None
    if isinstance(resp, dict):
        status = resp.get("status")
        cont = resp.get("continue_url")
        if cont:
            continue_url = cont

    result = {
        "ok": True,
        "mode": mode,
        "business_url": business_url,
        "checkout_id": checkout_id or (resp.get("id") if isinstance(resp, dict) else None),
        "status": status,
        "result": resp,
    }
    if continue_url:
        result["continue_url"] = continue_url
        result["requires_escalation"] = (status == "requires_escalation")

    return json.dumps(result, ensure_ascii=False, indent=2)


def _extract_continue_url(exc: UCPBuyerInputError) -> str | None:
    """Extract continue_url from error body."""
    if isinstance(exc.body, dict):
        cont = exc.body.get("continue_url")
        if cont:
            return str(cont)
        ucp = exc.body.get("ucp", {})
        cont = ucp.get("continue_url")
        if cont:
            return str(cont)
    return None
