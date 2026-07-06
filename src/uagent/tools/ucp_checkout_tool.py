"""ucp_checkout_tool

Manage checkout sessions via UCP — create, get, update, complete, and poll.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import time
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
                "mode='create' — start a new checkout.\n"
                "mode='get' — fetch current checkout status.\n"
                "mode='update' — modify checkout fields.\n"
                "mode='complete' — finalize the order. "
                "If the business returns requires_escalation with a continue_url, "
                "the user MUST open that URL in a browser to complete payment. "
                "After the user pays in the browser, use mode='poll' to wait for completion.\n"
                "mode='poll' — poll checkout status until completed or timeout. "
                "Use after the user completes payment via continue_url."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["create", "get", "update", "complete", "poll"],
                    "description": _(
                        "param.mode.description",
                        default="'create' / 'get' / 'update' / 'complete' / 'poll'.",
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
                        default="Checkout session ID (required for get/update/complete/poll).",
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
                "poll_timeout": {
                    "type": "integer",
                    "description": _(
                        "param.poll_timeout.description",
                        default="Max seconds to poll (mode='poll' only, default 120).",
                    ),
                },
                "poll_interval": {
                    "type": "integer",
                    "description": _(
                        "param.poll_interval.description",
                        default="Seconds between poll attempts (mode='poll' only, default 3).",
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
    poll_timeout = int(args.get("poll_timeout", 120))
    poll_interval = int(args.get("poll_interval", 3))

    if not business_url:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "business_url is required."},
        }, ensure_ascii=False)

    if mode in ("get", "update", "complete", "poll") and not checkout_id:
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
            body: dict[str, Any] = {}
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
            resp = ucp_request(
                business_url,
                "checkout-sessions/{id}/complete".format(id=checkout_id),
                method="POST", body=body if body else None,
                profile=profile, idempotent=True,
            )

        elif mode == "poll":
            return _poll_checkout(business_url, checkout_id, profile, poll_timeout, poll_interval)

        else:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_mode", "message": "Unknown mode: {mode}".format(mode=mode)},
            }, ensure_ascii=False)

    except UCPBuyerInputError as exc:
        return _build_escalation_response(checkout_id, exc)
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

    result: dict[str, Any] = {
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
        result["user_action_required"] = True
        result["user_action_message"] = (
            "Open the continue_url in your browser to complete payment. "
            "After paying, use ucp_checkout with mode='poll' and the same checkout_id "
            "to wait for the order to complete."
        )

    return json.dumps(result, ensure_ascii=False, indent=2)


def _poll_checkout(
    business_url: str,
    checkout_id: str,
    profile: dict[str, Any],
    timeout: int,
    interval: int,
) -> str:
    """Poll checkout status until completed or timeout."""
    deadline = time.monotonic() + timeout
    attempts = 0

    while time.monotonic() < deadline:
        attempts += 1
        try:
            resp = ucp_request(
                business_url,
                "checkout-sessions/{id}".format(id=checkout_id),
                method="GET", profile=profile,
            )
        except Exception:
            resp = None

        if isinstance(resp, dict):
            status = resp.get("status")
            if status == "completed":
                order_id = None
                # Some businesses return order info in the checkout response
                if "order" in resp:
                    order_id = resp["order"].get("id")
                elif "order_id" in resp:
                    order_id = resp["order_id"]

                return json.dumps({
                    "ok": True,
                    "mode": "poll",
                    "business_url": business_url,
                    "checkout_id": checkout_id,
                    "status": "completed",
                    "order_id": order_id,
                    "attempts": attempts,
                    "elapsed_seconds": int(time.monotonic() + timeout - deadline),
                    "result": resp,
                }, ensure_ascii=False, indent=2)

            if status == "canceled":
                return json.dumps({
                    "ok": False,
                    "error": {"code": "checkout_canceled", "message": "Checkout session was canceled."},
                    "checkout_id": checkout_id,
                    "attempts": attempts,
                }, ensure_ascii=False)

        time.sleep(interval)

    return json.dumps({
        "ok": False,
        "error": {
            "code": "poll_timeout",
            "message": "Checkout did not complete within {timeout} seconds. "
                       "The user may not have completed payment in the browser yet. "
                       "Try mode='poll' again with a longer timeout.".format(timeout=timeout),
        },
        "checkout_id": checkout_id,
        "attempts": attempts,
        "poll_timeout_seconds": timeout,
    }, ensure_ascii=False)


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


def _build_escalation_response(checkout_id: str, exc: UCPBuyerInputError) -> str:
    """Build a structured escalation response with user instructions."""
    continue_url = _extract_continue_url(exc)
    result: dict[str, Any] = {
        "ok": True,
        "requires_escalation": True,
        "message": "Payment requires user action in browser.",
        "checkout_id": checkout_id,
        "user_action_required": True,
        "user_action_message": (
            "Open the continue_url in your browser to complete payment. "
            "After paying, use ucp_checkout with mode='poll' and checkout_id='{chk}' "
            "to wait for the order to complete.".format(chk=checkout_id)
        ),
    }
    if continue_url:
        result["continue_url"] = continue_url
    return json.dumps(result, ensure_ascii=False, indent=2)
