from __future__ import annotations

import json


def test_port_scan_returns_open_and_closed_ports(monkeypatch) -> None:
    from uagent.tools import network_discover_tool

    def fake_probe(target: str, port: int, timeout: float) -> dict:
        return {
            "port": port,
            "state": "open" if port == 443 else "closed",
            "latency_ms": 1.5,
        }

    monkeypatch.setattr(network_discover_tool, "_probe_tcp", fake_probe)

    result = json.loads(
        network_discover_tool.run_tool(
            {
                "mode": "port_scan",
                "target": "192.168.1.10",
                "ports": [80, 443],
                "timeout": 1,
            }
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "socket"
    assert result["target"] == "192.168.1.10"
    assert result["open_ports"] == [443]
    assert result["results"][0]["state"] in {"open", "closed"}


def test_port_scan_rejects_empty_target() -> None:
    from uagent.tools import network_discover_tool

    result = json.loads(
        network_discover_tool.run_tool(
            {"mode": "port_scan", "target": "", "ports": [443]}
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "TARGET_REQUIRED"


def test_port_scan_rejects_excessive_ports() -> None:
    from uagent.tools import network_discover_tool

    result = json.loads(
        network_discover_tool.run_tool(
            {"mode": "port_scan", "target": "192.168.1.10", "ports": list(range(1, 1000))}
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "PORT_LIMIT_EXCEEDED"
