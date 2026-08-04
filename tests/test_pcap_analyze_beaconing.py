from __future__ import annotations

import json
from pathlib import Path


def _run(tmp_path: Path, monkeypatch, timestamps: tuple[float, ...]) -> dict:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 443,
            "length": 100,
            "timestamp": timestamp,
        }
        for timestamp in timestamps
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")
    return json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["beaconing"],
                "thresholds": {
                    "beaconing_min_events": 5,
                    "beaconing_jitter_ratio": 0.2,
                    "beaconing_min_interval_seconds": 1,
                },
            }
        )
    )


def test_detect_finds_periodic_beaconing(tmp_path: Path, monkeypatch) -> None:
    result = _run(tmp_path, monkeypatch, (0.0, 10.0, 20.0, 30.0, 40.0))

    assert result["ok"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "beaconing"
    assert result["findings"][0]["event_count"] == 5


def test_detect_does_not_flag_irregular_intervals(tmp_path: Path, monkeypatch) -> None:
    result = _run(tmp_path, monkeypatch, (0.0, 1.0, 5.0, 20.0, 40.0))

    assert result["ok"] is True
    assert result["findings"] == []
