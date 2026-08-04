from __future__ import annotations

import json
from pathlib import Path


def test_statistics_returns_global_metadata(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {"protocol": "tcp", "length": 100, "timestamp": 1.0},
        {"protocol": "tcp", "length": 200, "timestamp": 3.5},
        {"protocol": "udp", "length": 50, "timestamp": 4.0},
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {"pcap_path": str(source), "operation": "statistics"}
        )
    )

    assert result["ok"] is True
    assert result["packet_count"] == 3
    assert result["total_bytes"] == 350
    assert result["duration_seconds"] == 3.0
    assert result["protocols"] == {"tcp": 2, "udp": 1}
    assert "payload" not in json.dumps(result)


def test_statistics_handles_empty_capture(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter([]))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {"pcap_path": str(source), "operation": "statistics"}
        )
    )

    assert result["ok"] is True
    assert result["packet_count"] == 0
    assert result["duration_seconds"] == 0
