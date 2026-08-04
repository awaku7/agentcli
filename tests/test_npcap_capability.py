from __future__ import annotations

import json


def test_capabilities_reports_npcap_status(monkeypatch) -> None:
    from uagent.tools import network_capabilities_tool

    monkeypatch.setattr(network_capabilities_tool, "_npcap_status", lambda: {"status": "available", "path": "C:/Npcap/wpcap.dll"})

    result = json.loads(network_capabilities_tool.run_tool({}))

    assert result["ok"] is True
    assert result["drivers"]["npcap"]["status"] == "available"
