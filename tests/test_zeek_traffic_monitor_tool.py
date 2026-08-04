from __future__ import annotations

import json
from pathlib import Path


def test_traffic_monitor_parses_zeek_conn_log(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import traffic_monitor_tool

    log = tmp_path / "conn.log"
    log.write_text(
        "#separator \\x09\n"
        "#fields ts\x09uid\x09id.orig_h\x09id.resp_h\x09id.resp_p\x09proto\x09orig_bytes\x09resp_bytes\n"
        "1.0\tC1\t192.168.1.10\t192.168.1.20\t443\ttcp\t100\t200\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(traffic_monitor_tool, "_find_zeek", lambda: "zeek")
    monkeypatch.setattr(traffic_monitor_tool, "_run_zeek", lambda *_args: log)

    result = json.loads(
        traffic_monitor_tool.run_tool(
            {"pcap_path": str(tmp_path / "capture.pcap"), "limit": 10}
        )
    )

    assert result["ok"] is True
    assert result["backend"] == "zeek"
    assert result["events"][0]["id.orig_h"] == "192.168.1.10"
    assert result["events"][0]["id.resp_p"] == "443"


def test_traffic_monitor_missing_zeek(monkeypatch, tmp_path: Path) -> None:
    from uagent.tools import traffic_monitor_tool

    monkeypatch.setattr(traffic_monitor_tool, "_find_zeek", lambda: None)
    result = json.loads(
        traffic_monitor_tool.run_tool({"pcap_path": str(tmp_path / "capture.pcap")})
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "EXTERNAL_DEPENDENCY_MISSING"
