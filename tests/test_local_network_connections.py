from __future__ import annotations

import json


def test_connections_include_process_metadata_and_filters(monkeypatch) -> None:
    from uagent.tools import local_network_tool

    class FakePsutil:
        @staticmethod
        def net_connections(kind="inet"):
            assert kind == "inet"
            return [
                type(
                    "Conn",
                    (),
                    {
                        "family": "AF_INET",
                        "type": "SOCK_STREAM",
                        "laddr": ("192.168.0.54", 50000),
                        "raddr": ("31.13.91.2", 443),
                        "status": "ESTABLISHED",
                        "pid": 1234,
                    },
                )(),
                type(
                    "Conn",
                    (),
                    {
                        "family": "AF_INET",
                        "type": "SOCK_STREAM",
                        "laddr": ("192.168.0.54", 50001),
                        "raddr": ("10.0.0.2", 80),
                        "status": "TIME_WAIT",
                        "pid": None,
                    },
                )(),
            ]

        class NoSuchProcess(Exception):
            pass

        class AccessDenied(Exception):
            pass

        @staticmethod
        def Process(pid):
            return type("Process", (), {"name": lambda self: "example.exe"})()

    monkeypatch.setattr(local_network_tool, "_get_psutil", lambda: FakePsutil)

    result = json.loads(
        local_network_tool.run_tool(
            {
                "operation": "connections",
                "remote_ip": "31.13.91.2",
                "port": 443,
            }
        )
    )

    assert result["ok"] is True
    assert len(result["connections"]) == 1
    connection = result["connections"][0]
    assert connection["remote_port"] == 443
    assert connection["pid"] == 1234
    assert connection["process_name"] == "example.exe"


def test_connections_can_omit_process_metadata(monkeypatch) -> None:
    from uagent.tools import local_network_tool

    class FakePsutil:
        @staticmethod
        def net_connections(kind="inet"):
            return [type("Conn", (), {"laddr": ("127.0.0.1", 1), "raddr": (), "status": "LISTEN", "pid": 1})()]

    monkeypatch.setattr(local_network_tool, "_get_psutil", lambda: FakePsutil)
    result = json.loads(local_network_tool.run_tool({"operation": "connections", "include_process": False}))

    assert result["ok"] is True
    assert "pid" not in result["connections"][0]
