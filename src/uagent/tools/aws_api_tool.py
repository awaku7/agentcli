from __future__ import annotations

import json
import os
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_READONLY_PREFIXES = (
    "BatchGet",
    "Check",
    "Describe",
    "Get",
    "Head",
    "List",
    "Lookup",
    "Preview",
    "Query",
    "Read",
    "Retrieve",
    "Scan",
    "Search",
    "Select",
    "Validate",
)


def _boto_session() -> Any:
    try:
        import boto3
    except ImportError:
        from .._pip_auto import install_with_status

        if not install_with_status(
            "boto3",
            display_name="boto3",
            version_spec=">=1.35.0",
        ):
            raise RuntimeError("Automatic boto3 installation failed.")
        import boto3
    access_key = os.getenv("UAGENT_AWS_ACCESS_KEY_ID") or None
    secret_key = os.getenv("UAGENT_AWS_SECRET_ACCESS_KEY") or None
    return boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=os.getenv("UAGENT_AWS_SESSION_TOKEN") or None,
        profile_name=(
            (os.getenv("UAGENT_AWS_PROFILE") or None)
            if not (access_key and secret_key)
            else None
        ),
        region_name=os.getenv("UAGENT_AWS_REGION") or None,
    )


def _service_names(session: Any) -> list[str]:
    return sorted(session.get_available_services())


def _client(session: Any, service: str, region: str | None) -> Any:
    name = str(service or "").strip().lower()
    if name not in _service_names(session):
        raise ValueError(f"Unsupported AWS service: {service}")
    return session.client(name, region_name=region or None)


def _readonly_operations(client: Any) -> list[str]:
    names = []
    for name in client.meta.service_model.operation_names:
        if name.startswith(_READONLY_PREFIXES):
            names.append(name)
    return sorted(names)


def _all_operations(client: Any) -> list[str]:
    return sorted(client.meta.service_model.operation_names)


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


def run_tool(args: dict[str, Any]) -> str:
    """List AWS services/operations or execute an AWS API call with write confirmation."""
    action = str(args.get("action", "list_services")).strip().lower()
    region = str(args.get("region", "")).strip() or None
    session = _boto_session()

    try:
        if action == "list_services":
            return json.dumps({"services": _service_names(session)}, ensure_ascii=False)

        service = str(args.get("service", "")).strip()
        if not service:
            raise ValueError("service is required for this action")
        client = _client(session, service, region)

        if action == "list_operations":
            include_write = bool(args.get("include_write", False))
            return json.dumps(
                {
                    "service": service,
                    "read_only": not include_write,
                    "operations": (
                        _all_operations(client)
                        if include_write
                        else _readonly_operations(client)
                    ),
                },
                ensure_ascii=False,
            )

        if action != "call":
            raise ValueError("action must be list_services, list_operations, or call")

        operation = str(args.get("operation", "")).strip()
        if not operation:
            raise ValueError("operation is required for call")
        confirm_write = bool(args.get("confirm_write", False))
        readonly = operation.startswith(_READONLY_PREFIXES)
        if not readonly and not confirm_write:
            raise PermissionError(
                f"Read-only policy rejected operation: {operation}. "
                "Set confirm_write=true to explicitly authorize a write operation."
            )
        allowed = (
            _all_operations(client) if confirm_write else _readonly_operations(client)
        )
        if operation not in allowed:
            raise ValueError(f"Unknown AWS operation: {operation}")

        raw_params = args.get("parameters", "{}")
        if isinstance(raw_params, str):
            parameters = json.loads(raw_params or "{}")
        elif isinstance(raw_params, dict):
            parameters = raw_params
        else:
            raise ValueError("parameters must be a JSON object or JSON string")
        if not isinstance(parameters, dict):
            raise ValueError("parameters must decode to a JSON object")

        result = getattr(client, operation)(**parameters)
        return json.dumps(
            {"service": service, "operation": operation, "result": _jsonable(result)},
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
        "name": "aws_api",
        "description": _(
            "tool.description",
            default=(
                "Tool for all AWS services. List services, list API operations, and call a selected AWS API."
                "Write operations require explicit confirmation."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["aws", "amazon web services", "boto3", "cloud", "aws_api"],
        ),
        "x_search_terms_en": [
            "aws",
            "amazon web services",
            "boto3",
            "cloud",
            "aws_api",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_services", "list_operations", "call"],
                    "default": "list_services",
                    "description": _(
                        "param.action",
                        default="Action to perform.",
                    ),
                },
                "service": {
                    "type": "string",
                    "description": _(
                        "param.service",
                        default="AWS service name, e.g. ec2 or s3.",
                    ),
                },
                "operation": {
                    "type": "string",
                    "description": _(
                        "param.operation",
                        default="Read-only boto3 client operation, e.g. DescribeInstances.",
                    ),
                },
                "parameters": {
                    "type": "string",
                    "description": _(
                        "param.parameters",
                        default="JSON object containing the operation parameters.",
                    ),
                },
                "region": {
                    "type": "string",
                    "description": _(
                        "param.region",
                        default="Optional AWS region; otherwise use the configured default.",
                    ),
                },
                "include_write": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.include_write",
                        default="For list_operations, include write-capable operations.",
                    ),
                },
                "confirm_write": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.confirm_write",
                        default=(
                            "Required true to execute a non-read-only AWS operation. "
                            "This is an explicit write confirmation."
                        ),
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}
