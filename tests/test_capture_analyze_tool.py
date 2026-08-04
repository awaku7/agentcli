from __future__ import annotations

import json

from uagent.tools import capture_analyze_tool as tool


def test_missing_pcap_path_is_structured_error() -> None:
    result = json.loads(tool.run_tool({}))
    assert result["ok"] is False
    assert result["error"]["code"] == "INPUT_REQUIRED"


def test_invalid_operation_is_rejected() -> None:
    result = json.loads(
        tool.run_tool({"pcap_path": "sample.pcap", "operations": ["live_capture"]})
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "UNSUPPORTED_OPERATION"


def test_offline_composition_and_correlation(monkeypatch) -> None:
    def fake_pcap(args):
        operation = args["operation"]
        if operation == "flows":
            return json.dumps(
                {
                    "ok": True,
                    "operation": "flows",
                    "flows": [
                        {
                            "src_ip": "192.168.1.20",
                            "dst_ip": "192.168.1.30",
                            "src_port": 50000,
                            "dst_port": 443,
                            "protocol": "tcp",
                            "packets": 2,
                            "bytes": 1200,
                        }
                    ],
                }
            )
        return json.dumps({"ok": True, "operation": operation})

    captured = {}

    def fake_local(args):
        captured.update(args)
        return json.dumps({"ok": True, "operation": "correlate", "results": []})

    monkeypatch.setattr(tool.pcap_analyze_tool, "run_tool", fake_pcap)
    monkeypatch.setattr(tool.local_network_tool, "run_tool", fake_local)

    result = json.loads(tool.run_tool({"pcap_path": "sample.pcap"}))
    assert result["ok"] is True
    assert set(result["analysis"]) == {"summary", "flows", "detect", "impact"}
    assert result["correlation"]["ok"] is True
    assert captured["findings"][0]["dst_port"] == 443
    assert result["warnings"]


def test_correlation_can_be_disabled(monkeypatch) -> None:
    calls = []

    def fake_pcap(args):
        calls.append(args["operation"])
        return json.dumps({"ok": True, "operation": args["operation"], "flows": []})

    def fail_local(_args):
        raise AssertionError("local_network must not run when correlate=false")

    monkeypatch.setattr(tool.pcap_analyze_tool, "run_tool", fake_pcap)
    monkeypatch.setattr(tool.local_network_tool, "run_tool", fail_local)

    result = json.loads(
        tool.run_tool(
            {
                "pcap_path": "sample.pcap",
                "operations": ["flows"],
                "correlate": False,
            }
        )
    )
    assert result["ok"] is True
    assert calls == ["flows"]
    assert result["correlation"] is None
