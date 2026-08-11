from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_unusual_destination_port(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 31337,
            "tcp_flags": "S",
            "length": 60,
            "timestamp": 1.0,
        }
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["unusual_port"],
                "thresholds": {"allowed_destination_ports": [80, 443]},
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "unusual_port"
    assert result["findings"][0]["dst_port"] == 31337


def test_unusual_port_uses_builtin_well_known_ports(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import pcap_analyze_tool

    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter([]))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["unusual_port"],
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
