from __future__ import annotations

import json
from pathlib import Path


def test_detect_finds_cleartext_protocol(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "telnet",
            "dst_port": 23,
            "length": 100,
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
                "rules": ["cleartext_protocol"],
            }
        )
    )

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "cleartext_protocol"
    assert result["findings"][0]["protocol"] == "telnet"


def test_detect_does_not_flag_tls(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tls",
            "dst_port": 443,
            "length": 100,
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
                "rules": ["cleartext_protocol"],
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"] == []
