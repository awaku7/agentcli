from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_port_scan_from_metadata(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": port,
            "length": 60,
            "timestamp": float(port),
        }
        for port in range(1, 6)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["port_scan"],
                "thresholds": {
                    "port_scan_distinct_ports": 3,
                    "port_scan_window_seconds": 10,
                },
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["category"] == "port_scan"
    assert finding["severity"] == "medium"
    assert finding["distinct_ports"] == 5
    assert "payload" not in json.dumps(result)


def test_detect_does_not_flag_below_threshold(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": port,
            "length": 60,
            "timestamp": float(port),
        }
        for port in (80, 443)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["port_scan"],
                "thresholds": {"port_scan_distinct_ports": 3},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []


def test_detect_requires_known_rule(tmp_path: Path) -> None:
    from uagent.tools import pcap_analyze_tool

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["unknown_rule"],
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNKNOWN_DETECTION_RULE"
