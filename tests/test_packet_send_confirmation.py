from __future__ import annotations

import json


def test_real_send_requires_human_confirmation() -> None:
    from uagent.tools import packet_send_tool

    result = json.loads(
        packet_send_tool.run_tool(
            {
                "action": "udp_send",
                "target": "192.168.1.10",
                "port": 9999,
                "payload": "test",
                "dry_run": False,
                "send_confirmed": False,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "SEND_CONFIRMATION_REQUIRED"
