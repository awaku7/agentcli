from __future__ import annotations

import json


def test_udp_send_defaults_to_dry_run(monkeypatch) -> None:
    from uagent.tools import packet_send_tool

    def fail_socket(*args, **kwargs):
        raise AssertionError("socket must not be opened during dry_run")

    monkeypatch.setattr(packet_send_tool.socket, "socket", fail_socket)

    result = json.loads(
        packet_send_tool.run_tool(
            {
                "action": "udp_send",
                "target": "192.168.1.10",
                "port": 9999,
                "payload": "test",
            }
        )
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["sent"] == 0
    assert result["payload_bytes"] == 4


def test_udp_send_can_be_mocked(monkeypatch) -> None:
    from uagent.tools import packet_send_tool

    class FakeSocket:
        def __init__(self):
            self.sent = []

        def sendto(self, data, address):
            self.sent.append((data, address))
            return len(data)

        def close(self):
            pass

    fake = FakeSocket()
    monkeypatch.setattr(packet_send_tool.socket, "socket", lambda *args, **kwargs: fake)

    result = json.loads(
        packet_send_tool.run_tool(
            {
                "action": "udp_send",
                "target": "192.168.1.10",
                "port": 9999,
                "payload": "test",
                "dry_run": False,
                "send_confirmed": True,
                "count": 2,
                "interval": 0,
            }
        )
    )

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["sent"] == 2
    assert len(fake.sent) == 2


def test_send_rejects_excessive_count() -> None:
    from uagent.tools import packet_send_tool

    result = json.loads(
        packet_send_tool.run_tool(
            {
                "action": "udp_send",
                "target": "192.168.1.10",
                "port": 9999,
                "payload": "test",
                "count": 11,
                "dry_run": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "COUNT_LIMIT_EXCEEDED"
