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


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_set_default",
        "description": _(
            "tool.description",
            default="Changes the default MCP server (mcp_servers[0]) in mcp_servers.json by moving the specified server to the top of the list.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": _(
                        "param.server_name.description",
                        default="The name of the server to set as default (mcp_servers[].name).",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the server list JSON. Defaults to the standard location if omitted.",
                    ),
                },
                "create_if_missing": {
                    "type": "boolean",
                    "description": _(
                        "param.create_if_missing.description",
                        default="If true, create a template file if the config is missing. Default is true.",
                    ),
                    "default": True,
                },
            },
            "required": ["server_name"],
        },
    },
}


def _load_config(
    path: str, create_if_missing: bool
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []

    if not os.path.exists(path):
        if create_if_missing:
            return {"mcp_servers": []}, [
                _("warn.not_exists_new", default="WARNING: {path!r} does not exist; treating as target for new creation.").format(path=path)
            ]
        return {"mcp_servers": []}, [_("err.not_exists", default="ERROR: {path!r} does not exist").format(path=path)]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"mcp_servers": []}, [_("err.root_not_dict", default="ERROR: root is not a dictionary")]
        if "mcp_servers" not in data:
            data["mcp_servers"] = []
        if not isinstance(data.get("mcp_servers"), list):
            return {"mcp_servers": []}, [_("err.mcp_servers_not_list", default="ERROR: 'mcp_servers' is not a list")]
        return data, warnings
    except Exception as e:
        return {"mcp_servers": []}, [
            _("err.load_fail", default="ERROR: Failed to load {path!r}: {err}").format(path=path, err=e)
        ]


def run_tool(args: Dict[str, Any]) -> str:
    server_name = str(args.get("server_name", "")).strip()
    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    create_if_missing = bool(args.get("create_if_missing", True))

    if not server_name:
        return "Error: server_name is required."

    config, msgs = _load_config(path, create_if_missing)
    if any(m.startswith("ERROR:") for m in msgs):
        return "\n".join(msgs)

    servers = config.get("mcp_servers", [])
    if not servers:
        return "\n".join(
            msgs + [_("err.empty", default="ERROR: mcp_servers is empty, cannot change default.")]
        )

    idx = None
    for i, s in enumerate(servers):
        if isinstance(s, dict) and s.get("name") == server_name:
            idx = i
            break

    if idx is None:
        return "\n".join(
            msgs + [_("err.name_not_found", default="ERROR: server_name={name!r} not found.").format(name=server_name)]
        )

    if idx == 0:
        return "\n".join(msgs + [_("out.already_default", default="OK: Already set as default: {name!r}").format(name=server_name)])

    item = servers.pop(idx)
    servers.insert(0, item)
    config["mcp_servers"] = servers

    text = json.dumps(config, ensure_ascii=False, indent=2)
    try:
        try:
            from .create_file_tool import run_tool as create_file
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return _("out.ok", default="OK: Changed default: {name!r}").format(name=server_name) + " (Note: create_file_tool import failed, direct write used)"

        create_file(
            {"filename": path, "content": text, "encoding": "utf-8", "overwrite": True}
        )
    except Exception as e:
        return _("err.write_fail", default="ERROR: Failed to write file: {err}").format(err=e)

    return "\n".join(
        msgs
        + [
            _("out.ok", default="OK: Changed default: {name!r}").format(name=server_name),
            f"default url: {servers[0].get('url')!r}",
        ]
    )
