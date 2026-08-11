from __future__ import annotations

import json
from pathlib import Path


def run_rule(
    tmp_path: Path, monkeypatch, rule: str, packets: list[dict], thresholds: dict
) -> dict:
    from uagent.tools import pcap_analyze_tool

    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / f"{rule}.pcap"
    source.write_bytes(b"pcap")
    return json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": [rule],
                "thresholds": thresholds,
            }
        )
    )


def base_packet(**kwargs) -> dict:
    value = {
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.20",
        "src_port": 50000,
        "dst_port": 443,
        "protocol": "tcp",
        "length": 60,
        "timestamp": 1.0,
        "tcp_flags": "A",
    }
    value.update(kwargs)
    return value


def test_long_lived_connection(tmp_path: Path, monkeypatch) -> None:
    result = run_rule(
        tmp_path,
        monkeypatch,
        "long_lived_connection",
        [base_packet(timestamp=0.0), base_packet(timestamp=20.0)],
        {"long_lived_seconds": 10},
    )
    assert result["ok"] is True
    assert result["findings"][0]["category"] == "long_lived_connection"


def test_broadcast_anomaly(tmp_path: Path, monkeypatch) -> None:
    packets = [
        base_packet(dst_ip="192.168.1.255", timestamp=float(i)) for i in range(4)
    ]
    result = run_rule(
        tmp_path, monkeypatch, "broadcast_anomaly", packets, {"broadcast_events": 3}
    )
    assert result["ok"] is True
    assert result["findings"][0]["category"] == "broadcast_anomaly"


def test_syn_flood_candidate(tmp_path: Path, monkeypatch) -> None:
    packets = [
        base_packet(src_port=50000 + i, tcp_flags="S", timestamp=float(i))
        for i in range(5)
    ]
    result = run_rule(
        tmp_path, monkeypatch, "syn_flood_candidate", packets, {"syn_events": 3}
    )
    assert result["ok"] is True
    assert result["findings"][0]["category"] == "syn_flood_candidate"


def test_rtt_anomaly(tmp_path: Path, monkeypatch) -> None:
    packets = [base_packet(rtt_ms=250.0, timestamp=float(i)) for i in range(3)]
    result = run_rule(tmp_path, monkeypatch, "rtt_anomaly", packets, {"rtt_ms": 100})
    assert result["ok"] is True
    assert result["findings"][0]["category"] == "rtt_anomaly"


def test_protocol_anomaly(tmp_path: Path, monkeypatch) -> None:
    packets = [base_packet(tcp_flags="FS", timestamp=1.0)]
    result = run_rule(tmp_path, monkeypatch, "protocol_anomaly", packets, {})
    assert result["ok"] is True
    assert result["findings"][0]["category"] == "protocol_anomaly"


def test_suspicious_dns_long_query(tmp_path: Path, monkeypatch) -> None:
    packets = [
        base_packet(
            protocol="dns",
            dst_port=53,
            dns_query_length=300,
            dns_rcode="NOERROR",
            timestamp=1.0,
        )
    ]
    result = run_rule(
        tmp_path,
        monkeypatch,
        "suspicious_dns",
        packets,
        {"dns_long_query_length": 200, "dns_min_queries": 10},
    )
    assert result["ok"] is True
    assert result["findings"][0]["category"] == "suspicious_dns_long_query"
