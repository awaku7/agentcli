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
        "name": "mcp_servers_list",
        "description": _(
            "tool.description",
            default="Lists the MCP server definitions in mcp_servers.json. This tool helps visualize possible targets referenced by mcp_tools_list (when url is omitted).",
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
                "pretty": {
                    "type": "boolean",
                    "description": _(
                        "param.pretty.description",
                        default="If true, return pretty-printed JSON. Default is true.",
                    ),
                    "default": True,
                },
                "validate": {
                    "type": "boolean",
                    "description": _(
                        "param.validate.description",
                        default="If true, perform basic validation (required keys, types, duplicate names, empty URLs, etc.) and show warnings. Default is true.",
                    ),
                    "default": True,
                },
                "default_only": {
                    "type": "boolean",
                    "description": _(
                        "param.default_only.description",
                        default="If true, return only the default server (mcp_servers[0]). Default is false.",
                    ),
                    "default": False,
                },
                "raw": {
                    "type": "boolean",
                    "description": _(
                        "param.raw.description",
                        default="If true, return only the JSON string without human-readable formatting. Default is false.",
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _load_config(path: str) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []

    if not os.path.exists(path):
        return {"mcp_servers": []}, [
            _(
                "warn.not_exists",
                default="WARNING: {path!r} does not exist (treating as empty list).",
            ).format(path=path)
        ]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            warnings.append(
                _("warn.root_not_dict", default="WARNING: root is not a dictionary.")
            )
            return {"mcp_servers": []}, warnings
        if "mcp_servers" not in data:
            warnings.append(
                _(
                    "warn.no_mcp_servers",
                    default="WARNING: 'mcp_servers' key is missing (treating as empty list).",
                )
            )
            data["mcp_servers"] = []
        if not isinstance(data.get("mcp_servers"), list):
            warnings.append(
                _(
                    "warn.mcp_servers_not_list",
                    default="WARNING: 'mcp_servers' is not a list (treating as empty list).",
                )
            )
            data["mcp_servers"] = []
        return data, warnings
    except Exception as e:
        return {"mcp_servers": []}, [
            _(
                "warn.load_fail", default="WARNING: Failed to load {path!r}: {err}"
            ).format(path=path, err=e)
        ]


def _validate_servers(servers: List[Any]) -> List[str]:
    warnings: List[str] = []

    seen_names: Dict[str, int] = {}
    for idx, s in enumerate(servers):
        if not isinstance(s, dict):
            warnings.append(
                _(
                    "warn.item_not_dict",
                    default="WARNING: mcp_servers[{idx}] is not a dictionary.",
                ).format(idx=idx)
            )
            continue

        name = s.get("name")
        url = s.get("url")

        if not isinstance(name, str) or not name.strip():
            warnings.append(
                _(
                    "warn.name_missing",
                    default="WARNING: mcp_servers[{idx}].name is missing or empty.",
                ).format(idx=idx)
            )
        else:
            seen_names[name] = seen_names.get(name, 0) + 1

        if not isinstance(url, str) or not url.strip():
            warnings.append(
                _(
                    "warn.url_missing",
                    default="WARNING: mcp_servers[{idx}].url is missing or empty.",
                ).format(idx=idx)
            )
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
            warnings.append(
                _(
                    "warn.name_duplicate",
                    default="WARNING: name={name!r} is duplicated ({count} times).",
                ).format(name=n, count=c)
            )

    return warnings


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    pretty = bool(args.get("pretty", True))
    validate = bool(args.get("validate", True))
    default_only = bool(args.get("default_only", False))
    raw = bool(args.get("raw", False))

    config, load_warnings = _load_config(path)
    servers = config.get("mcp_servers", [])

    warnings: List[str] = []
    warnings.extend(load_warnings)
    if validate:
        warnings.extend(_validate_servers(servers))

    view_servers = servers[:1] if default_only else servers

    out_obj: Dict[str, Any] = {
        "path": path,
        "default_index": 0,
        "count": len(servers),
        "default": servers[0] if servers else None,
        "servers": view_servers,
        "warnings": warnings,
    }

    if raw:
        return json.dumps(out_obj, ensure_ascii=False, indent=2 if pretty else None)

    lines: List[str] = []
    lines.append(f"mcp_servers.json path: {path}")
    lines.append(f"servers count: {len(servers)}")
    if servers:
        d = servers[0]
        lines.append(
            f"default (mcp_servers[0]): name={d.get('name')!r} url={d.get('url')!r}"
        )
    else:
        lines.append("default (mcp_servers[0]): <none>")

    lines.append("")
    lines.append("servers:")
    for i, s in enumerate(view_servers):
        if isinstance(s, dict):
            lines.append(
                f"- [{i}] name={s.get('name')!r} url={s.get('url')!r} transport={s.get('transport')!r}"
            )
        else:
            lines.append(f"- [{i}] <invalid item type: {type(s).__name__}>")

    if warnings:
        lines.append("")
        lines.append("warnings:")
        for w in warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("raw JSON:")
    lines.append(json.dumps(out_obj, ensure_ascii=False, indent=2 if pretty else None))

    return cb.truncate_output("mcp_servers_list", "\n".join(lines), limit=200_000)
