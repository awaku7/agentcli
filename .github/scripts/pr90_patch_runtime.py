from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Shared exact-boolean trust helper.
path = Path("src/uagent/tools/mcp_servers_shared.py")
text = path.read_text(encoding="utf-8")
text = text.replace("import json\n", "import json\nfrom typing import Any\n", 1)
marker = "\n\ndef ensure_mcp_config_template() -> str:\n"
helper = '''\n\ndef is_trusted_mcp_trace_propagation_enabled(server: Any) -> bool:\n    \"\"\"Return whether a managed MCP server explicitly opts into trace propagation.\n\n    Only the JSON boolean ``true`` is accepted. String/integer truthy values do not\n    cross this trust boundary.\n    \"\"\"\n\n    return (\n        isinstance(server, dict)\n        and server.get(\"trusted_trace_propagation\") is True\n    )\n'''
if "def is_trusted_mcp_trace_propagation_enabled" not in text:
    if marker not in text:
        raise SystemExit("shared helper insertion marker missing")
    text = text.replace(marker, helper + marker, 1)
path.write_text(text, encoding="utf-8")


# handle_mcp_v2: managed config -> both pooled and per-call HTTP clients.
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "    from .mcp_servers_shared import get_default_mcp_config_path\n",
    "    from .mcp_servers_shared import (\n"
    "        get_default_mcp_config_path,\n"
    "        is_trusted_mcp_trace_propagation_enabled,\n"
    "    )\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "    def get_default_mcp_config_path():\n",
    "    def is_trusted_mcp_trace_propagation_enabled(server: Any) -> bool:\n"
    "        return (\n"
    "            isinstance(server, dict)\n"
    "            and server.get(\"trusted_trace_propagation\") is True\n"
    "        )\n\n"
    "    def get_default_mcp_config_path():\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "    headers: dict[str, str],\n    protocol_mode: str,\n) -> str:\n",
    "    headers: dict[str, str],\n"
    "    protocol_mode: str,\n"
    "    trusted_trace_propagation: bool = False,\n"
    ") -> str:\n",
)
path = Path("src/uagent/tools/handle_mcp_v2_tool.py")
text = path.read_text(encoding="utf-8")
needle = "        protocol_mode=protocol_mode,\n        is_cancelled=is_cancelled if callable(is_cancelled) else None,\n"
if text.count(needle) != 2:
    raise SystemExit(f"expected two pooled protocol call sites, got {text.count(needle)}")
text = text.replace(
    needle,
    "        protocol_mode=protocol_mode,\n"
    "        trusted_trace_propagation=trusted_trace_propagation,\n"
    "        is_cancelled=is_cancelled if callable(is_cancelled) else None,\n",
)
path.write_text(text, encoding="utf-8")
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "    protocol_mode: str = \"auto\",\n) -> str:\n    if _mcp_session_reuse_enabled():\n",
    "    protocol_mode: str = \"auto\",\n"
    "    trusted_trace_propagation: bool = False,\n"
    ") -> str:\n"
    "    if _mcp_session_reuse_enabled():\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "            return _call_mcp_http_reused(url, name, argv, headers or {}, protocol_mode)\n",
    "            return _call_mcp_http_reused(\n"
    "                url,\n"
    "                name,\n"
    "                argv,\n"
    "                headers or {},\n"
    "                protocol_mode,\n"
    "                trusted_trace_propagation,\n"
    "            )\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "            protocol_mode=protocol_mode,\n        ) as client:\n",
    "            protocol_mode=protocol_mode,\n"
    "            trusted_trace_propagation=trusted_trace_propagation,\n"
    "        ) as client:\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "    http_headers: dict[str, str] = {}\n\n    config_path = get_default_mcp_config_path()\n",
    "    http_headers: dict[str, str] = {}\n"
    "    trusted_trace_propagation = False\n\n"
    "    config_path = get_default_mcp_config_path()\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "                            http_headers = _resolve_http_headers(s.get(\"headers\"))\n",
    "                            http_headers = _resolve_http_headers(s.get(\"headers\"))\n"
    "                            trusted_trace_propagation = (\n"
    "                                is_trusted_mcp_trace_propagation_enabled(s)\n"
    "                            )\n",
)
replace_once(
    "src/uagent/tools/handle_mcp_v2_tool.py",
    "                _call_mcp_http(url, name, argv, http_headers, protocol_mode)\n",
    "                _call_mcp_http(\n"
    "                    url,\n"
    "                    name,\n"
    "                    argv,\n"
    "                    http_headers,\n"
    "                    protocol_mode,\n"
    "                    trusted_trace_propagation,\n"
    "                )\n",
)


# Session pool: trust is part of the cache key and constructor contract.
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    "        factory_id: int,\n    ) -> str:\n",
    "        factory_id: int,\n"
    "        trusted_trace_propagation: bool = False,\n"
    "    ) -> str:\n",
)
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    '                "factory_id": factory_id,\n',
    '                "factory_id": factory_id,\n'
    '                "trusted_trace_propagation": bool(trusted_trace_propagation),\n',
)
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    "        protocol_mode: str,\n    ) -> _Entry:\n",
    "        protocol_mode: str,\n"
    "        trusted_trace_propagation: bool = False,\n"
    "    ) -> _Entry:\n",
)
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    "            protocol_mode=protocol_mode,\n        )\n        await client.__aenter__()\n",
    "            protocol_mode=protocol_mode,\n"
    "            trusted_trace_propagation=trusted_trace_propagation,\n"
    "        )\n"
    "        await client.__aenter__()\n",
)
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    "        protocol_mode: str,\n    ) -> tuple[Any, Any]:\n",
    "        protocol_mode: str,\n"
    "        trusted_trace_propagation: bool = False,\n"
    "    ) -> tuple[Any, Any]:\n",
)
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    "            protocol_mode=protocol_mode,\n        )\n        async with entry.lock:\n",
    "            protocol_mode=protocol_mode,\n"
    "            trusted_trace_propagation=trusted_trace_propagation,\n"
    "        )\n"
    "        async with entry.lock:\n",
)
path = Path("src/uagent/tools/mcp/session_pool.py")
text = path.read_text(encoding="utf-8")
# Both public methods gain the flag before cancellation callbacks.
needle = "        protocol_mode: str,\n        is_cancelled: Callable[[], bool] | None = None,\n"
if text.count(needle) != 2:
    raise SystemExit(f"expected two public pool signatures, got {text.count(needle)}")
text = text.replace(
    needle,
    "        protocol_mode: str,\n"
    "        trusted_trace_propagation: bool = False,\n"
    "        is_cancelled: Callable[[], bool] | None = None,\n",
)
# Both key creations are trust-separated.
needle = "        key = self._key(url, headers, protocol_mode, id(self._client_factory))\n"
if text.count(needle) != 2:
    raise SystemExit(f"expected two pool key call sites, got {text.count(needle)}")
text = text.replace(
    needle,
    "        key = self._key(\n"
    "            url,\n"
    "            headers,\n"
    "            protocol_mode,\n"
    "            id(self._client_factory),\n"
    "            trusted_trace_propagation,\n"
    "        )\n",
)
# _get_entry is called once from list_tools and once from _call_tool; add trust in both.
needle = "                protocol_mode=protocol_mode,\n            )\n"
if text.count(needle) < 2:
    raise SystemExit("pool entry call sites missing")
text = text.replace(
    needle,
    "                protocol_mode=protocol_mode,\n"
    "                trusted_trace_propagation=trusted_trace_propagation,\n"
    "            )\n",
    2,
)
# _call_tool submission also needs trust.
replace_once(
    "src/uagent/tools/mcp/session_pool.py",
    "                headers=headers,\n                protocol_mode=protocol_mode,\n            )\n        )\n        return self._wait_for_future(\n            future,\n            key=key,\n",
    "                headers=headers,\n"
    "                protocol_mode=protocol_mode,\n"
    "                trusted_trace_propagation=trusted_trace_propagation,\n"
    "            )\n"
    "        )\n"
    "        return self._wait_for_future(\n"
    "            future,\n"
    "            key=key,\n",
)
