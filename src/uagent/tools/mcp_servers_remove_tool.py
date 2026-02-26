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
        "name": "mcp_servers_remove",
        "description": _(
            "tool.description",
            default="Removes an MCP server definition from mcp_servers.json. You can specify by name or index (one is required).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="The name of the server to remove (mcp_servers[].name).",
                    ),
                },
                "index": {
                    "type": "integer",
                    "description": _(
                        "param.index.description",
                        default="The index of the server to remove (mcp_servers[n]). If specified with name, index takes priority.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the server list JSON. Defaults to the standard location if omitted.",
                    ),
                },
                "require_nonempty": {
                    "type": "boolean",
                    "description": _(
                        "param.require_nonempty.description",
                        default="If true, prevent the operation if it would leave the list empty. Default is false.",
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _load_config(path: str) -> Tuple[Dict[str, Any], List[str]]:
    if not os.path.exists(path):
        return {"mcp_servers": []}, [
            _("err.not_exists", default="ERROR: {path!r} does not exist").format(path=path)
        ]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"mcp_servers": []}, [_("err.root_not_dict", default="ERROR: root is not a dictionary")]
        if "mcp_servers" not in data:
            data["mcp_servers"] = []
        if not isinstance(data.get("mcp_servers"), list):
            return {"mcp_servers": []}, [_("err.mcp_servers_not_list", default="ERROR: 'mcp_servers' is not a list")]
        return data, []
    except Exception as e:
        return {"mcp_servers": []}, [
            _("err.load_fail", default="ERROR: Failed to load {path!r}: {err}").format(path=path, err=e)
        ]


def run_tool(args: Dict[str, Any]) -> str:
    name = args.get("name")
    index = args.get("index")
    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    require_nonempty = bool(args.get("require_nonempty", False))

    if index is None and (not isinstance(name, str) or not name.strip()):
        return _("err.name_or_index_required", default="Error: Please specify either name or index.")

    config, msgs = _load_config(path)
    if any(m.startswith("ERROR:") for m in msgs):
        return "\n".join(msgs)

    servers = config.get("mcp_servers", [])
    if not servers:
        return _("err.empty", default="ERROR: mcp_servers is empty")

    removed = None
    removed_idx = None

    if index is not None:
        try:
            idx = int(index)
        except Exception:
            return _("err.index_not_int", default="Error: index must be an integer.")
        if idx < 0 or idx >= len(servers):
            return _("err.index_out_of_range", default="Error: index out of range: {idx}").format(idx=idx)
        removed = servers.pop(idx)
        removed_idx = idx
    else:
        target = str(name).strip()
        for i, s in enumerate(servers):
            if isinstance(s, dict) and s.get("name") == target:
                removed = servers.pop(i)
                removed_idx = i
                break
        if removed is None:
            return _("err.name_not_found", default="Error: name={name!r} not found.").format(name=target)

    if require_nonempty and not servers:
        return _("err.require_nonempty", default="Error: require_nonempty=true, so removing the last item is not allowed.")

    config["mcp_servers"] = servers

    text = json.dumps(config, ensure_ascii=False, indent=2)
    try:
        try:
            from .create_file_tool import run_tool as create_file
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

            r_name = removed.get("name") if isinstance(removed, dict) else None
            return (
                _("out.ok", default="OK: removed index={idx} name={name!r}").format(idx=removed_idx, name=r_name) +
                " (Note: create_file_tool import failed, direct write used)"
            )

        create_file(
            {"filename": path, "content": text, "encoding": "utf-8", "overwrite": True}
        )
    except Exception as e:
        return _("err.write_fail", default="ERROR: Failed to write file: {err}").format(err=e)

    default_info = "<none>"
    if servers:
        default_info = f"name={servers[0].get('name')!r} url={servers[0].get('url')!r}"

    r_name = removed.get("name") if isinstance(removed, dict) else None

    return "\n".join(
        [
            _("out.ok", default="OK: removed index={idx} name={name!r}").format(idx=removed_idx, name=r_name),
            f"default: {default_info}",
            f"count: {len(servers)}",
        ]
    )
