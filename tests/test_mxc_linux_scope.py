from __future__ import annotations

import pytest

from uagent.runtime import mxc_linux_scope


def test_systemd_scope_command_requests_host_enforced_group_limits():
    command = mxc_linux_scope.systemd_scope_command(
        "/usr/bin/systemd-run",
        "uagent-mxc-abc.scope",
        ["/opt/node/bin/node", "/runtime/mxc_adapter.mjs", "worker"],
    )

    assert command[:2] == ["/usr/bin/systemd-run", "--user"]
    assert "--scope" in command
    # --pipe and --wait are both incompatible with --scope.
    assert "--pipe" not in command
    assert "--wait" not in command
    assert "--property=MemoryMax=1073741824" in command
    assert "--property=MemorySwapMax=0" in command
    assert "--property=TasksMax=64" in command
    assert "--property=CPUAccounting=yes" in command
    assert "--property=CPUQuota=100%" in command
    assert command[-4:] == [
        "--",
        "/opt/node/bin/node",
        "/runtime/mxc_adapter.mjs",
        "worker",
    ]


def test_linux_resource_limit_parsers_are_conservative():
    assert mxc_linux_scope._parse_bytes("1073741824") == 1_073_741_824
    assert mxc_linux_scope._parse_bytes("1G") == 1_073_741_824
    assert mxc_linux_scope._parse_bytes("infinity") is None
    assert mxc_linux_scope._parse_systemd_duration_us("1s") == 1_000_000
    assert mxc_linux_scope._parse_systemd_duration_us("500ms") == 500_000
    assert mxc_linux_scope._parse_systemd_duration_us("infinity") is None


def test_stop_escalates_to_killing_the_entire_scope_after_stop_timeout(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.wait_calls = 0

        def poll(self):
            return None

        def wait(self, timeout):
            self.wait_calls += 1
            return 0

    process = FakeProcess()
    scope = mxc_linux_scope.LinuxSystemdScope(
        process,
        unit="uagent-mxc-test.scope",
        environment={},
        systemctl="/usr/bin/systemctl",
    )
    verified = []
    scope._verify_stopped = lambda: verified.append(True)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[2] == "stop" and commands.count(command) == 1:
            raise mxc_linux_scope.subprocess.TimeoutExpired(command, 10)
        return mxc_linux_scope.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(mxc_linux_scope.subprocess, "run", run)
    scope.stop()

    kill_command = next(command for command in commands if command[2] == "kill")
    assert "--kill-whom=all" in kill_command
    assert "--signal=SIGKILL" in kill_command
    assert scope._closed
    assert verified == [True]


def test_cpu_watchdog_stops_scope_at_the_aggregate_budget(monkeypatch):
    class RunningProcess:
        def poll(self):
            return None

    scope = mxc_linux_scope.LinuxSystemdScope(
        RunningProcess(),
        unit="uagent-mxc-test.scope",
        environment={},
        systemctl="/usr/bin/systemctl",
    )
    monkeypatch.setattr(
        scope,
        "_show",
        lambda name: str(mxc_linux_scope.CPU_BUDGET_NS),
    )
    stopped = []
    monkeypatch.setattr(scope, "stop", lambda: stopped.append(True))

    scope._monitor_cpu()

    assert scope.cpu_exceeded
    assert stopped == [True]


def test_stopped_scope_checks_saved_cgroup_when_systemd_forgets_the_unit(
    monkeypatch, tmp_path
):
    cgroup_root = tmp_path / "cgroup"
    scope_path = cgroup_root / "user.slice" / "uagent.scope"
    scope_path.mkdir(parents=True)
    (scope_path / "cgroup.events").write_text(
        "populated 1\nfrozen 0\n", encoding="ascii"
    )
    monkeypatch.setattr(mxc_linux_scope, "CGROUP_ROOT", cgroup_root)

    class ExitedProcess:
        def poll(self):
            return 0

    scope = mxc_linux_scope.LinuxSystemdScope(
        ExitedProcess(),
        unit="uagent-mxc-test.scope",
        environment={},
        systemctl="/usr/bin/systemctl",
    )
    scope._cgroup_path = scope_path
    scope._show = lambda name: (_ for _ in ()).throw(RuntimeError("unit not found"))

    with pytest.raises(RuntimeError, match="still contains processes"):
        scope._verify_stopped()


def test_stale_scope_cleanup_requires_a_sha256_workspace_key():
    with pytest.raises(ValueError, match="scope key"):
        mxc_linux_scope.stop_stale_scope("../not-a-scope")
