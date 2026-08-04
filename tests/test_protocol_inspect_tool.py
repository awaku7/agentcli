from __future__ import annotations

import json
from pathlib import Path


def test_protocol_inspect_returns_selected_fields_only(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import protocol_inspect_tool

    packets = [
        {"src_ip": "192.168.1.10", "dst_ip": "192.168.1.20", "protocol": "tcp", "dst_port": 443, "length": 120, "timestamp": 1.0, "payload": b"secret"}
    ]
    monkeypatch.setattr(protocol_inspect_tool, "_iter_packets", lambda _path: iter(packets))
    monkeypatch.setattr(protocol_inspect_tool, "_packet_info", lambda packet: packet)

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        protocol_inspect_tool.run_tool(
            {
                "pcap_path": str(source),
                "fields": ["src_ip", "dst_ip", "protocol", "dst_port"],
                "limit": 10,
            }
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "scapy"
    assert result["packets"][0] == {
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.20",
        "protocol": "tcp",
        "dst_port": 443,
    }
    assert "payload" not in json.dumps(result)


def test_protocol_inspect_rejects_payload_field() -> None:
    from uagent.tools import protocol_inspect_tool

    result = json.loads(
        protocol_inspect_tool.run_tool(
            {"pcap_path": "capture.pcap", "fields": ["payload"]}
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "FIELD_NOT_ALLOWED"
