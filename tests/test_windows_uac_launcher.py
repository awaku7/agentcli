from __future__ import annotations

import sys


def test_build_helper_command_uses_fixed_module() -> None:
    from uagent.tools import windows_uac_launcher

    command = windows_uac_launcher.build_helper_command("request.json", "result.json")

    assert command[0] == sys.executable
    assert command[1:3] == ["-m", "uagent.tools.network_privileged_helper"]
    assert "request.json" in command
    assert "result.json" in command


def test_build_helper_command_rejects_arbitrary_module() -> None:
    from uagent.tools import windows_uac_launcher

    try:
        windows_uac_launcher.build_helper_command(
            "request.json", "result.json", module="os.system"
        )
    except ValueError as exc:
        assert "fixed" in str(exc)
    else:
        raise AssertionError("arbitrary module must be rejected")


def test_uac_launcher_is_not_available_on_non_windows(monkeypatch) -> None:
    from uagent.tools import windows_uac_launcher

    monkeypatch.setattr(windows_uac_launcher.os, "name", "posix")

    try:
        windows_uac_launcher.shell_execute_runas(["ignored"])
    except RuntimeError as exc:
        assert "Windows" in str(exc)
    else:
        raise AssertionError("UAC launcher must reject non-Windows")
