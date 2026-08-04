from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_tcp_retransmission(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "tcp_seq": 1000,
            "tcp_payload_length": 1200,
            "tcp_flags": "A",
            "length": 1260,
            "timestamp": 1.0,
        },
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "tcp_seq": 1000,
            "tcp_payload_length": 1200,
            "tcp_flags": "A",
            "length": 1260,
            "timestamp": 2.0,
        },
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["tcp_retransmission"],
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "tcp_retransmission"
    assert result["findings"][0]["retransmission_count"] == 1


def test_detect_ignores_different_tcp_sequences(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "tcp_seq": sequence,
            "tcp_payload_length": 1200,
            "tcp_flags": "A",
            "length": 1260,
            "timestamp": float(index),
        }
        for index, sequence in enumerate((1000, 2200))
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["tcp_retransmission"],
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
