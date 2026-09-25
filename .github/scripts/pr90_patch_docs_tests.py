from pathlib import Path
import json


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Keep the localized tool schema structurally complete. English fallback is
# preferable to silently omitting this security-sensitive setting.
path = Path("src/uagent/tools/mcp_servers_tool.json")
data = json.loads(path.read_text(encoding="utf-8"))
for locale, messages in data.items():
    if not isinstance(messages, dict):
        continue
    if locale == "ja":
        description = (
            "(add/init_template) この管理対象HTTP MCPサーバーをW3Cトレース伝播先として明示的に信頼します。既定: false。"
        )
    else:
        description = (
            "(add/init_template) Explicitly trust this managed HTTP MCP server for W3C trace propagation. Default: false."
        )
    messages["param.trusted_trace_propagation.description"] = description
path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)


# Observability contract and ordinary MCP development notes.
replace_once(
    "src/uagent/docs/DEVELOP_OBSERVABILITY.md",
    "- MCP stdio does not serialize W3C trace headers; it remains related to the current execution only through process-local context and the existing outer `execute_tool` span.\n",
    "- MCP stdio does not serialize W3C trace headers; it remains related to the current execution only through process-local context and the existing outer `execute_tool` span.\n"
    "- Managed MCP configuration may opt an HTTP server into this trust boundary only with the exact JSON boolean `\"trusted_trace_propagation\": true`. Missing, false, string, or numeric values remain OFF. Direct `url` tool arguments cannot enable the trust flag.\n"
    "- The process-local MCP HTTP session pool includes the trust flag in its cache key, so trusted and untrusted sessions for the same URL/headers/protocol mode are never reused across the propagation boundary.\n",
)
replace_once(
    "src/uagent/docs/DEVELOP_OBSERVABILITY.md",
    "Regression coverage for this slice is in `tests/test_observability_phase3_subagent.py`, `tests/test_observability_phase3_a2a.py`, and `tests/test_observability_phase3_mcp.py`.\n",
    "Regression coverage for this slice is in `tests/test_observability_phase3_subagent.py`, `tests/test_observability_phase3_a2a.py`, `tests/test_observability_phase3_mcp.py`, and `tests/test_observability_phase3_mcp_config.py`.\n",
)
replace_once(
    "src/uagent/docs/DEVELOP_OBSERVABILITY.md",
    "Wiring trusted MCP propagation into server-managed `mcp_servers.json` configuration and explicit trusted reverse-proxy ingress remain Phase-3 follow-up work. Provider SDK auto-instrumentation, controlled content capture, pseudonymous identity correlation, and user-visible trace query UI/proxy remain later work.\n",
    "Explicit trusted reverse-proxy ingress remains the Phase-3 follow-up work. Provider SDK auto-instrumentation, controlled content capture, pseudonymous identity correlation, and user-visible trace query UI/proxy remain later work.\n",
)
replace_once(
    "src/uagent/docs/DEVELOP.md",
    "Validate again after each config change.\n\nRecent smoke tests cover template creation and the basic add/list/validate/set_default/remove flow.\n",
    "Validate again after each config change.\n\n"
    "For a UAG-managed HTTP MCP server that is explicitly trusted for distributed tracing, set `\"trusted_trace_propagation\": true` in that server's `mcp_servers.json` entry. The default is false; only the JSON boolean `true` enables propagation, direct URL calls cannot enable it, and stdio ignores it.\n\n"
    "Recent smoke tests cover template creation and the basic add/list/validate/set_default/remove flow.\n",
)


# Focused regression coverage for the new managed trust boundary.
test = r'''from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


def _write_config(path: Path, servers: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps({"mcp_servers": servers}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_managed_trace_optin_requires_json_boolean_true(repo_tmp_path: Path) -> None:
    from uagent.tools.mcp_servers_shared import (
        is_trusted_mcp_trace_propagation_enabled,
    )
    from uagent.tools.mcp_servers_tool import run_tool

    path = repo_tmp_path / "mcp_servers.json"
    added = json.loads(
        run_tool(
            {
                "action": "add",
                "path": str(path),
                "name": "trusted",
                "url": "https://mcp.example/mcp",
                "trusted_trace_propagation": True,
            }
        )
    )
    assert added["ok"] is True
    stored = json.loads(path.read_text(encoding="utf-8"))["mcp_servers"][0]
    assert stored["trusted_trace_propagation"] is True
    assert is_trusted_mcp_trace_propagation_enabled(stored) is True
    assert (
        is_trusted_mcp_trace_propagation_enabled(
            {"trusted_trace_propagation": "true"}
        )
        is False
    )

    rejected = json.loads(
        run_tool(
            {
                "action": "add",
                "path": str(path),
                "name": "bad",
                "url": "https://bad.example/mcp",
                "trusted_trace_propagation": "true",
            }
        )
    )
    assert rejected["ok"] is False
    assert "must be boolean" in rejected["error"]


def test_handle_mcp_v2_managed_optin_and_direct_url_stays_off(
    repo_tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import handle_mcp_v2_tool as tool

    path = repo_tmp_path / "mcp_servers.json"
    _write_config(
        path,
        [
            {
                "name": "trusted",
                "url": "https://mcp.example/mcp",
                "trusted_trace_propagation": True,
            }
        ],
    )
    monkeypatch.setattr(tool, "get_default_mcp_config_path", lambda: str(path))
    monkeypatch.setattr(tool, "_mcp_session_reuse_enabled", lambda: False)
    seen: list[bool] = []

    async def fake_http(
        url: str,
        name: str,
        argv: dict[str, Any],
        headers: dict[str, str] | None = None,
        protocol_mode: str = "auto",
        trusted_trace_propagation: bool = False,
    ) -> str:
        seen.append(trusted_trace_propagation)
        return "ok"

    monkeypatch.setattr(tool, "_call_mcp_http", fake_http)
    tool.run_tool({"server_name": "trusted", "tool_name": "ping", "args": {}})
    tool.run_tool(
        {"url": "https://mcp.example/mcp", "tool_name": "ping", "args": {}}
    )
    assert seen == [True, False]


def test_mcp_tools_list_managed_optin(repo_tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import mcp_tools_list_tool as tool

    path = repo_tmp_path / "mcp_servers.json"
    _write_config(
        path,
        [
            {
                "name": "trusted",
                "url": "https://mcp.example/mcp",
                "trusted_trace_propagation": True,
            }
        ],
    )
    monkeypatch.setattr(tool, "get_default_mcp_config_path", lambda: str(path))
    seen: list[bool] = []

    async def fake_list(
        url: str,
        headers: dict[str, str] | None = None,
        protocol_mode: str = "auto",
        trusted_trace_propagation: bool = False,
    ) -> dict[str, Any]:
        seen.append(trusted_trace_propagation)
        return {"url": url, "tools_list": {"tools": []}}

    monkeypatch.setattr(tool, "_mcp_tools_list_http", fake_list)
    result = json.loads(tool.run_tool({"server_name": "trusted"}))
    assert result["tools_list"] == {"tools": []}
    assert seen == [True]


def test_resources_resolver_only_marks_managed_http_as_trusted(
    repo_tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import mcp_resources_tool as tool

    path = repo_tmp_path / "mcp_servers.json"
    _write_config(
        path,
        [
            {
                "name": "trusted-http",
                "url": "https://mcp.example/mcp",
                "trusted_trace_propagation": True,
            },
            {
                "name": "string-http",
                "url": "https://string.example/mcp",
                "trusted_trace_propagation": "true",
            },
            {
                "name": "trusted-stdio",
                "command": "python",
                "args": ["server.py"],
                "trusted_trace_propagation": True,
            },
        ],
    )
    monkeypatch.setattr(tool, "get_default_mcp_config_path", lambda: str(path))

    trusted, _ = tool._resolve({"server_name": "trusted-http"})
    string_value, _ = tool._resolve({"server_name": "string-http"})
    stdio, _ = tool._resolve({"server_name": "trusted-stdio"})
    direct, _ = tool._resolve({"url": "https://direct.example/mcp"})

    assert trusted["trusted_trace_propagation"] is True
    assert string_value["trusted_trace_propagation"] is False
    assert "trusted_trace_propagation" not in stdio
    assert "trusted_trace_propagation" not in direct


def test_session_pool_separates_trust_boundary_and_passes_flag() -> None:
    from uagent.tools.mcp.session_pool import MCPHTTPSessionPool

    created: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def list_tools(self):
            return {"tools": []}

    pool = MCPHTTPSessionPool()
    pool.set_client_factory(FakeClient)
    assert pool._key("https://mcp.example/mcp", {}, "legacy", 1, False) != pool._key(
        "https://mcp.example/mcp", {}, "legacy", 1, True
    )

    async def scenario() -> None:
        entry = await pool._get_entry(
            "trusted",
            url="https://mcp.example/mcp",
            headers={},
            protocol_mode="legacy",
            trusted_trace_propagation=True,
        )
        assert entry is not None
        await pool._close_all()

    asyncio.run(scenario())
    assert created[-1]["trusted_trace_propagation"] is True
'''
Path("tests/test_observability_phase3_mcp_config.py").write_text(
    test, encoding="utf-8"
)
