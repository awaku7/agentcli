from __future__ import annotations

import json
from pathlib import Path


def test_threat_detect_parses_suricata_eve_alerts(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import threat_detect_tool

    eve = tmp_path / "eve.json"
    eve.write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "event_type": "alert",
                "src_ip": "192.168.1.10",
                "dest_ip": "192.168.1.20",
                "dest_port": 443,
                "alert": {"signature": "Test signature", "severity": 2, "category": "Test"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(threat_detect_tool, "_find_suricata", lambda: "suricata")
    monkeypatch.setattr(threat_detect_tool, "_run_suricata", lambda *_args: eve)

    result = json.loads(
        threat_detect_tool.run_tool({"pcap_path": str(tmp_path / "capture.pcap")})
    )

    assert result["ok"] is True
    assert result["backend"] == "suricata"
    assert result["alerts"][0]["signature"] == "Test signature"
    assert "payload" not in json.dumps(result)


def test_threat_detect_ignores_non_alert_events(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import threat_detect_tool

    eve = tmp_path / "eve.json"
    eve.write_text(json.dumps({"event_type": "stats"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(threat_detect_tool, "_find_suricata", lambda: "suricata")
    monkeypatch.setattr(threat_detect_tool, "_run_suricata", lambda *_args: eve)

    result = json.loads(threat_detect_tool.run_tool({"pcap_path": "capture.pcap"}))

    assert result["ok"] is True
    assert result["alerts"] == []
