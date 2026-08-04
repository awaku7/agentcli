from __future__ import annotations

import json


def test_raw_probe_requires_human_confirmation_before_uac() -> None:
    from uagent.tools import packet_probe_tool

    result = json.loads(
        packet_probe_tool.run_tool(
            {
                "action": "tcp_syn",
                "target": "192.168.1.10",
                "port": 443,
                "dry_run": False,
                "allow_elevation": True,
                "elevation_confirmed": False,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "ELEVATION_CONFIRMATION_REQUIRED"
