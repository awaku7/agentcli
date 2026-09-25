from pathlib import Path

# Narrow ambiguous handle_mcp_v2 and session-pool staging operations.
path = Path(".github/scripts/pr90_patch_runtime.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "            protocol_mode=protocol_mode,\\n        ) as client:\\n",
    "            protocol_mode=protocol_mode,\\n"
    "            trusted_trace_propagation=trusted_trace_propagation,\\n"
    "        ) as client:\\n",
)
'''
new = '''replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "        async with MCPClient(\\n"
    "            url=url,\\n"
    "            headers=headers or {},\\n"
    "            protocol_mode=protocol_mode,\\n"
    "        ) as client:\\n",
    "        async with MCPClient(\\n"
    "            url=url,\\n"
    "            headers=headers or {},\\n"
    "            protocol_mode=protocol_mode,\\n"
    "            trusted_trace_propagation=trusted_trace_propagation,\\n"
    "        ) as client:\\n",
)
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one HTTP staging block, got {text.count(old)}")
text = text.replace(old, new)
marker = "\n# _call_tool submission also needs trust.\n"
if text.count(marker) != 1:
    raise SystemExit(f"expected redundant pool block marker once, got {text.count(marker)}")
text = text.split(marker, 1)[0].rstrip() + "\n"
path.write_text(text, encoding="utf-8")

# Narrow ambiguous staging operations in the MCP management tools.
path = Path(".github/scripts/pr90_patch_tools.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "    protocol_mode: str = \\"auto\\",\\n) -> dict[str, Any]:\\n",
    "    protocol_mode: str = \\"auto\\",\\n"
    "    trusted_trace_propagation: bool = False,\\n"
    ") -> dict[str, Any]:\\n",
)
'''
new = '''replace_once(
    "src/uagent/tools/mcp_tools_list_tool.py",
    "async def _mcp_tools_list_http(\\n"
    "    url: str,\\n"
    "    headers: dict[str, str] | None = None,\\n"
    "    protocol_mode: str = \\"auto\\",\\n"
    ") -> dict[str, Any]:\\n",
    "async def _mcp_tools_list_http(\\n"
    "    url: str,\\n"
    "    headers: dict[str, str] | None = None,\\n"
    "    protocol_mode: str = \\"auto\\",\\n"
    "    trusted_trace_propagation: bool = False,\\n"
    ") -> dict[str, Any]:\\n",
)
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one tools-list staging block, got {text.count(old)}")
text = text.replace(old, new)

start_marker = "# List validation: malformed values and stdio/no-HTTP true are visible.\n"
end_marker = "# Strict validation occurs after has_http/has_stdio are known.\n"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("server-list staging markers missing")
list_block = '''# List validation: malformed values and stdio/no-HTTP true are visible.
replace_once(
    "src/uagent/tools/mcp_servers_tool.py",
    "        command = s.get(\\\"command\\\")\\n\\n"
    "        if not isinstance(name, str) or not name.strip():\\n"
    "            warnings.append(\\n",
    "        command = s.get(\\\"command\\\")\\n"
    "        trusted_trace = s.get(\\\"trusted_trace_propagation\\\", False)\\n"
    "        if (\\n"
    "            \\\"trusted_trace_propagation\\\" in s\\n"
    "            and not isinstance(trusted_trace, bool)\\n"
    "        ):\\n"
    "            warnings.append(\\n"
    "                f\\\"WARNING: mcp_servers[{idx}].trusted_trace_propagation must be boolean.\\\"\\n"
    "            )\\n"
    "        elif trusted_trace is True and not (\\n"
    "            isinstance(url, str) and url.lower().startswith((\\\"http://\\\", \\\"https://\\\"))\\n"
    "        ):\\n"
    "            warnings.append(\\n"
    "                f\\\"WARNING: mcp_servers[{idx}].trusted_trace_propagation is ignored for non-HTTP transports.\\\"\\n"
    "            )\\n\\n"
    "        if not isinstance(name, str) or not name.strip():\\n"
    "            warnings.append(\\n",
)

'''
text = text[:start] + list_block + text[end:]
path.write_text(text, encoding="utf-8")
