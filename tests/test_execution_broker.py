from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent import hooks_engine, tools
from uagent.a2a.engine import run_once_uag
from uagent.llm_flow_helpers import _execute_tool_calls
from uagent.runtime.identity_context import IdentityContext, TurnContext
from uagent.runtime.execution_broker import (
    CancellationResult,
    ExecutionClass,
    IsolationLevel,
    SandboxCapabilities,
    SandboxCapability,
    SecurityProfile,
    cancel_execution_safely,
    computer_use_allowed,
    is_computer_use_tool_spec,
    TrustedSandboxScope,
    classify_tool,
    execution_profile,
    is_trusted_local_web,
    route_tool,
    trusted_web_scope,
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


def test_remote_web_scope_requires_nonlocal_authenticated_identity():
    local_identity = IdentityContext("local", True, "local")
    local_turn = TurnContext.from_identity(
        local_identity,
        entry_point="web",
        room_id="room-1",
        project_id="project-1",
    )
    assert trusted_web_scope(local_turn, "room-1") is None

    remote_identity = IdentityContext("alice", True, "oidc")
    remote_turn = TurnContext.from_identity(
        remote_identity,
        entry_point="web",
        room_id="room-1",
        project_id="project-1",
    )
    assert trusted_web_scope(remote_turn, "room-1") is not None


def test_concurrent_a2a_broker_authorization_uses_task_local_scope(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from uagent import core
    import uagent.uagent_llm as uagent_llm
    import uagent.providers.util_providers as util_providers
    import uagent.util_tools as util_tools
    from uagent.runtime.execution import lifecycle_execution
    from uagent.runtime.execution_broker import current_scope
    from uagent.runtime import session_store

    barrier = Barrier(2)
    observed: dict[str, str] = {}
    monkeypatch.setattr(core, "task_id", "sentinel", raising=False)
    monkeypatch.setattr(
        util_providers, "make_client", lambda _core: ("openai", object(), "model")
    )
    monkeypatch.setattr(
        session_store,
        "attach_opt_in_session_store",
        lambda *_args, **_kwargs: (None, "a2a-test-session"),
    )
    monkeypatch.setattr(
        session_store, "detach_opt_in_session_store", lambda *_args: None
    )
    monkeypatch.setattr(util_tools, "build_initial_messages", lambda **_kwargs: [])
    monkeypatch.setattr(core, "log_message", lambda _message: None)
    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setitem(tools._RUNNERS, "get_current_time", lambda _args: "unused")
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "get_current_time", False)

    def run_rounds(_provider, _client, _model, messages, **_kwargs):
        barrier.wait(timeout=10)
        scope = current_scope()
        assert scope is not None
        result = tools.run_tool("get_current_time", {})
        observed[scope.scope_id] = result
        messages.append({"role": "assistant", "content": "done"})

    monkeypatch.setattr(uagent_llm, "run_llm_rounds", run_rounds)

    def run_task(task_id: str):
        with lifecycle_execution():
            return run_once_uag(user_text=task_id, task_id=task_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run_task, ("task-a", "task-b")))

    assert all(error is None for _message, error in results)
    assert set(observed) == {"task-a", "task-b"}
    assert all("[get_current_time]" in result for result in observed.values()), observed
    assert core.task_id == "sentinel"


def test_a2a_requires_server_task_id_before_starting_run():
    with pytest.raises(ValueError, match="task_id is required"):
        run_once_uag(user_text="hello", task_id="")


def test_remote_call_without_trusted_scope_is_denied():
    decision = route_tool(
        "get_current_time", {}, profile=SecurityProfile.REMOTE, known_tool=True
    )
    assert not decision.allowed
    assert decision.reason == "trusted remote scope is required"


def test_remote_brokered_route_does_not_require_runner_registration():
    with execution_profile(SecurityProfile.REMOTE, scope=_remote_scope()):
        decision = route_tool(
            "get_current_time", {}, profile=SecurityProfile.REMOTE, known_tool=False
        )
    assert decision.allowed
    assert decision.execution_class is ExecutionClass.BROKERED


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
    assert still_unavailable.allowed
    assert still_unavailable.reason == ""


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
        SecurityProfile.REMOTE,
        sandbox_enabled=False,
        scope=_remote_scope(),
        authorization_check=lambda: True,
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
    # Remote fixed broker operations must work even when host tool plugins
    # have never been loaded and the generic runner registry is empty.
    monkeypatch.delitem(tools._RUNNERS, "get_current_time", raising=False)
    monkeypatch.delitem(
        tools._LAZY_TOOL_NAME_TO_MODULE, "get_current_time", raising=False
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "get_current_time", False)

    with execution_profile(
        SecurityProfile.REMOTE,
        sandbox_enabled=False,
        scope=_remote_scope(),
        authorization_check=lambda: True,
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
        SecurityProfile.REMOTE,
        sandbox_enabled=True,
        scope=_remote_scope(),
        authorization_check=lambda: True,
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
        SecurityProfile.REMOTE,
        sandbox_enabled=False,
        scope=_remote_scope(),
        authorization_check=lambda: True,
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


def test_tool_dispatch_revalidates_live_authorization_after_confirmation(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    calls = []
    authorization_checks = []
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setitem(
        tools._RUNNERS,
        "delete_file",
        lambda _args: calls.append("runner") or "unexpected",
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "delete_file", False)
    monkeypatch.setattr(tools, "_CONFIRMATION_CALLBACK", lambda *_args: True)

    def revalidate_room_membership():
        authorization_checks.append("checked")
        # Model membership revocation while the confirmation UI is open.
        return len(authorization_checks) == 1

    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED,
        authorization_check=revalidate_room_membership,
    ):
        result = tools.run_tool("delete_file", {"filename": str(tmp_path / "x")})

    assert "authorization" in result
    assert len(authorization_checks) == 2
    assert calls == []


def test_computer_use_is_only_available_to_local_trusted_sandbox_off():
    computer_spec = {
        "type": "function",
        "function": {"name": "computer", "parameters": {"type": "object"}},
    }
    assert is_computer_use_tool_spec(computer_spec)
    assert is_computer_use_tool_spec({"computer_use": {"environment": "browser"}})
    with execution_profile(SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=False):
        assert computer_use_allowed()
    with execution_profile(SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True):
        assert not computer_use_allowed()
    with execution_profile(SecurityProfile.REMOTE, scope=_remote_scope()):
        assert not computer_use_allowed()


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


def test_remote_user_prompt_submit_hook_cannot_spawn_host_command(
    monkeypatch, tmp_path
):
    from uagent.web_impl.agent_worker import _web_turn_execution_context
    from uagent.web_impl.rooms import WebRoom, web_manager

    calls = []
    monkeypatch.setattr(
        hooks_engine.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)
    hooks = {
        "UserPromptSubmit": [
            {"type": "command", "command": "echo host-hook-must-not-run"}
        ]
    }
    identity = IdentityContext("alice", True, "oidc")
    turn = TurnContext.from_identity(
        identity,
        entry_point="web",
        room_id="remote-hook-room",
        project_id="project-1",
        session_id="session-1",
    )
    room = WebRoom("remote-hook-room")
    with _web_turn_execution_context(room, turn, identity, str(tmp_path)):
        results = hooks_engine.fire_user_prompt_submit("hello", hooks=hooks)

    assert calls == []
    assert len(results) == 1
    assert not results[0]["ok"]
    assert "remote" in results[0]["error"]


def test_remote_human_ask_response_is_bound_to_initiating_principal(monkeypatch):
    from uagent.web_impl.rooms import WebRoom, web_manager
    from uagent.web_impl.routes_ws import _human_ask_response_is_authorized

    room = WebRoom("shared-room")
    room._human_ask_expected_principal_id = "alice"
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)

    assert _human_ask_response_is_authorized(room, "alice")
    assert not _human_ask_response_is_authorized(room, "bob")
    room._human_ask_expected_principal_id = ""
    assert not _human_ask_response_is_authorized(room, "alice")


def test_web_human_ask_revalidates_current_room_principal(monkeypatch):
    from uagent.runtime.identity_context import (
        IdentityContext,
        TurnContext,
        call_with_turn_context,
    )
    from uagent.runtime.execution_broker import trusted_web_scope
    from uagent.web_impl.init import _remote_human_ask_authorized
    from uagent.web_impl.rooms import WebRoom, web_manager

    identity = IdentityContext("alice", True, "oidc")
    turn = TurnContext.from_identity(
        identity,
        entry_point="web",
        room_id="room-1",
        project_id="project-1",
        session_id="session-1",
    )
    scope = trusted_web_scope(turn, turn.room_id)
    assert scope is not None
    room = WebRoom(turn.room_id)

    class Connection:
        def __init__(self):
            self.identity = identity
            self.authorized = True

        def validate_authentication_configuration(self):
            return None

        def validate_room_access(self, *, touch_activity=True):
            if not self.authorized:
                raise PermissionError("membership revoked")

    connection = Connection()
    room._connection_contexts["connection-1"] = connection
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)

    with execution_profile(SecurityProfile.REMOTE, scope=scope):
        assert call_with_turn_context(
            turn,
            _remote_human_ask_authorized,
            room,
            identity_context=identity,
        )
        connection.authorized = False
        assert not call_with_turn_context(
            turn,
            _remote_human_ask_authorized,
            room,
            identity_context=identity,
        )


def test_web_turn_profile_blocks_user_prompt_submit_host_hook(monkeypatch):
    from uagent.web_impl.agent_worker import _web_turn_execution_context
    from uagent.web_impl.rooms import WebRoom, web_manager

    calls = []
    monkeypatch.setattr(
        hooks_engine.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)
    room = WebRoom("room-1")
    identity = SimpleNamespace(
        authenticated=True,
        principal_id="alice",
        authn_kind="oidc",
    )
    turn = SimpleNamespace(
        authenticated=True,
        entry_point="web",
        room_id="room-1",
        principal_id="alice",
        project_id="project-1",
        authn_kind="oidc",
    )
    hooks = {
        "UserPromptSubmit": [
            {"type": "command", "command": "echo host-hook-must-not-run"}
        ]
    }

    with _web_turn_execution_context(room, turn, identity, "project-path"):
        results = hooks_engine.fire_user_prompt_submit("hello", hooks=hooks)

    assert calls == []
    assert len(results) == 1
    assert not results[0]["ok"]
    assert "remote" in results[0]["error"]


def test_remote_parallel_safety_check_does_not_load_plugins(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tools, "_ensure_loaded", lambda: calls.append("plugin_load") or None
    )
    with execution_profile(
        SecurityProfile.REMOTE,
        scope=_remote_scope(),
        authorization_check=lambda: True,
    ):
        assert not tools.is_parallel_safe("unregistered_plugin_tool", {})
    assert calls == []


def test_llm_tool_loop_rejects_unregistered_remote_tool_before_plugin_load(
    monkeypatch,
):
    plugin_loads = []

    def record_plugin_load():
        plugin_loads.append("load")

    monkeypatch.setattr(tools, "_ensure_loaded", record_plugin_load)
    core = SimpleNamespace(
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda *args: None,
    )
    tool_calls = [
        {
            "id": "unknown-remote-tool",
            "type": "function",
            "function": {
                "name": "unregistered_plugin_tool",
                "arguments": "{}",
            },
        }
    ]
    messages = []

    with execution_profile(
        SecurityProfile.REMOTE,
        scope=_remote_scope(),
        authorization_check=lambda: True,
    ):
        _execute_tool_calls(
            tool_calls_list=tool_calls,
            messages=messages,
            core=core,
            cache_mgr=SimpleNamespace(record_file_access=lambda *_args: None),
        )

    assert plugin_loads == []
    assert (
        "unknown" in messages[-1]["content"]
        or "execution denied" in messages[-1]["content"]
    )


def test_web_turn_authorization_rechecks_live_room_membership(monkeypatch, tmp_path):
    from uagent.web_impl import connection_identity
    from uagent.web_impl.agent_worker import _web_turn_authorization_valid
    from uagent.web_impl.rooms import WebRoom

    identity = IdentityContext("alice", True, "oidc")
    turn = TurnContext.from_identity(
        identity,
        entry_point="web",
        room_id="room-1",
        project_id="project-1",
        session_id="session-1",
        server_bound_project=True,
    )
    room = WebRoom("room-1")
    membership_active = True

    def require_room_access(_identity, _room_id, *, touch_activity=True):
        if not membership_active:
            raise PermissionError("membership revoked")
        return "project-1", False

    monkeypatch.setattr(connection_identity, "require_room_access", require_room_access)

    assert _web_turn_authorization_valid(room, turn, identity, str(tmp_path))
    membership_active = False
    assert not _web_turn_authorization_valid(room, turn, identity, str(tmp_path))


def test_web_broker_operation_is_rejected_when_room_membership_is_revoked(
    monkeypatch, tmp_path
):
    from uagent.web_impl import connection_identity
    from uagent.web_impl.agent_worker import _web_turn_authorization_valid
    from uagent.web_impl.rooms import WebRoom

    monkeypatch.setenv("UAGENT_POLICY_FILE", str(tmp_path / "policy.json"))
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    identity = IdentityContext("alice", True, "oidc")
    turn = TurnContext.from_identity(
        identity,
        entry_point="web",
        room_id="room-1",
        project_id="project-1",
        session_id="session-1",
        server_bound_project=True,
    )
    room = WebRoom("room-1")
    membership_active = True
    calls = []
    monkeypatch.setattr(
        tools,
        "_ensure_loaded",
        lambda: calls.append("runner registry loaded"),
    )
    monkeypatch.setitem(
        tools._RUNNERS, "get_current_time", lambda _args: "should not execute"
    )
    monkeypatch.setitem(tools._TOOL_TRACE_FLAGS, "get_current_time", False)

    def require_room_access(_identity, _room_id, *, touch_activity=True):
        if not membership_active:
            raise PermissionError("membership revoked")
        return "project-1", False

    monkeypatch.setattr(connection_identity, "require_room_access", require_room_access)
    scope = trusted_web_scope(turn, room.room_id)
    assert scope is not None

    def authorize():
        return _web_turn_authorization_valid(room, turn, identity, str(tmp_path))

    # The confirmation/execution boundary rechecks the live membership; revoke
    # it between the first admission check and the final pre-execution check.
    checks = []

    def revoke_between_checks():
        nonlocal membership_active
        checks.append(True)
        if len(checks) == 2:
            membership_active = False
        return authorize()

    with execution_profile(
        SecurityProfile.REMOTE,
        scope=scope,
        authorization_check=revoke_between_checks,
    ):
        result = tools.run_tool("get_current_time", {})

    assert "authorization" in result
    assert checks == [True, True]
    assert calls == []


def test_computer_use_tool_specs_are_filtered_for_remote_and_sandbox_profiles(
    monkeypatch,
):
    computer = {
        "type": "function",
        "function": {"name": "computer", "parameters": {"type": "object"}},
    }
    ordinary = {
        "type": "function",
        "function": {"name": "calculator", "parameters": {"type": "object"}},
    }
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(tools, "TOOL_SPECS", [computer, ordinary])
    monkeypatch.setattr(tools, "_TOOL_SPECS_DIRTY", True)
    monkeypatch.setattr(tools, "_TOOL_SPECS_CACHE", None)
    monkeypatch.setattr(tools, "_TOOL_SPECS_CACHE_EMBEDDED", None)
    monkeypatch.setattr(tools, "_ANALYZE_IMAGE_HIDDEN", None)

    with execution_profile(SecurityProfile.REMOTE, scope=_remote_scope()):
        remote_specs = tools.get_tool_specs()
    assert [spec["function"]["name"] for spec in remote_specs] == ["calculator"]

    with execution_profile(SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True):
        sandbox_specs = tools.get_tool_specs()
    assert {spec["function"]["name"] for spec in sandbox_specs} == {
        "create_file",
        "file_exists",
        "read_file",
        "python_exec",
    }


@pytest.mark.parametrize(
    ("profile", "sandbox_enabled"),
    [
        (SecurityProfile.REMOTE, False),
        (SecurityProfile.REMOTE, True),
        (SecurityProfile.LOCAL_TRUSTED, True),
    ],
)
def test_computer_use_alias_is_denied_before_tool_loading(
    monkeypatch, profile, sandbox_enabled
):
    loads = []
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: loads.append(True))
    scope = _remote_scope() if profile is SecurityProfile.REMOTE else None

    with execution_profile(profile, sandbox_enabled=sandbox_enabled, scope=scope):
        result = tools.run_tool("computer_use", {"action": "screenshot"})

    assert "Computer Use is disabled" in result
    assert loads == []
