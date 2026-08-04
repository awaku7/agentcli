from __future__ import annotations

import json
from pathlib import Path


def test_flows_aggregate_five_tuple_metadata(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 100,
            "timestamp": 1.0,
        },
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 200,
            "timestamp": 3.5,
        },
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {"pcap_path": str(source), "operation": "flows"}
        )
    )

    assert result["ok"] is True
    assert result["flow_count"] == 1
    flow = result["flows"][0]
    assert flow["src_ip"] == "192.168.1.10"
    assert flow["dst_port"] == 443
    assert flow["packets"] == 2
    assert flow["bytes"] == 300
    assert flow["duration_seconds"] == 2.5
    assert "payload" not in json.dumps(result)


def test_flows_respects_limit(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": f"192.168.1.{index}",
            "src_port": 50000,
            "dst_port": 443,
            "protocol": "tcp",
            "length": 100,
            "timestamp": float(index),
        }
        for index in range(1, 4)
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "flows",
                "limit": 2,
            }
        )
    )

    assert result["ok"] is True
    assert len(result["flows"]) == 2
    assert result["truncated"] is True
