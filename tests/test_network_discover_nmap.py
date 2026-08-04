from __future__ import annotations

import json


def test_service_scan_parses_nmap_xml(monkeypatch) -> None:
    from uagent.tools import network_discover_tool

    xml = """
    <nmaprun>
      <host>
        <status state="up" />
        <address addr="192.168.1.10" addrtype="ipv4" />
        <ports>
          <port protocol="tcp" portid="443">
            <state state="open" />
            <service name="https" product="Example" version="1.0" />
          </port>
        </ports>
      </host>
    </nmaprun>
    """
    monkeypatch.setattr(network_discover_tool, "_run_nmap", lambda *_args: xml)

    result = json.loads(
        network_discover_tool.run_tool(
            {
                "mode": "service_scan",
                "target": "192.168.1.10",
                "ports": [443],
            }
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "nmap"
    assert result["hosts"][0]["status"] == "up"
    assert result["hosts"][0]["ports"][0]["service"] == "https"
    assert result["hosts"][0]["ports"][0]["version"] == "Example 1.0"


def test_service_scan_reports_missing_nmap(monkeypatch) -> None:
    from uagent.tools import network_discover_tool

    monkeypatch.setattr(network_discover_tool, "which", lambda _name: None)
    monkeypatch.setattr(network_discover_tool.os.path, "isfile", lambda _path: False)

    result = json.loads(
        network_discover_tool.run_tool(
            {"mode": "service_scan", "target": "192.168.1.10", "ports": [443]}
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "EXTERNAL_DEPENDENCY_MISSING"
