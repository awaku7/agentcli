from __future__ import annotations

import json


def test_packet_probe_uses_fixed_uac_helper_when_allowed(monkeypatch) -> None:
    from uagent.tools import packet_probe_tool

    monkeypatch.setattr(packet_probe_tool.os, "name", "nt")
    monkeypatch.setattr(
        packet_probe_tool.windows_uac_launcher,
        "create_request_paths",
        lambda: ("request.json", "result.json"),
    )
    monkeypatch.setattr(
        packet_probe_tool.windows_uac_launcher, "write_request", lambda *_args: None
    )
    monkeypatch.setattr(
        packet_probe_tool.windows_uac_launcher,
        "build_helper_command",
        lambda *_args: ["python", "-m", "uagent.tools.network_privileged_helper"],
    )
    monkeypatch.setattr(
        packet_probe_tool.windows_uac_launcher, "shell_execute_runas", lambda _args: 33
    )
    monkeypatch.setattr(
        packet_probe_tool.windows_uac_launcher,
        "wait_for_result",
        lambda *_args, **_kwargs: {"ok": True, "result": {"state": "open"}},
    )

    result = json.loads(
        packet_probe_tool.run_tool(
            {
                "action": "tcp_syn",
                "target": "192.168.1.10",
                "port": 443,
                "dry_run": False,
                "allow_elevation": True,
                "elevation_confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["elevated"] is True
    assert result["result"]["state"] == "open"
