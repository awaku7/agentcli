"""ucp_order_tool

List and retrieve orders via UCP.
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
STATUS_LABEL = "tool:ucp_order"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_order",
        "description": _(
            "tool.description",
            default=(
                "List or retrieve orders via UCP. "
                "Use mode='list' to get order history, "
                "or mode='get' to fetch a specific order by ID."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["list", "get"],
                    "description": _(
                        "param.mode.description",
                        default="'list' for order history, 'get' for single order.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business.",
                    ),
                },
                "order_id": {
                    "type": "string",
                    "description": _(
                        "param.order_id.description",
                        default="Order ID (required for mode='get').",
                    ),
                },
            },
            "required": ["mode", "business_url"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    mode = str(args.get("mode") or "list").strip()
    business_url = str(args.get("business_url") or "").strip()
    order_id = str(args.get("order_id") or "").strip()

    if not business_url:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "business_url is required."},
        }, ensure_ascii=False)

    if mode == "get" and not order_id:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "order_id is required for mode='get'."},
        }, ensure_ascii=False)

    try:
        profile = discover_business(business_url)
    except Exception as exc:
        return json.dumps({
            "ok": False, "error": {"code": "discovery_failed", "message": str(exc)},
        }, ensure_ascii=False)

    try:
        if mode == "list":
            resp = ucp_request(business_url, "list-orders", method="POST", profile=profile)
        else:
            resp = ucp_request(
                business_url, "get-order",
                method="POST", body={"order_id": order_id},
                profile=profile,
            )
    except UCPError as exc:
        return json.dumps({
            "ok": False, "error": {"code": "ucp_error", "message": str(exc)},
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "ok": False, "error": {"code": "request_failed", "message": str(exc)},
        }, ensure_ascii=False)

    return json.dumps({
        "ok": True,
        "mode": mode,
        "business_url": business_url,
        "result": resp,
    }, ensure_ascii=False, indent=2)
