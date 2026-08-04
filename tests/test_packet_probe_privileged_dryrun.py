from __future__ import annotations

import json


def test_raw_probe_dry_run_returns_plan_without_privilege() -> None:
    from uagent.tools import packet_probe_tool

    result = json.loads(
        packet_probe_tool.run_tool(
            {
                "action": "tcp_syn",
                "target": "192.168.1.10",
                "port": 443,
                "dry_run": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["requires_privilege"] is True
    assert result["action"] == "tcp_syn"
