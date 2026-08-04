from __future__ import annotations

import json
from pathlib import Path


def _run(tmp_path: Path, monkeypatch, packets: list[dict]) -> dict:
    from uagent.tools import pcap_analyze_tool

    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")
    return json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["unusual_port"],
                "thresholds": {"allowed_destination_ports": [443]},
            }
        )
    )


def test_tcp_reverse_ephemeral_port_is_not_reported(tmp_path: Path, monkeypatch) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        [
            {
                "src_ip": "10.0.0.10",
                "dst_ip": "10.0.0.20",
                "protocol": "tcp",
                "src_port": 50000,
                "dst_port": 443,
                "tcp_flags": "S",
                "timestamp": 1.0,
            },
            {
                "src_ip": "10.0.0.20",
                "dst_ip": "10.0.0.10",
                "protocol": "tcp",
                "src_port": 443,
                "dst_port": 50000,
                "tcp_flags": "SA",
                "timestamp": 1.1,
            },
        ],
    )

    assert result["ok"] is True
    assert result["findings"] == []


def test_tcp_service_port_is_reported_from_initial_syn(tmp_path: Path, monkeypatch) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        [
            {
                "src_ip": "10.0.0.10",
                "dst_ip": "10.0.0.20",
                "protocol": "tcp",
                "src_port": 50000,
                "dst_port": 31337,
                "tcp_flags": "S",
                "timestamp": 1.0,
            },
            {
                "src_ip": "10.0.0.20",
                "dst_ip": "10.0.0.10",
                "protocol": "tcp",
                "src_port": 31337,
                "dst_port": 50000,
                "tcp_flags": "SA",
                "timestamp": 1.1,
            },
        ],
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["dst_port"] == 31337
    assert finding["direction"] == "server_bound"
    assert finding["evidence"]["direction_basis"] == "tcp_initial_syn"


def test_udp_direction_remains_datagram_destination(tmp_path: Path, monkeypatch) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        [
            {
                "src_ip": "10.0.0.10",
                "dst_ip": "10.0.0.20",
                "protocol": "udp",
                "src_port": 50000,
                "dst_port": 5353,
                "timestamp": 1.0,
            }
        ],
    )

    assert result["ok"] is True
    assert result["findings"][0]["direction"] == "datagram_destination"
    assert result["findings"][0]["evidence"]["direction_basis"] == "packet_destination"


def test_partial_tcp_capture_is_not_classified_directionally(tmp_path: Path, monkeypatch) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        [
            {
                "src_ip": "10.0.0.10",
                "dst_ip": "10.0.0.20",
                "protocol": "tcp",
                "dst_port": 31337,
                "timestamp": 1.0,
            }
        ],
    )

    assert result["ok"] is True
    assert result["findings"] == []
