from __future__ import annotations

import json


def test_interfaces_returns_minimal_metadata(monkeypatch) -> None:
    from uagent.tools import local_network_tool

    class Address:
        def __init__(self, family: str, address: str, netmask: str | None = None):
            self.family = family
            self.address = address
            self.netmask = netmask

    class FakePsutil:
        @staticmethod
        def net_if_addrs():
            return {
                "Ethernet": [Address("AF_INET", "192.168.1.10", "255.255.255.0")],
                "Loopback": [Address("AF_INET", "127.0.0.1", "255.0.0.0")],
            }

        @staticmethod
        def net_if_stats():
            return {"Ethernet": type("Stat", (), {"isup": True})()}

    monkeypatch.setattr(local_network_tool, "_get_psutil", lambda: FakePsutil)

    result = json.loads(local_network_tool.run_tool({"operation": "interfaces"}))

    assert result["ok"] is True
    assert result["interfaces"][0]["name"] == "Ethernet"
    assert result["interfaces"][0]["addresses"][0]["address"] == "192.168.1.10"
    assert "psutil_module" not in json.dumps(result)


def test_unsupported_operation_returns_error() -> None:
    from uagent.tools import local_network_tool

    result = json.loads(local_network_tool.run_tool({"operation": "routes"}))

    assert result["ok"] is False
    assert result["error"]["code"] == "UNSUPPORTED_OPERATION"
