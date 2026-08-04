from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_suspicious_dns_nxdomain_ratio(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.1",
            "protocol": "dns",
            "dns_rcode": "NXDOMAIN" if index < 4 else "NOERROR",
            "dns_query_length": 18,
            "length": 100,
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
                "rules": ["suspicious_dns"],
                "thresholds": {
                    "dns_min_queries": 5,
                    "dns_nxdomain_ratio": 0.6,
                },
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "suspicious_dns"
    assert result["findings"][0]["nxdomain_ratio"] == 0.8
    assert "qname" not in json.dumps(result)


def test_detect_does_not_flag_normal_dns(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.1",
            "protocol": "dns",
            "dns_rcode": "NOERROR",
            "dns_query_length": 18,
            "length": 100,
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
                "rules": ["suspicious_dns"],
                "thresholds": {"dns_min_queries": 5},
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
