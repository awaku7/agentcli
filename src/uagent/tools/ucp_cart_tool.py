"""ucp_cart_tool

Create, retrieve, and update shopping carts via UCP.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
from typing import Any

from .ucp_shared import (
    discover_business,
    ucp_request,
    UCPError,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:ucp_cart"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_cart",
        "description": _(
            "tool.description",
            default=(
                "Create, retrieve, or update a shopping cart via UCP. "
                "Use mode='create' to create a new cart, mode='get' to retrieve, "
                "or mode='update' to modify line items."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["create", "get", "update"],
                    "description": _(
                        "param.mode.description",
                        default="'create' to create cart, 'get' to retrieve, 'update' to modify.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business.",
                    ),
                },
                "cart_id": {
                    "type": "string",
                    "description": _(
                        "param.cart_id.description",
                        default="Cart ID (required for mode='get' and mode='update').",
                    ),
                },
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "variant_id": {"type": "string"},
                        },
                    },
                    "description": _(
                        "param.line_items.description",
                        default="Line items for the cart. "
                        "Each item has item_id (str) and quantity (int). "
                        "Required for mode='create' and mode='update'.",
                    ),
                },
                "currency": {
                    "type": "string",
                    "description": _(
                        "param.currency.description",
                        default="ISO 4217 currency code (e.g. 'USD', 'JPY'). Optional.",
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
    cart_id = str(args.get("cart_id") or "").strip()
    line_items = args.get("line_items")
    currency = str(args.get("currency") or "").strip() or None

    if not business_url:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "business_url is required."},
        }, ensure_ascii=False)

    if mode in ("get", "update") and not cart_id:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "cart_id is required for mode='{mode}'.".format(mode=mode)},
        }, ensure_ascii=False)

    if mode in ("create", "update") and not line_items:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "line_items is required for mode='{mode}'.".format(mode=mode)},
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
            body = {"line_items": line_items}
            if currency:
                body["currency"] = currency
            resp = ucp_request(business_url, "carts", method="POST", body=body, profile=profile)

        elif mode == "get":
            resp = ucp_request(
                business_url, "carts/{id}".format(id=cart_id),
                method="GET", profile=profile,
            )

        elif mode == "update":
            body = {"line_items": line_items}
            resp = ucp_request(
                business_url, "carts/{id}".format(id=cart_id),
                method="PATCH", body=body, profile=profile,
            )
        else:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_mode", "message": "Unknown mode: {mode}".format(mode=mode)},
            }, ensure_ascii=False)

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

    return json.dumps({
        "ok": True,
        "mode": mode,
        "business_url": business_url,
        "cart_id": cart_id or (resp.get("id") if isinstance(resp, dict) else None),
        "result": resp,
    }, ensure_ascii=False, indent=2)
