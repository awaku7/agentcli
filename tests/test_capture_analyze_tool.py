from __future__ import annotations

import json

from uagent.tools import capture_analyze_tool as tool


def test_missing_pcap_path_is_structured_error() -> None:
    result = json.loads(tool.run_tool({}))
    assert result["ok"] is False
    assert result["error"]["code"] == "INPUT_REQUIRED"


def test_live_capture_rejects_non_loopback_interface() -> None:
    result = json.loads(
        tool.run_tool({"live_capture": True, "interface": "Ethernet"})
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "INTERFACE_NOT_ALLOWED"


def test_live_capture_composes_analysis(monkeypatch) -> None:
    monkeypatch.setattr(
        tool,
        "_capture_loopback",
        lambda _args: {
            "ok": True,
            "interface": "lo",
            "duration": 1,
            "max_packets": 2,
            "packet_count": 2,
            "pcap_path": "captured.pcap",
        },
    )
    monkeypatch.setattr(
        tool.pcap_analyze_tool,
        "run_tool",
        lambda args: json.dumps({"ok": True, "operation": args["operation"], "findings": []}),
    )
    monkeypatch.setattr(
        tool.local_network_tool,
        "run_tool",
        lambda _args: json.dumps({"ok": True, "operation": "correlate", "results": []}),
    )
    result = json.loads(tool.run_tool({"live_capture": True, "operations": ["detect"]}))
    assert result["ok"] is True
    assert result["capture"]["packet_count"] == 2
    assert result["warnings"] == ["Live capture is restricted to a loopback interface."]


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


def test_classification_is_conservative() -> None:
    normal = tool._classify({"detect": {"findings": []}, "impact": {"devices": []}}, [])
    assert normal["classification"] == "normal"

    review = tool._classify(
        {
            "detect": {"findings": [{"category": "unusual_port", "severity": "medium"}]},
            "impact": {"devices": []},
        },
        [],
    )
    assert review["classification"] == "review"

    suspicious = tool._classify(
        {
            "detect": {"findings": [{"category": "port_scan", "severity": "high"}]},
            "impact": {"devices": []},
        },
        [],
    )
    assert suspicious["classification"] == "suspicious"

    unknown = tool._classify({}, [{"operation": "detect"}])
    assert unknown["classification"] == "unknown"


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
