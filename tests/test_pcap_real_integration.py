from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_fixture(path: Path) -> None:
    pytest.importorskip("scapy.all")
    from scapy.all import IP, TCP, PcapWriter, Raw

    writer = PcapWriter(str(path), append=False, sync=True)
    try:
        packet = IP(src="192.168.1.10", dst="192.168.1.20") / TCP(
            sport=50000, dport=443, seq=1000, flags="A"
        ) / Raw(b"hello")
        packet.time = 1.0
        writer.write(packet)
        retransmission = IP(src="192.168.1.10", dst="192.168.1.20") / TCP(
            sport=50000, dport=443, seq=1000, flags="A"
        ) / Raw(b"hello")
        retransmission.time = 2.0
        writer.write(retransmission)
    finally:
        writer.close()


def test_real_pcap_summary_and_flows(tmp_path: Path) -> None:
    from uagent.tools import pcap_analyze_tool

    source = tmp_path / "real.pcap"
    _write_fixture(source)

    summary = json.loads(
        pcap_analyze_tool.run_tool(
            {"pcap_path": str(source), "operation": "summary"}
        )
    )
    flows = json.loads(
        pcap_analyze_tool.run_tool(
            {"pcap_path": str(source), "operation": "flows"}
        )
    )

    assert summary["ok"] is True
    assert summary["packet_count"] == 2
    assert summary["protocols"]["tcp"] == 2
    assert flows["ok"] is True
    assert flows["flow_count"] == 1
    assert flows["flows"][0]["packets"] == 2


def test_real_pcap_detects_retransmission(tmp_path: Path) -> None:
    from uagent.tools import pcap_analyze_tool

    source = tmp_path / "real.pcap"
    _write_fixture(source)

    result = json.loads(
        pcap_analyze_tool.run_tool(
            {
                "pcap_path": str(source),
                "operation": "detect",
                "rules": ["tcp_retransmission"],
            }
        )
    )

    assert result["ok"] is True
    assert result["findings"][0]["category"] == "tcp_retransmission"
