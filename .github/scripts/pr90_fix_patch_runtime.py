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

# Narrow mcp_tools_list to its HTTP function; stdio has the same trailing signature.
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
path.write_text(text.replace(old, new), encoding="utf-8")
