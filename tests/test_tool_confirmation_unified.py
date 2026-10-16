"""Regression checks for the shared risky-operation confirmation path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent.runtime.identity_context import TurnContext, bind_turn_context
from uagent.tools.tool_confirmation import confirm_operation, dispatched_tool
from uagent.tools.tool_policy import (
    default_confirmation_callback,
    policy_for,
    reset_confirmation_grants,
)

_LOCALE_DATA = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "src"
        / "uagent"
        / "tools"
        / "human_ask_tool.json"
    ).read_text(encoding="utf-8")
)
_CONFIRM_LANGUAGES = ["en", *sorted(_LOCALE_DATA)]


@pytest.mark.parametrize("language", _CONFIRM_LANGUAGES)
def test_all_38_languages_have_exact_yes_no_all_answers(monkeypatch, language):
    from uagent.tools import tool_policy

    monkeypatch.setenv("UAGENT_LANG", language)
    assert len(_CONFIRM_LANGUAGES) == 38
    labels = _LOCALE_DATA.get(language)
    if language == "en":
        expected = ("yes", "no", "all")
    else:
        assert labels is not None
        expected = tuple(
            labels["confirm.reply_" + name] for name in ("yes", "no", "all")
        )
    assert len(set(expected)) == 3
    assert all(label.strip() for label in expected)
    assert (
        tuple(
            tool_policy._tool_("confirm.reply_" + name, default=name)
            for name in ("yes", "no", "all")
        )
        == expected
    )
    assert tool_policy._confirmation_reply_kind(expected[0]) == "yes"
    assert tool_policy._confirmation_reply_kind(expected[1]) == "deny"
    assert tool_policy._confirmation_reply_kind(expected[2]) == "all"
    assert tool_policy._confirmation_reply_kind("unexpected answer") == "deny"
    if labels is not None:
        assert expected[2] in labels["ui.all_yes"]


@pytest.mark.parametrize(
    "language,reply,expected",
    [
        ("ja", "全て", "all"),
        ("ja", "いいえ", "deny"),
        ("ja", "はい", "yes"),
        ("fr", "OUI", "yes"),
        ("es", "SI", "deny"),
        ("es", "SI" + chr(0x301), "yes"),
        ("zh_CN", "全部", "all"),
        ("ko", "아니요", "deny"),
    ],
)
def test_confirmation_reply_normalization_is_strict(
    monkeypatch, language, reply, expected
):
    from uagent.tools import tool_policy

    monkeypatch.setenv("UAGENT_LANG", language)
    assert tool_policy._confirmation_reply_kind(reply) == expected


@pytest.mark.parametrize(
    "language,approval",
    [("ja", "全て"), ("fr", "tous"), ("ko", "모두"), ("ar", "الكل")],
)
def test_localized_all_approval_is_shown_and_scoped(monkeypatch, language, approval):
    from uagent import core
    from uagent.tools import tool_policy

    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    monkeypatch.setenv("UAGENT_LANG", language)
    seen = []
    monkeypatch.setattr(
        "uagent.tools.human_ask_tool.run_tool",
        lambda req: seen.append(req)
        or json.dumps({"user_reply": approval, "cancelled": False}),
    )
    turn = TurnContext(
        principal_id="local-user",
        room_id="",
        project_id="project",
        session_id="session-" + language,
        entry_point="cli",
        authenticated=True,
        authn_kind="local",
    )
    tool_policy.reset_confirmation_grants()
    try:
        with bind_turn_context(turn):
            assert tool_policy.default_confirmation_callback(
                "delete_file", {}, tool_policy.policy_for("delete_file")
            )
            assert tool_policy.default_confirmation_callback(
                "delete_file", {}, tool_policy.policy_for("delete_file")
            )
        assert len(seen) == 1
        assert approval in seen[0]["message"]
        assert seen[0]["confirmation"] is True
        assert seen[0]["_confirmation_hint_in_message"] is True
    finally:
        tool_policy.reset_confirmation_grants()


@pytest.mark.parametrize(
    "answer,deleted",
    [("はい", True), ("いいえ", False), ("全て", False)],
)
def test_cli_rm_reuses_one_localized_approval(
    monkeypatch, repo_tmp_path, answer, deleted
):
    from uagent import util_cmd_files
    from uagent.tools import human_ask_tool

    monkeypatch.setenv("UAGENT_LANG", "ja")
    target = repo_tmp_path / "single_confirmation.tmp"
    target.write_text("data", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        human_ask_tool,
        "run_tool",
        lambda args: calls.append(args)
        or json.dumps({"user_reply": answer, "cancelled": False}),
    )

    assert util_cmd_files._handle_cmd_rm(str(target), tr=None)
    assert len(calls) == 1
    assert target.exists() is not deleted


def test_web_confirmation_respects_room_locale_over_server(monkeypatch):
    from uagent import core, tools
    from uagent.i18n import reset_contextvar_locale, set_contextvar_locale
    from uagent.tools import tool_policy

    monkeypatch.setenv("UAGENT_LANG", "ja")
    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    monkeypatch.setattr(core, "_is_web", True, raising=False)
    prompts = []

    def web_ask(name, args):
        assert name == "human_ask"
        prompts.append(args)
        return json.dumps({"user_reply": "tous", "cancelled": False})

    monkeypatch.setattr(tools, "run_tool", web_ask)
    room_turn = TurnContext(
        principal_id="p",
        room_id="room-fr",
        project_id="project",
        session_id="s",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    tool_policy.reset_confirmation_grants()
    token = set_contextvar_locale("fr")
    try:
        with bind_turn_context(room_turn):
            assert tool_policy.default_confirmation_callback(
                "delete_file", {}, tool_policy.policy_for("delete_file")
            )
            assert tool_policy.default_confirmation_callback(
                "delete_file", {}, tool_policy.policy_for("delete_file")
            )
        assert len(prompts) == 1
        assert "tous" in prompts[0]["message"]
        assert "Autoriser" in prompts[0]["message"]
    finally:
        reset_contextvar_locale(token)
        tool_policy.reset_confirmation_grants()


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
    from uagent import tools

    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    asks = []
    replies = iter(["all", "yes", "no"])

    def _reply(_args):
        asks.append(_args)
        answer = next(replies)
        return '{"user_reply": "' + answer + '", "cancelled": false}'

    monkeypatch.setattr(tools, "run_tool", lambda _name, args: _reply(args))
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


def test_absconfirm_ignores_cached_all_grant(monkeypatch):
    from uagent import tools
    from uagent.tools import tool_policy

    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    prompts = []
    answers = iter(["all", "no"])

    def _reply(_args):
        prompts.append(_args)
        return '{"user_reply": "' + next(answers) + '", "cancelled": false}'

    monkeypatch.setattr(tools, "run_tool", lambda _name, args: _reply(args))
    monkeypatch.setattr(
        tool_policy, "_absolute_confirmation_required", lambda *_args: True
    )
    turn = TurnContext(
        principal_id="p",
        room_id="room",
        project_id="project",
        session_id="session",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    reset_confirmation_grants()
    try:
        with bind_turn_context(turn):
            assert default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
            assert not default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
        assert len(prompts) == 2
    finally:
        reset_confirmation_grants()


def test_injected_autopilot_absconfirm_never_caches_all(monkeypatch):
    from types import SimpleNamespace

    from uagent import core, tools
    from uagent.tools import tool_policy

    monkeypatch.setenv("UAGENT_INJECT_MODE", "1")
    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    monkeypatch.setattr(core, "auto_pilot_active", True, raising=False)
    calls = []
    policy = SimpleNamespace(
        inject_requires_confirmation=lambda *_args: False,
        auto_pilot_requires_confirmation=lambda *_args: True,
    )
    monkeypatch.setattr(
        "uagent.tools.enterprise_policy.get_enterprise_policy", lambda: policy
    )
    monkeypatch.setattr(
        tools,
        "run_tool",
        lambda _name, args: calls.append(args)
        or '{"user_reply": "all", "cancelled": false}',
    )
    turn = TurnContext(
        principal_id="p",
        room_id="room",
        project_id="project",
        session_id="session",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    reset_confirmation_grants()
    try:
        with bind_turn_context(turn):
            assert tool_policy._absolute_confirmation_required("delete_file", {})
            assert default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
            assert default_confirmation_callback(
                "delete_file", {}, policy_for("delete_file")
            )
            # The model can answer "all", but mandatory auto-pilot confirmation
            # must still be performed on every dangerous tool call.
            assert len(calls) == 2
            assert tool_policy._ALLOW_ALL_TOOLS == set()
    finally:
        reset_confirmation_grants()


def test_injected_absconfirm_still_applies_without_autopilot(monkeypatch):
    from types import SimpleNamespace

    from uagent import core
    from uagent.tools import tool_policy

    monkeypatch.setenv("UAGENT_INJECT_MODE", "1")
    monkeypatch.setattr(core, "auto_pilot_active", False, raising=False)
    policy = SimpleNamespace(
        inject_requires_confirmation=lambda *_args: True,
        auto_pilot_requires_confirmation=lambda *_args: False,
    )
    monkeypatch.setattr(
        "uagent.tools.enterprise_policy.get_enterprise_policy", lambda: policy
    )
    assert tool_policy._absolute_confirmation_required("delete_file", {})


def test_web_fallback_confirmation_uses_room_tool_wrapper(monkeypatch):
    from uagent import core, tools
    from uagent.tools import human_ask_tool

    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    calls = []

    def web_ask(name, args):
        calls.append((name, args))
        return '{"user_reply": "yes", "cancelled": false}'

    monkeypatch.setattr(tools, "run_tool", web_ask)
    monkeypatch.setattr(
        human_ask_tool,
        "run_tool",
        lambda _args: (_ for _ in ()).throw(
            AssertionError("Web must not call CLI human_ask")
        ),
    )
    turn = TurnContext(
        principal_id="p",
        room_id="web-room",
        project_id="project",
        session_id="session",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    with bind_turn_context(turn):
        assert default_confirmation_callback(
            "bash_exec", {"command": "echo hi"}, policy_for("bash_exec")
        )
    assert len(calls) == 1
    assert calls[0][0] == "human_ask"
    assert calls[0][1]["_auto_pilot_tool"] == "bash_exec"


def test_web_fallback_without_bound_turn_fails_closed(monkeypatch):
    from uagent import core, tools
    from uagent.tools import human_ask_tool

    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.setattr(
        tools,
        "run_tool",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("missing Web turn must not prompt")
        ),
    )
    monkeypatch.setattr(
        human_ask_tool,
        "run_tool",
        lambda _args: (_ for _ in ()).throw(AssertionError("must not use CLI queue")),
    )
    assert not default_confirmation_callback(
        "bash_exec", {"command": "echo hi"}, policy_for("bash_exec")
    )


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
