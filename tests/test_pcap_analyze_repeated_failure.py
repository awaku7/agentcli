from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_repeated_tcp_resets(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 443,
            "tcp_flags": "R",
            "length": 60,
            "timestamp": float(index),
        }
        for index in range(4)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["repeated_failure"],
                "thresholds": {"repeated_failure_events": 3},
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "repeated_failure"
    assert result["findings"][0]["event_count"] == 4


def test_detect_does_not_flag_normal_tcp_ack(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 443,
            "tcp_flags": "A",
            "length": 60,
            "timestamp": float(index),
        }
        for index in range(4)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["repeated_failure"],
                "thresholds": {"repeated_failure_events": 3},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
