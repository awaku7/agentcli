"""ucp_discover_tool

Discover a business's UCP capabilities and negotiate available features.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
from typing import Any

from .ucp_shared import (
    discover_business,
    negotiate_capabilities,
    resolve_endpoint,
    resolve_mcp_endpoint,
    get_payment_handlers,
    UCPUnrecoverableError,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:ucp_discover"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_discover",
        "description": _(
            "tool.description",
            default=(
                "Discover a business's UCP (Universal Commerce Protocol) capabilities. "
                "Fetches the /.well-known/ucp profile and returns supported services, "
                "transports, capabilities, and authentication methods."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business (e.g. 'https://example.shop').",
                    ),
                },
            },
            "required": ["business_url"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    business_url = str(args.get("business_url") or "").strip()

    if not business_url:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.missing_business_url",
                    default="Error: business_url is required.",
                ),
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    try:
        profile = discover_business(business_url)
    except UCPUnrecoverableError as exc:
        payload = {
            "ok": False,
            "error": {
                "code": "ucp_not_supported",
                "message": str(exc),
            },
        }
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        payload = {
            "ok": False,
            "error": {
                "code": "discovery_failed",
                "message": f"Discovery failed: {exc}",
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    ucp = profile.get("ucp", profile)
    capabilities = ucp.get("capabilities", {})
    services = ucp.get("services", {})
    version = ucp.get("version", "unknown")
    payment_handlers = get_payment_handlers(profile)
    endpoint = resolve_endpoint(profile)

    # Negotiate with default platform profile
    negotiated = negotiate_capabilities(profile)

    cap_list = []
    for cap_name in sorted(capabilities.keys()):
        cap_list.append(
            {
                "name": cap_name,
                "version": capabilities[cap_name][0].get("version", "unknown")
                if isinstance(capabilities[cap_name], list) and capabilities[cap_name]
                else "unknown",
                "negotiated": cap_name in negotiated,
            }
        )

    transport_list = []
    for svc_name, svc_def in services.items() if isinstance(services, dict) else []:
        if isinstance(svc_def, list):
            for t in svc_def:
                if isinstance(t, dict):
                    transport_list.append(
                        {
                            "service": svc_name,
                            "transport": t.get("transport", "unknown"),
                            "endpoint": t.get("endpoint", ""),
                        }
                    )
        elif isinstance(svc_def, dict):
            transport_list.append(
                {
                    "service": svc_name,
                    "transport": svc_def.get("transport", "rest"),
                    "endpoint": svc_def.get("endpoint", ""),
                }
            )

    result = {
        "ok": True,
        "business_url": business_url,
        "ucp_version": version,
        "capabilities": cap_list,
        "transports": transport_list,
        "rest_endpoint": endpoint,
        "mcp_endpoint": resolve_mcp_endpoint(profile),
        "payment_handlers": [
            {
                "id": h.get("id", ""),
                "spec": h.get("spec", ""),
            }
            for h in payment_handlers
        ],
        "negotiated_count": len(negotiated),
        "negotiated_capabilities": list(negotiated.keys()),
    }

    return json.dumps(result, ensure_ascii=False, indent=2)
