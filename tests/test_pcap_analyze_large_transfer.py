from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_large_transfer(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 443,
            "length": 600,
            "timestamp": float(index),
        }
        for index in range(3)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["large_transfer"],
                "thresholds": {"large_transfer_bytes": 1000},
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "large_transfer"
    assert result["findings"][0]["total_bytes"] == 1800


def test_detect_does_not_flag_small_transfer(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "udp",
            "dst_port": 53,
            "length": 100,
            "timestamp": float(index),
        }
        for index in range(3)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["large_transfer"],
                "thresholds": {"large_transfer_bytes": 1000},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
