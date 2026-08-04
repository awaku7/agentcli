from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_host_scan(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": f"192.168.1.{index}",
            "protocol": "tcp",
            "dst_port": 443,
            "length": 60,
            "timestamp": float(index),
        }
        for index in range(20, 25)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["host_scan"],
                "thresholds": {
                    "host_scan_distinct_hosts": 3,
                    "host_scan_window_seconds": 10,
                },
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "host_scan"
    assert result["findings"][0]["distinct_hosts"] == 5


def test_detect_does_not_flag_single_host(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 443,
            "length": 60,
            "timestamp": float(index),
        }
        for index in range(5)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["host_scan"],
                "thresholds": {"host_scan_distinct_hosts": 3},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
