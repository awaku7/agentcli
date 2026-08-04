from __future__ import annotations

import json


def test_protocol_inspect_uses_tshark_when_requested(tmp_path, monkeypatch) -> None:
    from uagent.tools import protocol_inspect_tool

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")
    monkeypatch.setattr(protocol_inspect_tool, "_find_tshark", lambda: "tshark.exe")
    monkeypatch.setattr(
        protocol_inspect_tool,
        "_run_tshark",
        lambda *_args, **_kwargs: [{"ip.src": "192.168.1.10", "ip.dst": "192.168.1.20"}],
    )

    result = json.loads(
        protocol_inspect_tool.run_tool(
            {
                "pcap_path": str(source),
                "backend": "tshark",
                "display_filter": "ip",
                "fields": ["ip.src", "ip.dst"],
            }
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "tshark"
    assert result["packets"][0]["ip.src"] == "192.168.1.10"


def test_protocol_inspect_falls_back_when_tshark_missing(tmp_path, monkeypatch) -> None:
    from uagent.tools import protocol_inspect_tool

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"pcap")
    monkeypatch.setattr(protocol_inspect_tool, "_find_tshark", lambda: None)
    monkeypatch.setattr(protocol_inspect_tool, "_iter_packets", lambda _path: iter([]))

    result = json.loads(
        protocol_inspect_tool.run_tool(
            {
                "pcap_path": str(source),
                "backend": "auto",
                "display_filter": "ip",
                "fields": ["src_ip"],
            }
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "scapy"
    assert result["degraded"] is True
