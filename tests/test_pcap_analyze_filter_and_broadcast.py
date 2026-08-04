from __future__ import annotations

import json
from pathlib import Path


def test_flows_apply_ip_filter(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "src_port": 1000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 60,
            "timestamp": 1.0,
        },
        {
            "src_ip": "10.0.0.3",
            "dst_ip": "10.0.0.4",
            "src_port": 1001,
            "dst_port": 80,
            "protocol": "tcp",
            "length": 60,
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
                "operation": "flows",
                "filter": {"src_ip": "10.0.0.1"},
            }
        )
    )

    assert result["ok"] is True
    assert result["flow_count"] == 1
    assert result["flows"][0]["src_ip"] == "10.0.0.1"


def test_known_broadcast_ports_can_be_excluded(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "10.0.0.1",
            "dst_ip": "255.255.255.255",
            "src_port": 17500,
            "dst_port": 17500,
            "protocol": "udp",
            "length": 146,
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
                "rules": ["broadcast_anomaly"],
                "thresholds": {"broadcast_events": 3},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []


def test_unknown_broadcast_port_is_still_detected(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "10.0.0.1",
            "dst_ip": "255.255.255.255",
            "src_port": 40123,
            "dst_port": 40123,
            "protocol": "udp",
            "length": 146,
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
                "rules": ["broadcast_anomaly"],
                "thresholds": {"broadcast_events": 3},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"][0]["category"] == "broadcast_anomaly"
