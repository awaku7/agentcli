from __future__ import annotations

import json
from pathlib import Path


def test_extract_filters_tcp_destination_port_and_returns_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 443,
            "length": 100,
        },
        {
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.20",
            "protocol": "tcp",
            "dst_port": 80,
            "length": 100,
        },
    ]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    monkeypatch.setattr(
        pcap_analyze_tool, "_write_packet", lambda _writer, packet: None
    )

    source = tmp_path / "capture.pcap"
    output = tmp_path / "filtered.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "extract",
                "output_path": str(output),
                "filter": {"protocol": "tcp", "dst_port": 443},
            }
        )
    )

    assert result["ok"] is True
    assert result["written_packets"] == 1
    assert result["read_packets"] == 2
    assert result["artifact"]["kind"] == "pcap"
    assert "pcap_path" not in result


def test_extract_rejects_same_input_and_output(tmp_path: Path) -> None:
    from uagent.tools import pcap_analyze_tool

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "extract",
                "output_path": str(source),
                "filter": {},
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INPUT_OUTPUT_SAME"


def test_extract_respects_limit(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [{"protocol": "tcp", "length": 64} for _ in range(5)]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    monkeypatch.setattr(
        pcap_analyze_tool, "_write_packet", lambda _writer, packet: None
    )

    source = tmp_path / "capture.pcap"
    output = tmp_path / "filtered.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "extract",
                "output_path": str(output),
                "filter": {},
                "limit": 2,
            }
        )
    )

    assert result["ok"] is True
    assert result["written_packets"] == 2
    assert result["truncated"] is True


def test_default_response_does_not_include_payload(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    packets = [{"protocol": "tcp", "length": 64, "payload": b"secret"}]
    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", lambda _path: iter(packets))
    monkeypatch.setattr(
        pcap_analyze_tool, "_write_packet", lambda _writer, packet: None
    )

    source = tmp_path / "capture.pcap"
    output = tmp_path / "filtered.pcap"
    source.write_bytes(b"pcap")

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "extract",
                "output_path": str(output),
                "filter": {},
            }
        )
    )

    assert "payload" not in json.dumps(result)
