from __future__ import annotations

import json
import os
from typing import Any

import requests

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_DISCOVERY_URL = "https://www.googleapis.com/discovery/v1/apis"
_READONLY_METHODS = {
    "get",
    "list",
    "aggregatedList",
    "search",
    "query",
    "check",
    "validate",
    "testIamPermissions",
    "getIamPolicy",
}


def _google_credentials() -> Any:
    credentials_file = os.getenv("UAGENT_GCP_CREDENTIALS_FILE", "").strip()
    if credentials_file:
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(credentials_file)
    try:
        import google.auth

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials
    except Exception:
        return None


def _ensure_google_client() -> Any:
    try:
        from googleapiclient import discovery
    except ImportError:
        from .._pip_auto import install_with_status

        if not install_with_status(
            "google-api-python-client",
            module_name="googleapiclient",
            display_name="Google API Python Client",
            version_spec=">=2.160.0",
        ):
            raise RuntimeError("Automatic Google API Python Client installation failed.")
        from googleapiclient import discovery
    return discovery


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _discovery_services() -> list[dict[str, Any]]:
    response = requests.get(_DISCOVERY_URL, params={"preferred": "true"}, timeout=30)
    response.raise_for_status()
    data = response.json()
    return [
        {
            "name": item.get("name"),
            "title": item.get("title"),
            "id": item.get("id"),
            "version": item.get("version"),
            "discoveryRestUrl": item.get("discoveryRestUrl"),
        }
        for item in data.get("items", [])
    ]


def _discovery_doc(api: str, version: str) -> dict[str, Any]:
    url = f"https://{api}.googleapis.com/$discovery/rest?version={version}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _methods(resources: dict[str, Any], prefix: str = "") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for resource_name, resource in resources.items():
        resource_path = f"{prefix}.{resource_name}" if prefix else resource_name
        for method_name in resource.get("methods", {}):
            found.append(
                {
                    "resource": resource_path,
                    "method": method_name,
                    "read_only": method_name in _READONLY_METHODS,
                }
            )
        found.extend(_methods(resource.get("resources", {}), resource_path))
    return found


def _resource_object(service: Any, resource_path: str) -> Any:
    current = service
    for part in resource_path.split("."):
        current = getattr(current, part)()
    return current


def run_tool(args: dict[str, Any]) -> str:
    """List Google APIs/methods or execute a Google API call."""
    action = str(args.get("action", "list_services")).strip().lower()
    try:
        if action == "list_services":
            return json.dumps({"services": _discovery_services()}, ensure_ascii=False)

        api = str(args.get("api", "")).strip()
        version = str(args.get("version", "")).strip()
        if not api or not version:
            raise ValueError("api and version are required for this action")

        if action == "list_methods":
            doc = _discovery_doc(api, version)
            methods = _methods(doc.get("resources", {}))
            if not bool(args.get("include_write", False)):
                methods = [item for item in methods if item["read_only"]]
            return json.dumps(
                {"api": api, "version": version, "methods": methods}, ensure_ascii=False
            )

        if action != "call":
            raise ValueError("action must be list_services, list_methods, or call")

        resource = str(args.get("resource", "")).strip()
        method = str(args.get("method", "")).strip()
        if not resource or not method:
            raise ValueError("resource and method are required for call")

        confirm_write = bool(args.get("confirm_write", False))
        readonly = method in _READONLY_METHODS
        if not readonly and not confirm_write:
            raise PermissionError(
                f"Read-only policy rejected method: {resource}.{method}. "
                "Set confirm_write=true to explicitly authorize a write operation."
            )

        discovery = _ensure_google_client()
        service = discovery.build(
            api,
            version,
            credentials=_google_credentials(),
            cache_discovery=False,
        )
        target = getattr(_resource_object(service, resource), method)
        raw_params = args.get("parameters", "{}")
        if isinstance(raw_params, str):
            parameters = json.loads(raw_params or "{}")
        elif isinstance(raw_params, dict):
            parameters = dict(raw_params)
        else:
            raise ValueError("parameters must be a JSON object or JSON string")
        body = args.get("body")
        if body is not None:
            if isinstance(body, str):
                body = json.loads(body)
            parameters["body"] = body
        result = target(**parameters).execute()
        return json.dumps(
            {"api": api, "version": version, "resource": resource, "method": method, "result": _jsonable(result)},
            ensure_ascii=False,
        )
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
        "name": "gcp_api",
        "description": _(
            "tool.description",
            default=(
                "Generic API tool for all GCP services. List services and API methods through Google API Discovery, and "
                "call read/write APIs. Write operations require explicit confirmation."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["gcp", "google cloud", "google api", "cloud", "gcp_api"],
        ),
        "x_search_terms_en": ["gcp", "google cloud", "google api", "cloud", "gcp_api"],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_services", "list_methods", "call"], "default": "list_services"},
                "api": {"type": "string", "description": _("param.api", default="Google API name, for example compute or storage.")},
                "version": {"type": "string", "description": _("param.version", default="API version, for example v1 or v1beta1.")},
                "resource": {"type": "string", "description": _("param.resource", default="Dot-separated resource path, for example projects.locations.")},
                "method": {"type": "string", "description": _("param.method", default="API method, for example get, list, insert, or delete.")},
                "parameters": {"type": "string", "description": _("param.parameters", default="JSON object containing query/path parameters.")},
                "body": {"type": "string", "description": _("param.body", default="Optional JSON request body.")},
                "include_write": {"type": "boolean", "default": False, "description": _("param.include_write", default="For list_methods, include write-capable methods.")},
                "confirm_write": {"type": "boolean", "default": False, "description": _("param.confirm_write", default="Required true to execute a non-read-only method.")},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}
