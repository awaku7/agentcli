from __future__ import annotations

import json
import os
from typing import Any

import requests

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_ARM = "https://management.azure.com"
_API_VERSION = "2021-04-01"


def _credential() -> Any:
    try:
        from azure.identity import AzureCliCredential, ClientSecretCredential
    except ImportError:
        from .._pip_auto import install_with_status

        if not install_with_status(
            "azure-identity",
            display_name="Azure Identity",
            version_spec=">=1.19.0",
        ):
            raise RuntimeError("Automatic Azure Identity installation failed.")
        from azure.identity import AzureCliCredential, ClientSecretCredential

    tenant = os.getenv("UAGENT_AZURE_TENANT_ID", "").strip()
    client = os.getenv("UAGENT_AZURE_CLIENT_ID", "").strip()
    secret = os.getenv("UAGENT_AZURE_CLIENT_SECRET", "")
    if tenant and client and secret:
        return ClientSecretCredential(tenant_id=tenant, client_id=client, client_secret=secret)
    return AzureCliCredential()


def _subscription_id() -> str:
    value = os.getenv("UAGENT_AZURE_SUBSCRIPTION_ID", "").strip()
    if not value:
        raise ValueError("UAGENT_AZURE_SUBSCRIPTION_ID is required")
    return value


def _request(method: str, url: str, params: dict[str, Any] | None = None, body: Any = None) -> Any:
    credential = _credential()
    token = credential.get_token("https://management.azure.com/.default").token
    response = requests.request(
        method.upper(),
        url,
        params=params,
        json=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    if not response.content:
        return {"status_code": response.status_code}
    try:
        return response.json()
    except ValueError:
        return response.text


def _url(value: str) -> str:
    raw = value.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if not raw.startswith("/"):
        raw = "/" + raw
    return _ARM + raw


def run_tool(args: dict[str, Any]) -> str:
    """List Azure providers/operations or execute an ARM REST API call."""
    action = str(args.get("action", "list_providers")).strip().lower()
    try:
        subscription = _subscription_id()
        if action == "list_providers":
            result = _request(
                "GET",
                f"{_ARM}/subscriptions/{subscription}/providers",
                {"api-version": _API_VERSION},
            )
            return json.dumps(result, ensure_ascii=False)

        provider = str(args.get("provider", "")).strip()
        api_version = str(args.get("api_version", _API_VERSION)).strip()
        if action == "list_operations":
            if not provider:
                raise ValueError("provider is required for list_operations")
            result = _request(
                "GET",
                f"{_ARM}/providers/{provider}/operations",
                {"api-version": api_version},
            )
            return json.dumps(result, ensure_ascii=False)

        if action != "call":
            raise ValueError("action must be list_providers, list_operations, or call")

        method = str(args.get("method", "GET")).strip().upper()
        resource = str(args.get("resource", "")).strip()
        if not resource:
            raise ValueError("resource is required for call")
        if method != "GET" and not bool(args.get("confirm_write", False)):
            raise PermissionError(
                f"Read-only policy rejected HTTP method: {method}. "
                "Set confirm_write=true to explicitly authorize a write operation."
            )
        raw_params = args.get("parameters", "{}")
        if isinstance(raw_params, str):
            parameters = json.loads(raw_params or "{}")
        elif isinstance(raw_params, dict):
            parameters = raw_params
        else:
            raise ValueError("parameters must be a JSON object or JSON string")
        parameters.setdefault("api-version", api_version)
        body = args.get("body")
        if isinstance(body, str) and body.strip():
            body = json.loads(body)
        result = _request(method, _url(resource), parameters, body)
        return json.dumps({"method": method, "resource": resource, "result": result}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": type(exc).__name__, "message": str(exc)},
            ensure_ascii=False,
        )


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "external",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "azure_api",
        "description": _(
            "tool.description",
            default=(
                "Generic REST API tool for all Azure services. List providers through Azure Resource Manager API, "
                "list operations, and call read/write APIs. Write operations require explicit confirmation."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["azure", "microsoft azure", "azure arm", "cloud", "azure_api"],
        ),
        "x_search_terms_en": ["azure", "microsoft azure", "azure arm", "cloud", "azure_api"],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_providers", "list_operations", "call"], "default": "list_providers"},
                "provider": {"type": "string", "description": _("param.provider", default="Azure resource provider namespace, for example Microsoft.Compute.")},
                "resource": {"type": "string", "description": _("param.resource", default="ARM resource path or full management URL.")},
                "method": {"type": "string", "default": "GET", "description": _("param.method", default="HTTP method, for example GET, PUT, POST, PATCH, or DELETE.")},
                "api_version": {"type": "string", "default": _API_VERSION, "description": _("param.api_version", default="Azure API version.")},
                "parameters": {"type": "string", "description": _("param.parameters", default="JSON object containing query parameters.")},
                "body": {"type": "string", "description": _("param.body", default="Optional JSON request body.")},
                "confirm_write": {"type": "boolean", "default": False, "description": _("param.confirm_write", default="Required true for non-GET operations.")},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}
