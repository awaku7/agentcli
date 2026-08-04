from __future__ import annotations

from pathlib import Path

from tests.test_pcap_analyze_remaining_rules import run_rule, base_packet


def test_syn_flood_ignores_completed_reverse_handshakes(tmp_path: Path, monkeypatch) -> None:
    packets = []
    for index in range(5):
        client_port = 50000 + index
        packets.append(
            base_packet(
                src_port=client_port,
                dst_port=443,
                tcp_flags="S",
                timestamp=float(index),
            )
        )
        packets.append(
            base_packet(
                src_ip="192.168.1.20",
                dst_ip="192.168.1.10",
                src_port=443,
                dst_port=client_port,
                tcp_flags="SA",
                timestamp=float(index) + 0.1,
            )
        )

    result = run_rule(
        tmp_path,
        monkeypatch,
        "syn_flood_candidate",
        packets,
        {"syn_events": 3},
    )

    assert result["ok"] is True
    assert result["findings"] == []


def test_syn_flood_reports_unanswered_syns(tmp_path: Path, monkeypatch) -> None:
    packets = [
        base_packet(src_port=50000 + index, dst_port=443, tcp_flags="S", timestamp=float(index))
        for index in range(5)
    ]

    result = run_rule(
        tmp_path,
        monkeypatch,
        "syn_flood_candidate",
        packets,
        {"syn_events": 3},
    )

    assert result["ok"] is True
    assert result["findings"][0]["syn_count"] == 5
    assert result["findings"][0]["syn_ack_count"] == 0
