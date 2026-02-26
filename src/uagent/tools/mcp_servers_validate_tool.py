from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import json
import os
from typing import Any, Dict, List, Tuple

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        return "mcp_servers.json"


from .context import get_callbacks

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_validate",
        "description": _(
            "tool.description",
            default="Validates the content of mcp_servers.json and returns warnings or errors (required keys, types, duplicate names, empty URLs, etc.).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the server list JSON. Defaults to the standard location if omitted.",
                    ),
                },
                "fail_on_warning": {
                    "type": "boolean",
                    "description": _(
                        "param.fail_on_warning.description",
                        default="If true, return overall=FAIL if there is at least one warning. Default is false.",
                    ),
                    "default": False,
                },
                "pretty": {
                    "type": "boolean",
                    "description": _(
                        "param.pretty.description",
                        default="If true, return pretty-printed JSON. Default is true.",
                    ),
                    "default": True,
                },
            },
            "required": [],
        },
    },
}


def _load_config(path: str) -> Tuple[Dict[str, Any], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not os.path.exists(path):
        errors.append(_("err.not_exists", default="ERROR: {path!r} does not exist").format(path=path))
        return {"mcp_servers": []}, warnings, errors

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        errors.append(
            _("err.load_fail", default="ERROR: Failed to load {path!r}: {err}").format(path=path, err=e)
        )
        return {"mcp_servers": []}, warnings, errors

    if not isinstance(data, dict):
        errors.append(_("err.root_not_dict", default="ERROR: root is not a dictionary"))
        return {"mcp_servers": []}, warnings, errors

    servers = data.get("mcp_servers")
    if servers is None:
        warnings.append(_("warn.no_mcp_servers", default="WARNING: 'mcp_servers' key is missing"))
        servers = []
    if not isinstance(servers, list):
        errors.append(_("err.mcp_servers_not_list", default="ERROR: 'mcp_servers' is not a list"))
        servers = []

    data["mcp_servers"] = servers
    return data, warnings, errors


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    fail_on_warning = bool(args.get("fail_on_warning", False))
    pretty = bool(args.get("pretty", True))

    config, warnings, errors = _load_config(path)
    servers: List[Any] = config.get("mcp_servers", [])

    seen_names: Dict[str, int] = {}

    for idx, s in enumerate(servers):
        if not isinstance(s, dict):
            errors.append(_("err.item_not_dict", default="ERROR: mcp_servers[{idx}] is not a dictionary").format(idx=idx))
            continue

        name = s.get("name")
        url = s.get("url")

        if not isinstance(name, str) or not name.strip():
            errors.append(_("err.name_missing", default="ERROR: mcp_servers[{idx}].name is missing or empty").format(idx=idx))
        else:
            seen_names[name] = seen_names.get(name, 0) + 1

        if not isinstance(url, str) or not url.strip():
            errors.append(_("err.url_missing", default="ERROR: mcp_servers[{idx}].url is missing or empty").format(idx=idx))
        else:
            if not url.rstrip().endswith("/mcp"):
                warnings.append(
                    _(
                        "warn.url_no_mcp",
                        default="WARNING: mcp_servers[{idx}].url={url!r} does not end with '/mcp'. (handle_mcp_v2 / mcp_tools_list will auto-append, but explicit suffix is recommended)",
                    ).format(idx=idx, url=url)
                )

    for n, c in seen_names.items():
        if c > 1:
            errors.append(_("err.name_duplicate", default="ERROR: name={name!r} is duplicated ({count} times)").format(name=n, count=c))

    overall = "OK"
    if errors:
        overall = "FAIL"
    elif warnings and fail_on_warning:
        overall = "FAIL"

    out = {
        "path": path,
        "overall": overall,
        "count": len(servers),
        "warnings": warnings,
        "errors": errors,
    }

    return cb.truncate_output(
        "mcp_servers_validate",
        json.dumps(out, ensure_ascii=False, indent=2 if pretty else None),
        limit=200_000,
    )
