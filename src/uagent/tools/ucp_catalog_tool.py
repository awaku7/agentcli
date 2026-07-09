"""ucp_catalog_tool

Search and lookup products in a UCP-enabled business catalog.
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
STATUS_LABEL = "tool:ucp_catalog"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "ucp_catalog",
        "description": _(
            "tool.description",
            default=(
                "Search or lookup products in a UCP-enabled business catalog. "
                "Use mode='search' for keyword search or mode='lookup' for "
                "fetching product details by item IDs."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["search", "lookup"],
                    "description": _(
                        "param.mode.description",
                        default="'search' for keyword search, 'lookup' for product detail by ID.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business (e.g. 'https://example.shop').",
                    ),
                },
                "query": {
                    "type": "string",
                    "description": _(
                        "param.query.description",
                        default="Search query string (required for mode='search').",
                    ),
                },
                "item_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.item_ids.description",
                        default="List of item IDs to look up (required for mode='lookup').",
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
    mode = str(args.get("mode") or "search").strip()
    business_url = str(args.get("business_url") or "").strip()
    query = str(args.get("query") or "").strip()
    item_ids = args.get("item_ids")
    currency = str(args.get("currency") or "").strip() or None

    if not business_url:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "business_url is required.",
                },
            },
            ensure_ascii=False,
        )

    if mode == "search" and not query:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "query is required for mode='search'.",
                },
            },
            ensure_ascii=False,
        )

    if mode == "lookup" and not item_ids:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "item_ids is required for mode='lookup'.",
                },
            },
            ensure_ascii=False,
        )

    try:
        profile = discover_business(business_url)
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": {"code": "discovery_failed", "message": str(exc)},
            },
            ensure_ascii=False,
        )

    try:
        if mode == "search":
            body = {"query": query}
            if currency:
                body["currency"] = currency
            resp = ucp_request(business_url, "search", body=body, profile=profile)
        else:
            ids = item_ids if isinstance(item_ids, list) else [str(item_ids)]
            resp = ucp_request(
                business_url,
                "lookup-catalog",
                body={"item_ids": ids},
                profile=profile,
            )
    except UCPError as exc:
        return json.dumps(
            {
                "ok": False,
                "error": {"code": "ucp_error", "message": str(exc)},
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": {"code": "request_failed", "message": str(exc)},
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "ok": True,
            "mode": mode,
            "business_url": business_url,
            "results": resp,
        },
        ensure_ascii=False,
        indent=2,
    )
