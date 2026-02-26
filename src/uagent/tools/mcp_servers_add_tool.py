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
        env_path = os.environ.get("UAGENT_MCP_CONFIG")
        if env_path:
            return os.path.abspath(os.path.expanduser(env_path))

        try:
            from uagent.utils.paths import get_mcp_servers_json_path

            return str(get_mcp_servers_json_path())
        except Exception:
            p_new = os.path.join(
                os.path.expanduser("~"), ".uag", "mcps", "mcp_servers.json"
            )
            if os.path.exists(p_new):
                return p_new
            return os.path.join(
                os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json"
            )


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_add",
        "description": _(
            "tool.description",
            default=(
                "Add a server definition to mcp_servers.json (or update an existing one). "
                "If the same name already exists, it is only overwritten when replace=true. "
                "For HTTP(SSE) connections, provide url. For stdio connections, provide command and args."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Add or update an MCP server entry in mcp_servers.json.\n"
                "- Be careful when overwriting existing entries (replace=true).\n"
                "- For HTTP(SSE): set url.\n"
                "- For stdio: set command and args.\n"
                "- Do not store secrets (tokens, passwords) in this file unless the user explicitly requests it."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="Server name (mcp_servers[].name).",
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default=(
                            "MCP endpoint URL (e.g., REPLACE_ME (set your MCP server URL)). "
                            "Omit for stdio connections."
                        ),
                    ),
                },
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="Command to execute for stdio connections (e.g., npx, python, docker).",
                    ),
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.args.description",
                        default="Command arguments for stdio connections.",
                    ),
                },
                "env": {
                    "type": "object",
                    "description": _(
                        "param.env.description",
                        default="Environment variables (mapping) for stdio connections.",
                    ),
                },
                "transport": {
                    "type": "string",
                    "description": _(
                        "param.transport.description",
                        default="Transport (informational). One of streamable-http or stdio.",
                    ),
                    "default": "streamable-http",
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the server list JSON file. If omitted, uses the default location.",
                    ),
                },
                "set_default": {
                    "type": "boolean",
                    "description": _(
                        "param.set_default.description",
                        default=(
                            "If true, make this server the default entry (move to index 0) after adding/updating. "
                            "Default: false."
                        ),
                    ),
                    "default": False,
                },
                "replace": {
                    "type": "boolean",
                    "description": _(
                        "param.replace.description",
                        default="If true, overwrite an existing entry with the same name. Default: false.",
                    ),
                    "default": False,
                },
                "create_if_missing": {
                    "type": "boolean",
                    "description": _(
                        "param.create_if_missing.description",
                        default="If true, create the file if it does not exist. Default: true.",
                    ),
                    "default": True,
                },
            },
            "required": ["name"],
        },
    },
}


def _load_config(
    path: str, create_if_missing: bool
) -> Tuple[Dict[str, Any], List[str]]:
    if not os.path.exists(path):
        if create_if_missing:
            return {"mcp_servers": []}, [
                f"WARNING: {path!r} does not exist; creating a new file"
            ]
        return {"mcp_servers": []}, [f"ERROR: {path!r} does not exist"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"mcp_servers": []}, ["ERROR: root is not a JSON object"]
        if "mcp_servers" not in data:
            data["mcp_servers"] = []
        if not isinstance(data.get("mcp_servers"), list):
            return {"mcp_servers": []}, ["ERROR: 'mcp_servers' is not a list"]
        return data, []
    except Exception as e:
        return {"mcp_servers": []}, [
            f"ERROR: failed to load JSON: {type(e).__name__}: {e}"
        ]


def _save_config(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_tool(args: Dict[str, Any]) -> str:
    name = str(args.get("name") or "").strip()
    url = args.get("url")
    command = args.get("command")
    arg_list = args.get("args")
    env = args.get("env")
    transport = str(args.get("transport") or "streamable-http")

    path = args.get("path")
    set_default = bool(args.get("set_default", False))
    replace = bool(args.get("replace", False))
    create_if_missing = bool(args.get("create_if_missing", True))

    if not name:
        return json.dumps(
            {"ok": False, "error": "name is required"}, ensure_ascii=False
        )

    config_path = str(path or get_default_mcp_config_path())

    data, msgs = _load_config(config_path, create_if_missing=create_if_missing)
    servers = data.get("mcp_servers") or []

    # Normalize args/env
    if arg_list is None:
        arg_list = []
    if env is None:
        env = {}

    if not isinstance(arg_list, list):
        return json.dumps(
            {"ok": False, "error": "args must be an array"}, ensure_ascii=False
        )
    if not isinstance(env, dict):
        return json.dumps(
            {"ok": False, "error": "env must be an object"}, ensure_ascii=False
        )

    # Find existing
    idx = None
    for i, s in enumerate(servers):
        if isinstance(s, dict) and s.get("name") == name:
            idx = i
            break

    new_entry: Dict[str, Any] = {
        "name": name,
        "transport": transport,
    }
    if url:
        new_entry["url"] = str(url)
    if command:
        new_entry["command"] = str(command)
    if arg_list:
        new_entry["args"] = [str(x) for x in arg_list]
    if env:
        # stringify keys/values defensively
        new_entry["env"] = {str(k): str(v) for k, v in env.items()}

    if idx is None:
        servers.append(new_entry)
        idx = len(servers) - 1
    else:
        if not replace:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"server {name!r} already exists (set replace=true to overwrite)",
                    "path": config_path,
                },
                ensure_ascii=False,
            )
        servers[idx] = new_entry

    if set_default and idx != 0:
        servers.insert(0, servers.pop(idx))

    data["mcp_servers"] = servers

    _save_config(config_path, data)

    return json.dumps(
        {
            "ok": True,
            "path": config_path,
            "count": len(servers),
            "warnings": [m for m in msgs if m.startswith("WARNING")],
        },
        ensure_ascii=False,
    )
