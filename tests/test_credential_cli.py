from __future__ import annotations

import json

from uagent.auth import InMemoryCredentialStore
from uagent.util_cmd_credentials import handle_credential_command


class _Core:
    pass


def _translate(text: str, **_: object) -> str:
    return text


def test_credential_command_set_get_remove(monkeypatch, capsys) -> None:
    import uagent.util_cmd_credentials as commands

    store = InMemoryCredentialStore()
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        "uagent.tools.run_tool",
        lambda name, args: (
            json.dumps({"user_reply": "secret-value"})
            if args.get("is_password")
            else json.dumps({"user_reply": "y"})
        ),
    )
    core = _Core()

    handle_credential_command("set demo api_key", core=core, tr=_translate)
    assert store.get("demo") is not None

    handle_credential_command("get demo", core=core, tr=_translate)
    output = capsys.readouterr().out
    assert "name: demo" in output
    assert "kind: api_key" in output
    assert "secret-value" not in output

    handle_credential_command("remove demo", core=core, tr=_translate)
    assert store.get("demo") is None


def _git_scope():
    from uagent.runtime.execution_broker import TrustedSandboxScope

    return TrustedSandboxScope(
        "cli",
        "os-uid:42",
        "project",
        "cli-session",
        "runtime-1",
        settings_session_id="session-a",
    )


def test_git_credential_one_step_setup_and_status(monkeypatch, capsys) -> None:
    import uagent.util_cmd_credentials as commands
    from uagent.runtime.sandbox_git_credentials import (
        effective_git_credential_alias,
        resolve_git_https_token_for_host,
        selected_git_https_host_for_scope,
    )

    store = InMemoryCredentialStore()
    scope = _git_scope()
    core = _Core()
    core._sandbox_scope = scope
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        commands.sys,
        "stdin",
        type("TTY", (), {"isatty": lambda self: True})(),
    )
    monkeypatch.setattr(commands.getpass, "getpass", lambda prompt: "PRIVATE_TOKEN")

    handle_credential_command("git github.com", core=core, tr=_translate)
    handle_credential_command("git status", core=core, tr=_translate)

    assert effective_git_credential_alias(scope, store=store) == "github.com"
    assert selected_git_https_host_for_scope(scope, store=store) == "github.com"
    assert resolve_git_https_token_for_host(scope, store=store) == "PRIVATE_TOKEN"
    output = capsys.readouterr().out
    assert "github.com" in output
    assert "PRIVATE_TOKEN" not in output


def test_git_setup_rejects_invalid_host_without_secret_prompt(
    monkeypatch, capsys
) -> None:
    import uagent.util_cmd_credentials as commands

    store = InMemoryCredentialStore()
    core = _Core()
    core._sandbox_scope = _git_scope()
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        commands.getpass,
        "getpass",
        lambda prompt: (_ for _ in ()).throw(AssertionError("must not prompt")),
    )

    handle_credential_command(
        "git https://github.com/owner/repo", core=core, tr=_translate
    )
    assert "Invalid Git host" in capsys.readouterr().out
    assert not store.list_names()


def test_git_setup_preserves_existing_session_override(monkeypatch, capsys) -> None:
    import uagent.util_cmd_credentials as commands
    from uagent.runtime.sandbox_git_credentials import (
        effective_git_credential_alias,
        save_git_https_token,
        select_git_credential,
    )

    store = InMemoryCredentialStore()
    scope = _git_scope()
    core = _Core()
    core._sandbox_scope = scope
    save_git_https_token(
        scope, "session", "SESSION_TOKEN", store=store, remote_host="gitlab.com"
    )
    select_git_credential(scope, "session", "session", store=store)
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        commands.sys,
        "stdin",
        type("TTY", (), {"isatty": lambda self: True})(),
    )
    monkeypatch.setattr(commands.getpass, "getpass", lambda prompt: "USER_TOKEN")

    handle_credential_command("git github.com", core=core, tr=_translate)

    assert effective_git_credential_alias(scope, store=store) == "session"
    assert "separate override" in capsys.readouterr().out


def test_git_credential_remove_revokes_only_selected_alias(
    monkeypatch, capsys
) -> None:
    import uagent.util_cmd_credentials as commands
    from uagent.runtime.sandbox_git_credentials import (
        effective_git_credential_alias,
        save_git_https_token,
        select_git_credential,
    )

    store = InMemoryCredentialStore()
    scope = _git_scope()
    core = _Core()
    core._sandbox_scope = scope
    save_git_https_token(
        scope, "user", "USER_TOKEN", store=store, remote_host="github.com"
    )
    save_git_https_token(
        scope, "session", "SESSION_TOKEN", store=store, remote_host="gitlab.com"
    )
    select_git_credential(scope, "user", "user", store=store)
    select_git_credential(scope, "session", "session", store=store)
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        commands.sys,
        "stdin",
        type("TTY", (), {"isatty": lambda self: True})(),
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    handle_credential_command("git remove", core=core, tr=_translate)

    assert effective_git_credential_alias(scope, store=store) == "user"
    from uagent.runtime.sandbox_git_credentials import _token_key

    assert store.get(_token_key(scope, "session")) is None
    assert store.get(_token_key(scope, "user")) is not None
    assert "revoked" in capsys.readouterr().out


def test_git_credential_requires_tty_and_trusted_cli_scope(monkeypatch, capsys) -> None:
    import uagent.util_cmd_credentials as commands
    from uagent.runtime.execution_broker import TrustedSandboxScope

    store = InMemoryCredentialStore()
    core = _Core()
    core._sandbox_scope = _git_scope()
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        commands.sys,
        "stdin",
        type("Pipe", (), {"isatty": lambda self: False})(),
    )
    handle_credential_command("git github.com", core=core, tr=_translate)
    assert "interactive terminal" in capsys.readouterr().out

    core._sandbox_scope = TrustedSandboxScope(
        "web", "principal", "project", "web-room", "room"
    )
    handle_credential_command("git github.com", core=core, tr=_translate)
    assert "local CLI" in capsys.readouterr().out


def test_sandbox_command_gate_allows_only_git_credential_subcommand(
    monkeypatch, capsys
) -> None:
    import uagent.util_tools as commands

    core = _Core()
    core._sandbox_enabled = True
    calls = []
    sentinel = object()

    def fake_git_handler(arg, *, core, tr):
        calls.append(arg)
        return sentinel

    monkeypatch.setattr(commands, "handle_credential_command", fake_git_handler)
    assert commands.handle_command(
        ":credential git status", [], None, "", core=core
    ) is sentinel
    assert calls == ["git status"]

    commands.handle_command(":credential list", [], None, "", core=core)
    assert calls == ["git status"]
    assert "unavailable in Sandbox mode" in capsys.readouterr().out
