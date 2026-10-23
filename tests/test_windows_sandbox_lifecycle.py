from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from uagent.runtime.windows_sandbox_lifecycle import (
    WindowsSandboxLease,
    WindowsSandboxLifecycleClient,
    WindowsSandboxLifecycleError,
    WxcCommandResult,
)

SANDBOX_ID = "wsb:deadbeef"


class ScriptedRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[list[str], float, dict | None]] = []

    def __call__(self, argv, timeout_seconds):
        args = list(argv)
        config = None
        if "--config" in args:
            config = json.loads(Path(args[args.index("--config") + 1]).read_text())
        self.calls.append((args, timeout_seconds, config))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def make_client(tmp_path, runner):
    runtime = tmp_path / "runtime"
    package = runtime / "node_modules" / "@microsoft" / "mxc-sdk"
    (package / "bin" / "x64").mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "@microsoft/mxc-sdk", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (package / "bin" / "x64" / "wxc-exec.exe").write_bytes(b"test stub")
    return WindowsSandboxLifecycleClient(runtime, command_runner=runner)


def test_lifecycle_client_uses_narrow_schema_and_owner_id(tmp_path):
    runner = ScriptedRunner(
        [
            WxcCommandResult(0, json.dumps({"sandboxId": SANDBOX_ID}), ""),
            WxcCommandResult(0, "started", ""),
            WxcCommandResult(0, "guest output", ""),
            WxcCommandResult(0, "stopped", ""),
            WxcCommandResult(0, "deprovisioned", ""),
        ]
    )
    workspace = tmp_path / "scope-workspace"
    workspace.mkdir()
    client = make_client(tmp_path, runner)

    lease = client.provision(workspace)
    assert lease.sandbox_id == SANDBOX_ID
    provision_args, _, config = runner.calls[0]
    assert provision_args[provision_args.index("--operation") + 1] == "provision"
    assert config["containment"] == "windows_sandbox"
    assert "fallback" not in config
    assert config["filesystem"] == {
        "readwritePaths": [str(workspace.resolve())],
        "readonlyPaths": [],
    }
    assert "--force-reclaim" not in provision_args

    client.start(lease)
    result = client.execute(
        lease, command_line="powershell.exe -Command Write-Output ok", timeout_ms=5000
    )
    assert result.stdout == "guest output"
    client.stop(lease)
    client.deprovision(lease)

    for operation in ("start", "exec", "stop", "deprovision"):
        args = next(args for args, _, _ in runner.calls if operation in args)
        assert args[args.index("--container-id") + 1] == SANDBOX_ID
        assert "--force-reclaim" not in args
    assert lease.state == "closed"


def test_lifecycle_client_rejects_unowned_or_malformed_sandbox_ids(tmp_path):
    runner = ScriptedRunner([])
    workspace = tmp_path / "scope-workspace"
    workspace.mkdir()
    client = make_client(tmp_path, runner)
    forged = WindowsSandboxLease("wsb:deadbeef", workspace)

    with pytest.raises(WindowsSandboxLifecycleError, match="not owned"):
        client.stop(forged)
    with pytest.raises(WindowsSandboxLifecycleError, match="invalid MXC"):
        client._validate_sandbox_id("foreign-sandbox")
    assert runner.calls == []


def test_ambiguous_provision_result_poison_client_fail_closed(tmp_path):
    runner = ScriptedRunner(
        [
            WxcCommandResult(
                0,
                json.dumps({"sandboxId": SANDBOX_ID, "containerId": "wsb:0123abcd"}),
                "",
            )
        ]
    )
    workspace = tmp_path / "scope-workspace"
    workspace.mkdir()
    client = make_client(tmp_path, runner)

    with pytest.raises(WindowsSandboxLifecycleError, match="exactly one"):
        client.provision(workspace)
    with pytest.raises(WindowsSandboxLifecycleError, match="outcome is uncertain"):
        client.provision(workspace)
    assert len(runner.calls) == 1


def test_exec_timeout_attempts_only_owner_bound_deprovision(tmp_path):
    runner = ScriptedRunner(
        [
            WxcCommandResult(0, json.dumps({"sandboxId": SANDBOX_ID}), ""),
            WxcCommandResult(0, "started", ""),
            subprocess.TimeoutExpired(cmd="wxc-exec", timeout=1),
            WxcCommandResult(0, "deprovisioned", ""),
        ]
    )
    workspace = tmp_path / "scope-workspace"
    workspace.mkdir()
    client = make_client(tmp_path, runner)
    lease = client.provision(workspace)
    client.start(lease)

    with pytest.raises(WindowsSandboxLifecycleError, match="timed out"):
        client.execute(
            lease,
            command_line="powershell.exe -Command Start-Sleep 99",
            timeout_ms=1000,
        )

    cleanup_args = runner.calls[-1][0]
    assert cleanup_args[cleanup_args.index("--operation") + 1] == "deprovision"
    assert cleanup_args[cleanup_args.index("--container-id") + 1] == SANDBOX_ID
    assert "--force-reclaim" not in cleanup_args
    assert lease.state == "closed"


def test_client_rejects_wrong_pinned_sdk_version(tmp_path):
    runner = ScriptedRunner([])
    runtime = tmp_path / "runtime"
    package = runtime / "node_modules" / "@microsoft" / "mxc-sdk"
    (package / "bin" / "x64").mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "@microsoft/mxc-sdk", "version": "1.0.1"}),
        encoding="utf-8",
    )
    (package / "bin" / "x64" / "wxc-exec.exe").write_bytes(b"test stub")

    with pytest.raises(WindowsSandboxLifecycleError, match="expected pinned"):
        WindowsSandboxLifecycleClient(runtime, command_runner=runner)
    assert runner.calls == []
