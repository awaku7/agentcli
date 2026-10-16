"""Regression checks for the shared risky-operation confirmation path."""

from __future__ import annotations

from uagent.runtime.identity_context import TurnContext, bind_turn_context
from uagent.tools.tool_confirmation import confirm_operation, dispatched_tool
from uagent.tools.tool_policy import (
    default_confirmation_callback,
    policy_for,
    reset_confirmation_grants,
)


def test_confirm_operation_uses_host_callback_and_never_raw_input(monkeypatch):
    from uagent import tools

    asked = []
    monkeypatch.setattr(
        tools,
        "_CONFIRMATION_CALLBACK",
        lambda name, args, policy: asked.append((name, args, policy)) or False,
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda *_args: (_ for _ in ()).throw(AssertionError("raw input called")),
    )
    with dispatched_tool("bash_exec", approved=False):
        assert not confirm_operation("risk", tool_name="bash_exec")
    assert asked[0][0] == "bash_exec"
    assert asked[0][1] == {"details": "risk"}
    assert asked[0][2].requires_confirmation

    with dispatched_tool("bash_exec", approved=True):
        assert confirm_operation("risk", tool_name="bash_exec")
        assert not confirm_operation("risk", tool_name="zip_ops")
    assert len(asked) == 2


def test_confirm_operation_denies_unavailable_or_failing_callback(monkeypatch):
    from uagent import tools
    from uagent.tools import tool_policy

    monkeypatch.setattr(tools, "_CONFIRMATION_CALLBACK", None)
    monkeypatch.setattr(tool_policy, "default_confirmation_callback", lambda *_: False)
    assert not confirm_operation("risk", tool_name="zip_ops")
    monkeypatch.setattr(
        tools,
        "_CONFIRMATION_CALLBACK",
        lambda *_: (_ for _ in ()).throw(RuntimeError("no frontend")),
    )
    assert not confirm_operation("risk", tool_name="zip_ops")


def test_all_confirmation_grants_are_bound_to_room_and_tool(monkeypatch):
    from uagent.tools import human_ask_tool

    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    asks = []
    replies = iter(["all", "yes", "no"])

    def _reply(_args):
        asks.append(_args)
        answer = next(replies)
        return '{"user_reply": "' + answer + '", "cancelled": false}'

    monkeypatch.setattr(human_ask_tool, "run_tool", _reply)
    reset_confirmation_grants()
    first = TurnContext(
        principal_id="principal",
        room_id="room-one",
        project_id="project",
        session_id="session-one",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    second = TurnContext(
        principal_id="principal",
        room_id="room-two",
        project_id="project",
        session_id="session-two",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    try:
        with bind_turn_context(first):
            assert default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
            assert default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
            assert default_confirmation_callback("zip_ops", {}, policy_for("zip_ops"))
        assert len(asks) == 2
        with bind_turn_context(second):
            assert not default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
        assert len(asks) == 3
    finally:
        reset_confirmation_grants()


def test_command_guard_uses_dispatch_approval_without_reasking(monkeypatch):
    from uagent.tools.safe_exec_ops import ExecDecision, confirm_if_needed

    decision = ExecDecision(True, "risk", require_confirm=True, confirm_message="ask")
    from uagent import tools

    seen = []
    monkeypatch.setattr(
        tools,
        "_CONFIRMATION_CALLBACK",
        lambda *_: seen.append(True) or False,
    )
    with dispatched_tool("bash_exec", approved=True):
        assert confirm_if_needed(decision) is None
    assert not seen

    with dispatched_tool("bash_exec", approved=False):
        assert confirm_if_needed(decision) is not None
    assert len(seen) == 1


def test_directory_delete_gets_only_one_confirmation(monkeypatch, tmp_path):
    from uagent.tools import safe_file_ops

    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "data.txt").write_text("data", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        safe_file_ops,
        "_ask_user_confirm",
        lambda path, operation: calls.append((path, operation)) or True,
    )
    monkeypatch.setattr(safe_file_ops, "_is_trigger_path", lambda _path: True)
    safe_file_ops.safe_delete_path(str(folder))
    assert calls == [(str(folder), "delete_dir")]
    assert not folder.exists()
