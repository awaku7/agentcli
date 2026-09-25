from pathlib import Path

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
