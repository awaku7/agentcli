from __future__ import annotations

import json
from pathlib import Path


def test_impact_ranks_device_by_bytes_and_exposes_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.0.54",
            "dst_ip": "203.0.113.10",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 1000,
            "tcp_flags": "PA",
            "tcp_seq": 1,
            "tcp_payload_length": 900,
            "timestamp": 1.0,
        },
        {
            "src_ip": "192.168.0.54",
            "dst_ip": "203.0.113.10",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 1000,
            "tcp_flags": "PA",
            "tcp_seq": 1,
            "tcp_payload_length": 900,
            "timestamp": 1.1,
        },
        {
            "src_ip": "192.168.0.54",
            "dst_ip": "255.255.255.255",
            "src_port": 17500,
            "dst_port": 17500,
            "protocol": "udp",
            "length": 146,
            "timestamp": 2.0,
        },
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {"pcap_path": str(source), "operation": "impact", "limit": 5}
        )
    )

    assert result["ok"] is True
    assert result["operation"] == "impact"
    device = next(
        item for item in result["devices"] if item["device"] == "192.168.0.54"
    )
    assert device["bytes"] == 2146
    assert device["retransmissions"] == 1
    assert device["broadcast_packets"] == 1
    assert device["top_destinations"][0]["ip"] == "203.0.113.10"
