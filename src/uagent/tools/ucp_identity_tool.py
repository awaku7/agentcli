"""ucp_identity_tool

Link user identity (OAuth 2.0) and check linking status via UCP.
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
STATUS_LABEL = "tool:ucp_identity"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_identity",
        "description": _(
            "tool.description",
            default=(
                "Manage user identity linking via UCP. "
                "Use mode='link' to get an OAuth authorization URL for the user "
                "to authenticate in their browser, or mode='status' to check "
                "the current linking status."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["link", "status"],
                    "description": _(
                        "param.mode.description",
                        default="'link' to get OAuth URL, 'status' to check linking status.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business.",
                    ),
                },
                "redirect_uri": {
                    "type": "string",
                    "description": _(
                        "param.redirect_uri.description",
                        default="Redirect URI for OAuth callback (required for mode='link').",
                    ),
                },
                "link_id": {
                    "type": "string",
                    "description": _(
                        "param.link_id.description",
                        default="Link ID from a previous link attempt (required for mode='status').",
                    ),
                },
            },
            "required": ["mode", "business_url"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    mode = str(args.get("mode") or "link").strip()
    business_url = str(args.get("business_url") or "").strip()
    redirect_uri = str(args.get("redirect_uri") or "").strip()
    link_id = str(args.get("link_id") or "").strip()

    if not business_url:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "business_url is required."},
        }, ensure_ascii=False)

    if mode == "link" and not redirect_uri:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "redirect_uri is required for mode='link'."},
        }, ensure_ascii=False)

    if mode == "status" and not link_id:
        return json.dumps({
            "ok": False,
            "error": {"code": "invalid_argument", "message": "link_id is required for mode='status'."},
        }, ensure_ascii=False)

    try:
        profile = discover_business(business_url)
    except Exception as exc:
        return json.dumps({
            "ok": False, "error": {"code": "discovery_failed", "message": str(exc)},
        }, ensure_ascii=False)

    try:
        if mode == "link":
            resp = ucp_request(
                business_url, "identity-link",
                method="POST",
                body={"redirect_uri": redirect_uri},
                profile=profile,
            )
        else:
            resp = ucp_request(
                business_url, "identity-link-status",
                method="POST",
                body={"link_id": link_id},
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

    result: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "business_url": business_url,
        "result": resp,
    }

    # Surface authorization_url if present
    if mode == "link" and isinstance(resp, dict):
        auth_url = resp.get("authorization_url") or resp.get("auth_url") or resp.get("url")
        if auth_url:
            result["authorization_url"] = auth_url
            result["user_action_required"] = True
            result["user_action_message"] = (
                "Open the authorization_url in your browser to link your account. "
                "After authorizing, use ucp_identity mode='status' with the link_id "
                "to check if linking was successful."
            )

    return json.dumps(result, ensure_ascii=False, indent=2)
