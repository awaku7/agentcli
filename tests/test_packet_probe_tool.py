from __future__ import annotations

import json


def test_tcp_connect_probe_returns_result(monkeypatch) -> None:
    from uagent.tools import packet_probe_tool

    monkeypatch.setattr(
        packet_probe_tool,
        "_probe_tcp",
        lambda target, port, timeout: {"state": "open", "latency_ms": 2.0},
    )

    result = json.loads(
        packet_probe_tool.run_tool(
            {
                "action": "tcp_connect",
                "target": "192.168.1.10",
                "port": 443,
                "timeout": 2,
            }
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "socket"
    assert result["state"] == "open"
    assert result["port"] == 443


def test_tcp_connect_rejects_invalid_port() -> None:
    from uagent.tools import packet_probe_tool

    result = json.loads(
        packet_probe_tool.run_tool(
            {"action": "tcp_connect", "target": "192.168.1.10", "port": 70000}
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_PORT"


def test_raw_probe_requires_explicit_elevation() -> None:
    from uagent.tools import packet_probe_tool

    result = json.loads(
        packet_probe_tool.run_tool(
            {"action": "tcp_syn", "target": "192.168.1.10", "port": 443}
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "PRIVILEGE_REQUIRED"
