from __future__ import annotations

import json


def test_capabilities_returns_external_command_status(monkeypatch) -> None:
    from uagent.tools import network_capabilities_tool

    monkeypatch.setattr(
        network_capabilities_tool,
        "which",
        lambda name: "C:/bin/" + name if name in {"nmap", "tshark"} else None,
    )
    monkeypatch.setattr(network_capabilities_tool, "_python_is_admin", lambda: False)

    result = json.loads(network_capabilities_tool.run_tool({}))

    assert result["ok"] is True
    assert result["platform"]
    assert result["executables"]["nmap"]["status"] == "available"
    assert result["executables"]["zeek"]["status"] == "missing"
    assert result["privilege"]["elevated"] is False


def test_capabilities_never_returns_command_output() -> None:
    from uagent.tools import network_capabilities_tool

    result = json.loads(network_capabilities_tool.run_tool({}))

    assert result["ok"] is True
    assert "stdout" not in json.dumps(result)
    assert "stderr" not in json.dumps(result)
