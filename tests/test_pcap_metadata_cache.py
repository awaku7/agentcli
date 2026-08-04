from __future__ import annotations

from pathlib import Path


def test_metadata_cache_reuses_records(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import pcap_analyze_tool

    source = tmp_path / "capture.pcap"
    source.write_bytes(b"fake-pcap")
    packets = [
        {
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "protocol": "tcp",
            "src_port": 50000,
            "dst_port": 443,
            "length": 60,
            "timestamp": 1.0,
        }
    ]
    calls = {"count": 0}

    monkeypatch.setattr(pcap_analyze_tool, "_is_real_pcap", lambda _path: True)

    def reader(_path):
        calls["count"] += 1
        return iter(packets)

    monkeypatch.setattr(pcap_analyze_tool, "_iter_packets", reader)
    monkeypatch.setenv("UAGENT_PCAP_CACHE_DIR", str(tmp_path / "cache"))

    first = pcap_analyze_tool._metadata_records(source)
    second = pcap_analyze_tool._metadata_records(source)

    assert first == second
    assert calls["count"] == 1
    assert list((tmp_path / "cache").glob("*.sqlite"))
