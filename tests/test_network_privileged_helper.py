from __future__ import annotations


def test_helper_accepts_only_known_probe_actions() -> None:
    from uagent.tools import network_privileged_helper

    request = {
        "action": "tcp_syn",
        "target": "192.168.1.10",
        "port": 443,
        "dry_run": True,
    }

    validated = network_privileged_helper.validate_request(request)

    assert validated["action"] == "tcp_syn"
    assert validated["target"] == "192.168.1.10"
    assert validated["port"] == 443


def test_helper_dry_run_does_not_import_scapy() -> None:
    from uagent.tools import network_privileged_helper

    result = network_privileged_helper.run_request(
        {"action": "icmp", "target": "192.168.1.10", "dry_run": True}
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["plan"]["action"] == "icmp"


def test_helper_rejects_arbitrary_command() -> None:
    from uagent.tools import network_privileged_helper

    try:
        network_privileged_helper.validate_request(
            {"action": "run_command", "command": "whoami"}
        )
    except ValueError as exc:
        assert "action" in str(exc)
    else:
        raise AssertionError("arbitrary command must be rejected")


def test_helper_rejects_invalid_target() -> None:
    from uagent.tools import network_privileged_helper

    try:
        network_privileged_helper.validate_request(
            {"action": "icmp", "target": "", "port": 0}
        )
    except ValueError as exc:
        assert "target" in str(exc)
    else:
        raise AssertionError("empty target must be rejected")
