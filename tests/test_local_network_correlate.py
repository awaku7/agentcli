from __future__ import annotations

import json


def test_correlate_matches_pcap_finding_to_current_connection(monkeypatch) -> None:
    from uagent.tools import local_network_tool

    class FakePsutil:
        @staticmethod
        def net_connections(kind="inet"):
            return [
                type(
                    "Conn",
                    (),
                    {
                        "family": "AF_INET",
                        "type": "SOCK_STREAM",
                        "laddr": ("192.168.0.54", 60000),
                        "raddr": ("31.13.91.2", 443),
                        "status": "ESTABLISHED",
                        "pid": 77,
                    },
                )()
            ]

        class NoSuchProcess(Exception):
            pass

        class AccessDenied(Exception):
            pass

        @staticmethod
        def Process(pid):
            return type("Process", (), {"name": lambda self: "browser.exe"})()

    monkeypatch.setattr(local_network_tool, "_get_psutil", lambda: FakePsutil)
    result = json.loads(
        local_network_tool.run_tool(
            {
                "operation": "correlate",
                "findings": [
                    {
                        "category": "large_transfer",
                        "src": "192.168.0.54",
                        "dst": "31.13.91.2",
                        "dst_port": 443,
                    },
                    {
                        "category": "beaconing",
                        "src": "192.168.0.54",
                        "dst": "203.0.113.10",
                        "dst_port": 443,
                    },
                ],
            }
        )
    )

    assert result["ok"] is True
    assert result["results"][0]["matched"] is True
    assert result["results"][0]["connections"][0]["process_name"] == "browser.exe"
    assert result["results"][1]["matched"] is False
