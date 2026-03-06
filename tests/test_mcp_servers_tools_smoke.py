from __future__ import annotations

import json
from pathlib import Path


def _write_config(path: Path, servers: list[dict]) -> None:
    path.write_text(
        json.dumps({"mcp_servers": servers}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_tool_catalog_smoke() -> None:
    from uagent.tools.catalog_tool import run_tool

    out = run_tool({"query": "read file", "max_results": 5})
    obj = json.loads(out)
    assert obj["ok"] is True
    assert isinstance(obj.get("tools"), list)
    assert any(item.get("name") == "read_file" for item in obj["tools"])


def test_mcp_servers_init_template_smoke(repo_tmp_path: Path) -> None:
    from uagent.tools.mcp_servers_init_template_tool import run_tool

    path = repo_tmp_path / "mcp_servers.json"
    out = run_tool(
        {
            "path": str(path),
            "default_name": "local",
            "default_url": "http://example.test/mcp",
            "default_transport": "streamable-http",
        }
    )

    assert path.exists()
    data = _load_config(path)
    assert data["mcp_servers"][0]["name"] == "local"
    assert data["mcp_servers"][0]["url"] == "http://example.test/mcp"
    assert "created template" in out.lower()


def test_mcp_servers_add_list_validate_set_default_remove_smoke(
    repo_tmp_path: Path,
) -> None:
    from uagent.tools.mcp_servers_add_tool import run_tool as add_tool
    from uagent.tools.mcp_servers_list_tool import run_tool as list_tool
    from uagent.tools.mcp_servers_remove_tool import run_tool as remove_tool
    from uagent.tools.mcp_servers_set_default_tool import run_tool as set_default_tool
    from uagent.tools.mcp_servers_validate_tool import run_tool as validate_tool

    path = repo_tmp_path / "mcp_servers.json"
    _write_config(
        path,
        [
            {
                "name": "first",
                "url": "http://first.test/mcp",
                "transport": "streamable-http",
            },
            {
                "name": "second",
                "url": "http://second.test/mcp",
                "transport": "streamable-http",
            },
        ],
    )

    out_add = add_tool(
        {
            "name": "third",
            "url": "http://third.test/mcp",
            "transport": "streamable-http",
            "path": str(path),
            "set_default": False,
            "replace": False,
            "create_if_missing": True,
        }
    )
    add_obj = json.loads(out_add)
    assert add_obj["ok"] is True
    assert add_obj["count"] == 3

    out_list = list_tool(
        {
            "path": str(path),
            "pretty": True,
            "validate": True,
            "default_only": False,
            "raw": True,
        }
    )
    list_obj = json.loads(out_list)
    assert list_obj["count"] == 3
    assert list_obj["default"]["name"] == "first"

    out_validate = validate_tool(
        {"path": str(path), "fail_on_warning": False, "pretty": True}
    )
    validate_obj = json.loads(out_validate)
    assert validate_obj["count"] == 3
    assert validate_obj["errors"] == []
    assert validate_obj["overall"] == "OK"
    assert isinstance(validate_obj["warnings"], list)

    out_set_default = set_default_tool(
        {"server_name": "third", "path": str(path), "create_if_missing": True}
    )
    assert "third" in out_set_default
    data_after_default = _load_config(path)
    assert data_after_default["mcp_servers"][0]["name"] == "third"

    out_remove = remove_tool(
        {"name": "second", "index": None, "path": str(path), "require_nonempty": False}
    )
    assert "removed" in out_remove.lower()
    data_after_remove = _load_config(path)
    names = [row["name"] for row in data_after_remove["mcp_servers"]]
    assert names == ["third", "first"]
