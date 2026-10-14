from __future__ import annotations

import pytest

from uagent import tools
from uagent.a2a.engine import run_once_uag
from uagent.runtime.execution_broker import (
    CancellationResult,
    ExecutionClass,
    IsolationLevel,
    SandboxCapabilities,
    SandboxCapability,
    SecurityProfile,
    cancel_execution_safely,
    TrustedSandboxScope,
    classify_tool,
    execution_profile,
    is_trusted_local_web,
    route_tool,
)


def _remote_scope() -> TrustedSandboxScope:
    return TrustedSandboxScope(
        deployment_id="test",
        principal_id="service",
        project_id="project",
        scope_kind="a2a-task",
        scope_id="task-1",
    )


def test_local_web_requires_exact_loopback_and_local_identity():
    assert is_trusted_local_web("127.0.0.1", "local")
    for bind_host, identity_mode in (
        ("0.0.0.0", "local"),
        ("::", "local"),
        ("192.168.1.20", "local"),
        ("127.0.0.1", "oidc"),
        ("localhost", "local"),
    ):
        assert not is_trusted_local_web(bind_host, identity_mode)


def test_a2a_requires_server_task_id_before_starting_run():
    with pytest.raises(ValueError, match="task_id is required"):
        run_once_uag(user_text="hello", task_id="")


def test_remote_call_without_trusted_scope_is_denied():
    decision = route_tool(
        "get_current_time", {}, profile=SecurityProfile.REMOTE, known_tool=True
    )
    assert not decision.allowed
    assert decision.reason == "trusted remote scope is required"


def test_remote_general_tools_fail_closed_without_backend():
    for name in ("read_file", "get_env", "http_request"):
        with execution_profile(SecurityProfile.REMOTE, scope=_remote_scope()):
            decision = route_tool(
                name, {}, profile=SecurityProfile.REMOTE, known_tool=True
            )
        assert decision.execution_class is ExecutionClass.SANDBOX
        assert not decision.allowed
        assert "sandbox" in decision.reason


def test_unregistered_remote_tool_is_denied_even_if_backend_exists():
    with execution_profile(SecurityProfile.REMOTE, scope=_remote_scope()):
        decision = route_tool(
            "some_dynamic_tool",
            {},
            profile=SecurityProfile.REMOTE,
            sandbox_enabled=True,
            backend_available=True,
            backend_capabilities=SandboxCapabilities(
                isolation_level=IsolationLevel.VM,
                available=frozenset(SandboxCapability),
            ),
            known_tool=False,
        )
    assert decision.execution_class is ExecutionClass.DENY
    assert not decision.allowed
    assert "unknown" in decision.reason


def test_remote_capability_probe_requires_vm_and_all_controls():
    partial = SandboxCapabilities(
        isolation_level=IsolationLevel.PROCESS,
        available=frozenset({SandboxCapability.FILESYSTEM_POLICY}),
    )
    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=True, scope=_remote_scope()
    ):
        denied = route_tool(
            "python_exec",
            {},
            profile=SecurityProfile.REMOTE,
            sandbox_enabled=True,
            backend_available=True,
            backend_capabilities=partial,
            known_tool=True,
        )
    assert not denied.allowed
    assert denied.reason == "sandbox capabilities are insufficient"

    claims_vm = SandboxCapabilities(
        isolation_level=IsolationLevel.VM,
        available=frozenset(SandboxCapability),
    )
    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=True, scope=_remote_scope()
    ):
        still_unavailable = route_tool(
            "python_exec",
            {},
            profile=SecurityProfile.REMOTE,
            sandbox_enabled=True,
            backend_available=True,
            backend_capabilities=claims_vm,
            known_tool=True,
        )
    assert not still_unavailable.allowed
    assert still_unavailable.reason == "sandbox backend is not implemented"


def test_cancel_result_requires_confirmed_execution_stop():
    assert CancellationResult(execution_stopped=True).safe_to_reuse
    assert not CancellationResult(execution_stopped=False).safe_to_reuse
    assert not CancellationResult(
        execution_stopped=True, lease_terminated=True
    ).safe_to_reuse


def test_local_sandbox_opt_in_does_not_fall_back_to_host():
    decision = route_tool(
        "python_exec",
        {},
        profile=SecurityProfile.LOCAL_TRUSTED,
        sandbox_enabled=True,
        backend_available=False,
    )
    assert not decision.allowed
    assert decision.reason == "no compliant sandbox backend"


def test_remote_sandbox_opt_in_does_not_allow_missing_backend():
    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=True, scope=_remote_scope()
    ):
        decision = route_tool(
            "python_exec",
            {},
            profile=SecurityProfile.REMOTE,
            sandbox_enabled=True,
            backend_available=False,
            known_tool=True,
        )
    assert not decision.allowed
    assert decision.reason == "no compliant sandbox backend"


def test_local_off_preserves_direct_dispatch_without_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setitem(tools._RUNNERS, "test_local", lambda _args: "local-ok")
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "test_local", False)

    with execution_profile(SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=False):
        assert tools.run_tool("test_local", {}) == "local-ok"


def test_remote_dispatch_never_calls_host_runner(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        tools, "_ensure_loaded", lambda: calls.append("plugin_load") or None
    )
    monkeypatch.setitem(
        tools._RUNNERS, "read_file", lambda _args: calls.append("runner") or "bad"
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "read_file", False)

    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=False, scope=_remote_scope()
    ):
        result = tools.run_tool("read_file", {"path": "secret.txt"})

    assert "execution denied" in result
    assert calls == []


def test_remote_brokered_time_does_not_enter_host_runner(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        tools, "_ensure_loaded", lambda: calls.append("plugin_load") or None
    )
    monkeypatch.setitem(
        tools._RUNNERS,
        "get_current_time",
        lambda _args: calls.append("runner") or "bad",
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "get_current_time", False)

    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=False, scope=_remote_scope()
    ):
        result = tools.run_tool("get_current_time", {})

    assert result.startswith("[get_current_time]")
    assert "NTP Sync:        N/A" in result
    assert calls == []


def test_brokered_operation_rejects_arguments():
    assert (
        classify_tool("get_current_time", {"host": "example.org"})
        is ExecutionClass.DENY
    )
    with execution_profile(SecurityProfile.REMOTE, scope=_remote_scope()):
        decision = route_tool(
            "get_current_time", {"host": "example.org"}, profile=SecurityProfile.REMOTE
        )
    assert not decision.allowed


def test_remote_capability_rejection_precedes_confirmation_and_runner(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        tools, "_ensure_loaded", lambda: calls.append("plugin_load") or None
    )
    monkeypatch.setitem(
        tools._RUNNERS,
        "delete_file",
        lambda _args: calls.append("runner") or "bad",
    )
    monkeypatch.setattr(
        tools,
        "_CONFIRMATION_CALLBACK",
        lambda *_args: calls.append("confirmation") or True,
    )

    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=True, scope=_remote_scope()
    ):
        result = tools.run_tool("delete_file", {"filename": str(tmp_path / "x")})

    assert "no compliant sandbox backend" in result
    assert calls == []


def test_remote_parallel_dispatch_cannot_bypass_broker(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        tools, "_ensure_loaded", lambda: calls.append("plugin_load") or None
    )
    monkeypatch.setitem(
        tools._RUNNERS, "get_env", lambda _args: calls.append("runner") or "bad"
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "get_env", False)

    with execution_profile(
        SecurityProfile.REMOTE, sandbox_enabled=False, scope=_remote_scope()
    ):
        result = tools.run_tools_parallel([("get_env", {"name": "PATH"})])

    assert len(result) == 1
    assert "execution denied" in result[0][2]
    assert calls == []


def test_policy_change_during_confirmation_blocks_runner(monkeypatch, tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(policy_path))
    calls: list[str] = []
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setitem(
        tools._RUNNERS,
        "delete_file",
        lambda _args: calls.append("runner") or "bad",
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "delete_file", False)

    def approve_then_revoke(*_args):
        policy_path.write_text('{"tools":{"delete_file":"deny"}}', encoding="utf-8")
        return True

    monkeypatch.setattr(tools, "_CONFIRMATION_CALLBACK", approve_then_revoke)
    result = tools.run_tool("delete_file", {"filename": str(tmp_path / "gone")})

    assert "policy changed" in result
    assert calls == []


def test_confirmation_cannot_change_approved_arguments(monkeypatch, tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(policy_path))
    calls: list[str] = []
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setitem(
        tools._RUNNERS,
        "delete_file",
        lambda _args: calls.append("runner") or "bad",
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "delete_file", False)

    def mutate_and_approve(_name, args, _policy):
        args["filename"] = "redirected-target"
        return True

    monkeypatch.setattr(tools, "_CONFIRMATION_CALLBACK", mutate_and_approve)
    result = tools.run_tool("delete_file", {"filename": str(tmp_path / "original")})

    assert result == "[tool policy] confirmation invalidated"
    assert calls == []


def test_cancel_contract_terminates_lease_if_execution_stop_is_unconfirmed():
    class FakeBackend:
        def __init__(self):
            self.cancel_call = None
            self.terminated = []

        def cancel_execution(self, execution_handle, *, reason):
            self.cancel_call = (execution_handle, reason)
            return CancellationResult(execution_stopped=False)

        def terminate(self, lease_handle):
            self.terminated.append(lease_handle)

    backend = FakeBackend()
    result = cancel_execution_safely(
        backend, "execution-1", "lease-1", reason="user stop"
    )

    assert backend.cancel_call == ("execution-1", "user stop")
    assert backend.terminated == ["lease-1"]
    assert not result.safe_to_reuse
    assert result.lease_terminated
