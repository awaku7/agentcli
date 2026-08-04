from __future__ import annotations

import json
from pathlib import Path


def test_packets_returns_limited_safe_fields(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 100,
            "timestamp": 1.25,
            "payload": b"secret",
        }
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "packets",
                "detail_level": 1,
                "limit": 10,
            }
        )
    )

    assert result["ok"] is True
    assert result["returned_packets"] == 1
    packet = result["packets"][0]
    assert packet["index"] == 0
    assert packet["dst_port"] == 443
    assert "payload" not in json.dumps(result)


def test_packets_detail_level_two_includes_tcp_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "tcp_flags": "A",
            "tcp_seq": 1000,
            "tcp_payload_length": 80,
            "length": 140,
            "timestamp": 1.25,
        }
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "packets",
                "detail_level": 2,
            }
        )
    )

    packet = result["packets"][0]
    assert packet["tcp_flags"] == "A"
    assert packet["tcp_seq"] == 1000


def test_packets_respects_filter_and_limit(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {"protocol": "tcp", "dst_port": 443, "length": 60, "timestamp": 1.0},
        {"protocol": "udp", "dst_port": 53, "length": 70, "timestamp": 2.0},
        {"protocol": "tcp", "dst_port": 443, "length": 80, "timestamp": 3.0},
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "packets",
                "filter": {"protocol": "tcp", "dst_port": 443},
                "limit": 1,
            }
        )
    )

    assert result["ok"] is True
    assert result["returned_packets"] == 1
    assert result["truncated"] is True
