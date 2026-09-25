from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# mcp_tools_list: only managed server_name entries may enable trusted HTTP propagation.
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "    from .mcp_servers_shared import get_default_mcp_config_path\n",
    "    from .mcp_servers_shared import (\n"
    "        get_default_mcp_config_path,\n"
    "        is_trusted_mcp_trace_propagation_enabled,\n"
    "    )\n",
)
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "    def get_default_mcp_config_path():\n",
    "    def is_trusted_mcp_trace_propagation_enabled(server: Any) -> bool:\n"
    "        return (\n"
    "            isinstance(server, dict)\n"
    "            and server.get(\"trusted_trace_propagation\") is True\n"
    "        )\n\n"
    "    def get_default_mcp_config_path():\n",
)
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "    protocol_mode: str = \"auto\",\n) -> dict[str, Any]:\n",
    "    protocol_mode: str = \"auto\",\n"
    "    trusted_trace_propagation: bool = False,\n"
    ") -> dict[str, Any]:\n",
)
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "    async with MCPClient(\n        url=url, headers=headers or {}, protocol_mode=protocol_mode\n    ) as client:\n",
    "    async with MCPClient(\n"
    "        url=url,\n"
    "        headers=headers or {},\n"
    "        protocol_mode=protocol_mode,\n"
    "        trusted_trace_propagation=trusted_trace_propagation,\n"
    "    ) as client:\n",
)
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "    http_headers: dict[str, str] = {}\n\n    if (not url) and server_name:\n",
    "    http_headers: dict[str, str] = {}\n"
    "    trusted_trace_propagation = False\n\n"
    "    if (not url) and server_name:\n",
)
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "                            http_headers = _resolve_http_headers(s.get(\"headers\"))\n",
    "                            http_headers = _resolve_http_headers(s.get(\"headers\"))\n"
    "                            trusted_trace_propagation = (\n"
    "                                is_trusted_mcp_trace_propagation_enabled(s)\n"
    "                            )\n",
)
replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "                _mcp_tools_list_http(str(url), http_headers, protocol_mode)\n",
    "                _mcp_tools_list_http(\n"
    "                    str(url),\n"
    "                    http_headers,\n"
    "                    protocol_mode,\n"
    "                    trusted_trace_propagation,\n"
    "                )\n",
)


# Resources resolver is shared by Resources, Prompts, and Discover.
replace_once(
    "src/uagent/tools/mcp_resources_tool.py",
    "from .mcp_servers_shared import get_default_mcp_config_path\n",
    "from .mcp_servers_shared import (\n"
    "    get_default_mcp_config_path,\n"
    "    is_trusted_mcp_trace_propagation_enabled,\n"
    ")\n",
)
old = '''            return {
                "url": server.get("url") or None,
                "command": server.get("command") or None,
                "args": [str(item) for item in server.get("args", [])],
                "env": {str(k): str(v) for k, v in (server.get("env") or {}).items()},
                "headers": _headers(server.get("headers")),
                "protocol_mode": mode,
            }, server_name
'''
new = '''            resolved_url = server.get("url") or None
            connection = {
                "url": resolved_url,
                "command": server.get("command") or None,
                "args": [str(item) for item in server.get("args", [])],
                "env": {str(k): str(v) for k, v in (server.get("env") or {}).items()},
                "headers": _headers(server.get("headers")),
                "protocol_mode": mode,
            }
            if isinstance(resolved_url, str) and resolved_url.lower().startswith(
                ("http://", "https://")
            ):
                connection["trusted_trace_propagation"] = (
                    is_trusted_mcp_trace_propagation_enabled(server)
                )
            return connection, server_name
'''
replace_once("src/uagent/tools/mcp_resources_tool.py", old, new)


# mcp_servers management surface: schema, strict boolean validation, persisted field.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    '''                "protocol_mode": {
                    "type": "string",
                    "enum": ["auto", "legacy", "stateless"],
                    "description": _(
                        "param.protocol_mode.description",
                        default="(add) MCP protocol mode: auto, legacy, or stateless.",
                    ),
                    "default": "auto",
                },
''',
    '''                "protocol_mode": {
                    "type": "string",
                    "enum": ["auto", "legacy", "stateless"],
                    "description": _(
                        "param.protocol_mode.description",
                        default="(add) MCP protocol mode: auto, legacy, or stateless.",
                    ),
                    "default": "auto",
                },
                "trusted_trace_propagation": {
                    "type": "boolean",
                    "description": _(
                        "param.trusted_trace_propagation.description",
                        default=(
                            "(add/init_template) Explicitly trust this managed HTTP MCP "
                            "server for W3C trace propagation. Default: false."
                        ),
                    ),
                    "default": False,
                },
''',
)
# List validation: malformed values and stdio/no-HTTP true are visible.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "        command = s.get(\"command\")\n\n        if not isinstance(name, str) or not name.strip():\n",
    "        command = s.get(\"command\")\n"
    "        trusted_trace = s.get(\"trusted_trace_propagation\", False)\n"
    "        if (\n"
    "            \"trusted_trace_propagation\" in s\n"
    "            and not isinstance(trusted_trace, bool)\n"
    "        ):\n"
    "            warnings.append(\n"
    "                f\"WARNING: mcp_servers[{idx}].trusted_trace_propagation must be boolean.\"\n"
    "            )\n"
    "        elif trusted_trace is True and not (\n"
    "            isinstance(url, str) and url.lower().startswith((\"http://\", \"https://\"))\n"
    "        ):\n"
    "            warnings.append(\n"
    "                f\"WARNING: mcp_servers[{idx}].trusted_trace_propagation is ignored for non-HTTP transports.\"\n"
    "            )\n\n"
    "        if not isinstance(name, str) or not name.strip():\n",
)
# Strict validation occurs after has_http/has_stdio are known.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "        has_http = isinstance(url, str) and url.strip()\n        has_stdio = isinstance(command, str) and command.strip()\n\n        if not has_http and not has_stdio:\n",
    "        has_http = isinstance(url, str) and url.strip()\n"
    "        has_stdio = isinstance(command, str) and command.strip()\n"
    "        trusted_trace = s.get(\"trusted_trace_propagation\", False)\n"
    "        if (\n"
    "            \"trusted_trace_propagation\" in s\n"
    "            and not isinstance(trusted_trace, bool)\n"
    "        ):\n"
    "            errors.append(\n"
    "                f\"ERROR: mcp_servers[{idx}].trusted_trace_propagation must be boolean\"\n"
    "            )\n"
    "        elif trusted_trace is True and not (\n"
    "            has_http and str(url).lower().startswith((\"http://\", \"https://\"))\n"
    "        ):\n"
    "            warnings.append(\n"
    "                f\"WARNING: mcp_servers[{idx}].trusted_trace_propagation is ignored for non-HTTP transports.\"\n"
    "            )\n\n"
    "        if not has_http and not has_stdio:\n",
)
# Template parsing + persistence.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "    default_transport = (\n        str(args.get(\"transport\", \"streamable-http\")).strip() or \"streamable-http\"\n    )\n\n    if os.path.exists(config_path):\n",
    "    default_transport = (\n"
    "        str(args.get(\"transport\", \"streamable-http\")).strip() or \"streamable-http\"\n"
    "    )\n"
    "    trusted_trace_propagation = args.get(\"trusted_trace_propagation\", False)\n"
    "    if not isinstance(trusted_trace_propagation, bool):\n"
    "        return _json_out(\n"
    "            {\n"
    "                \"ok\": False,\n"
    "                \"action\": action,\n"
    "                \"error\": \"trusted_trace_propagation must be boolean\",\n"
    "            },\n"
    "            pretty=pretty,\n"
    "        )\n\n"
    "    if os.path.exists(config_path):\n",
)
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "                \"transport\": default_transport,\n            }\n",
    "                \"transport\": default_transport,\n"
    "                \"trusted_trace_propagation\": trusted_trace_propagation,\n"
    "            }\n",
)
# Entry builder carries the explicit boolean.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "    protocol_mode: str,\n    url: Any,\n",
    "    protocol_mode: str,\n"
    "    trusted_trace_propagation: bool,\n"
    "    url: Any,\n",
)
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    '        "protocol_mode": protocol_mode,\n    }\n',
    '        "protocol_mode": protocol_mode,\n'
    '        "trusted_trace_propagation": trusted_trace_propagation,\n'
    '    }\n',
)
# Add action validates exact boolean type.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "    protocol_mode = str(args.get(\"protocol_mode\") or \"auto\").strip().lower()\n    if protocol_mode not in {\"auto\", \"legacy\", \"stateless\"}:\n",
    "    protocol_mode = str(args.get(\"protocol_mode\") or \"auto\").strip().lower()\n"
    "    trusted_trace_propagation = args.get(\"trusted_trace_propagation\", False)\n"
    "    if not isinstance(trusted_trace_propagation, bool):\n"
    "        return _json_out(\n"
    "            {\n"
    "                \"ok\": False,\n"
    "                \"action\": action,\n"
    "                \"error\": \"trusted_trace_propagation must be boolean\",\n"
    "            },\n"
    "            pretty=pretty,\n"
    "        )\n"
    "    if protocol_mode not in {\"auto\", \"legacy\", \"stateless\"}:\n",
)
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "        protocol_mode=protocol_mode,\n        url=url,\n",
    "        protocol_mode=protocol_mode,\n"
    "        trusted_trace_propagation=trusted_trace_propagation,\n"
    "        url=url,\n",
)
