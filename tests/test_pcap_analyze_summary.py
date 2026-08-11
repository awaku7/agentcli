from __future__ import annotations

import json
from pathlib import Path


def test_summary_returns_counts_without_packet_payload(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {"protocol": "tcp", "length": 100, "payload": b"secret"},
        {"protocol": "tcp", "length": 120},
        {"protocol": "udp", "length": 80},
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool({"pcap_path": str(source), "operation": "summary"})
    )

    assert result["ok"] is True
    assert result["operation"] == "summary"
    assert result["packet_count"] == 3
    assert result["protocols"] == {"tcp": 2, "udp": 1}
    assert result["total_bytes"] == 300
    assert "payload" not in json.dumps(result)
    assert "pcap_path" not in result


def test_summary_supports_filter_and_limit(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {"protocol": "tcp", "dst_port": 443, "length": 100},
        {"protocol": "tcp", "dst_port": 80, "length": 120},
        {"protocol": "tcp", "dst_port": 443, "length": 140},
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "summary",
                "filter": {"dst_port": 443},
                "limit": 1,
            }
        )
    )

    assert result["ok"] is True
    assert result["packet_count"] == 1
    assert result["total_bytes"] == 100
    assert result["truncated"] is True
