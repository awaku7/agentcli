"""Regression tests for trusted, per-user and per-session Sandbox settings."""

from __future__ import annotations

import json
import os
import stat

import pytest

from uagent.runtime import mxc_backend, mxc_session_settings
from uagent.runtime.execution_broker import TrustedSandboxScope


@pytest.fixture
def scope():
    return TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="room-1",
        binding_generation="generation-1",
    )


def test_session_environment_inherits_user_and_overrides_per_session(
    tmp_path, monkeypatch, scope
):
    mxc_session_settings.save_environment(
        tmp_path,
        scope,
        "user",
        {"GIT_AUTHOR_NAME": "Alice", "GIT_AUTHOR_EMAIL": "alice@example.test"},
    )
    mxc_session_settings.save_environment(
        tmp_path, scope, "session", {"GIT_AUTHOR_NAME": "Session Alice"}
    )
    assert mxc_session_settings.effective_environment(tmp_path, scope) == {
        "GIT_AUTHOR_NAME": "Session Alice",
        "GIT_AUTHOR_EMAIL": "alice@example.test",
    }
    monkeypatch.setattr(mxc_backend, "_local_app_data", lambda: tmp_path)
    assert mxc_backend._session_settings_environment(scope)["GIT_AUTHOR_NAME"] == (
        "Session Alice"
    )


def test_session_environment_isolated_by_principal_and_scope(tmp_path, scope):
    mxc_session_settings.save_environment(
        tmp_path, scope, "user", {"GIT_AUTHOR_NAME": "Alice"}
    )
    mxc_session_settings.save_environment(
        tmp_path, scope, "session", {"SESSION_LABEL": "Room 1"}
    )
    other_principal = TrustedSandboxScope(
        "web", "bob", "project-a", "web-room", "room-1", "generation-1"
    )
    other_session = TrustedSandboxScope(
        "web", "alice", "project-a", "web-room", "room-2", "generation-1"
    )
    rebound_session = TrustedSandboxScope(
        "web", "alice", "project-a", "web-room", "room-1", "generation-2"
    )
    assert mxc_session_settings.effective_environment(tmp_path, other_principal) == ({})
    assert mxc_session_settings.effective_environment(tmp_path, other_session) == {
        "GIT_AUTHOR_NAME": "Alice"
    }
    assert mxc_session_settings.effective_environment(tmp_path, rebound_session) == {
        "GIT_AUTHOR_NAME": "Alice"
    }
    assert mxc_backend._scope_key(rebound_session) != mxc_backend._scope_key(scope)


@pytest.mark.parametrize(
    "environment",
    [
        {"HOME": "/host/home"},
        {"PATH": "/tmp/untrusted"},
        {"LD_PRELOAD": "/tmp/payload.so"},
        {"NODE_OPTIONS": "--require=payload.js"},
        {"GIT_ASKPASS": "/tmp/askpass"},
        {"UAGENT_MXC_NODE": "/tmp/node"},
        {"GIT_CONFIG_COUNT": "1"},
        {"API_TOKEN": "not-allowed"},
        {"OPENAI_API_KEY": "not-allowed"},
        {"ANTHROPIC_API_KEY": "not-allowed"},
        {"GEMINI_API_KEY": "not-allowed"},
        {"GIT_AUTH_TOKEN": "not-allowed"},
        {"HTTP_PROXY": "http://alice:password@example.test:8080"},
        {"AN_ENV": "line\nnext"},
    ],
)
def test_session_environment_rejects_sensitive_or_runtime_overrides(
    tmp_path, scope, environment
):
    with pytest.raises(ValueError):
        mxc_session_settings.save_environment(tmp_path, scope, "session", environment)


def test_existing_file_must_be_private(tmp_path, scope):
    file = mxc_session_settings.save_environment(tmp_path, scope, "user", {"TEAM": "A"})
    if os.name != "nt":
        assert stat.S_IMODE(file.stat().st_mode) == 0o600
        file.chmod(0o644)
        with pytest.raises(PermissionError, match="private"):
            mxc_session_settings.effective_environment(tmp_path, scope)


def test_symbolic_settings_file_is_rejected(tmp_path, scope):
    if os.name == "nt":
        pytest.skip("symlink creation may require Windows privileges")
    file = mxc_session_settings.settings_path(tmp_path, scope, "session")
    file.parent.mkdir(parents=True, mode=0o700)
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"environment": {"TEAM": "stolen"}}), encoding="utf-8")
    file.symlink_to(other)
    with pytest.raises(OSError):
        mxc_session_settings.effective_environment(tmp_path, scope)
    with pytest.raises(PermissionError):
        mxc_session_settings.save_environment(
            tmp_path, scope, "session", {"TEAM": "safe"}
        )


def test_settings_save_rejects_oversized_payload_without_clobbering_old(
    tmp_path, scope
):
    mxc_session_settings.save_environment(tmp_path, scope, "user", {"TEAM": "old"})
    with pytest.raises(ValueError, match="16 KiB"):
        mxc_session_settings.save_environment(
            tmp_path,
            scope,
            "user",
            {"VAR_" + str(i): "x" * 2048 for i in range(10)},
        )
    assert mxc_session_settings.effective_environment(tmp_path, scope) == {
        "TEAM": "old"
    }


def test_uag_settings_ancestor_cannot_be_symlink(tmp_path, scope):
    if os.name == "nt":
        pytest.skip("symlink creation may require Windows privileges")
    original = tmp_path / "other-uag"
    original.mkdir(mode=0o700)
    (tmp_path / "uag").symlink_to(original, target_is_directory=True)
    with pytest.raises(PermissionError):
        mxc_session_settings.effective_environment(tmp_path, scope)


def test_cli_gui_share_os_user_defaults_without_sharing_session_overrides(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(mxc_backend, "_trusted_local_principal", lambda: "os-uid:42")
    cli = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="conversation-a"
    )
    gui = mxc_backend.startup_scope(
        entry_point="gui", project_path=str(tmp_path), session_id="conversation-a"
    )
    another_cli = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="conversation-b"
    )
    assert cli.principal_id == gui.principal_id
    assert mxc_session_settings.settings_path(
        tmp_path, cli, "user"
    ) == mxc_session_settings.settings_path(tmp_path, gui, "user")
    assert mxc_session_settings.settings_path(
        tmp_path, cli, "session"
    ) != mxc_session_settings.settings_path(tmp_path, gui, "session")
    assert mxc_session_settings.settings_path(
        tmp_path, cli, "session"
    ) != mxc_session_settings.settings_path(tmp_path, another_cli, "session")
    mxc_session_settings.save_environment(
        tmp_path, cli, "user", {"GIT_AUTHOR_NAME": "Shared local"}
    )
    mxc_session_settings.save_environment(
        tmp_path, cli, "session", {"GIT_AUTHOR_NAME": "CLI override"}
    )
    assert mxc_session_settings.effective_environment(tmp_path, cli)[
        "GIT_AUTHOR_NAME"
    ] == "CLI override"
    assert mxc_session_settings.effective_environment(tmp_path, gui)[
        "GIT_AUTHOR_NAME"
    ] == "Shared local"


def test_session_settings_survive_process_scope_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(mxc_backend, "_trusted_local_principal", lambda: "os-uid:42")
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 14001)
    first = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="saved-id"
    )
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 14002)
    second = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="saved-id"
    )
    assert first.scope_id != second.scope_id
    assert mxc_backend._scope_key(first) != mxc_backend._scope_key(second)
    assert mxc_session_settings.settings_path(
        tmp_path, first, "session"
    ) == mxc_session_settings.settings_path(tmp_path, second, "session")
    mxc_session_settings.save_environment(
        tmp_path, first, "session", {"SESSION_LABEL": "saved"}
    )
    assert mxc_session_settings.effective_environment(tmp_path, second)[
        "SESSION_LABEL"
    ] == "saved"


def test_web_and_a2a_settings_remain_separate_from_local_principal(tmp_path):
    principal = "os-uid:42"
    cli = TrustedSandboxScope(
        "cli", principal, "project", "cli-session", "one", settings_session_id="one"
    )
    web = TrustedSandboxScope(
        "web", principal, "project", "web-room", "one", settings_session_id="one"
    )
    a2a = TrustedSandboxScope(
        "a2a", principal, "project", "a2a-task", "one", settings_session_id="one"
    )
    paths = {
        mxc_session_settings.settings_path(tmp_path, item, "user")
        for item in (cli, web, a2a)
    }
    assert len(paths) == 3
    mxc_session_settings.save_environment(
        tmp_path, cli, "user", {"GIT_AUTHOR_NAME": "OS User"}
    )
    assert mxc_session_settings.effective_environment(tmp_path, web) == {}
    assert mxc_session_settings.effective_environment(tmp_path, a2a) == {}


def test_web_session_settings_follow_room_not_process(monkeypatch, tmp_path):
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 14001)
    first = mxc_backend.local_web_room_scope(
        principal_id="web-user",
        project_id="project",
        room_id="room-x",
        room_generation="generation-1",
    )
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 14002)
    second = mxc_backend.local_web_room_scope(
        principal_id="web-user",
        project_id="project",
        room_id="room-x",
        room_generation="generation-1",
    )
    renewed = mxc_backend.local_web_room_scope(
        principal_id="web-user",
        project_id="project",
        room_id="room-x",
        room_generation="generation-2",
    )
    assert first.scope_id != second.scope_id
    assert mxc_session_settings.settings_path(
        tmp_path, first, "session"
    ) == mxc_session_settings.settings_path(tmp_path, second, "session")
    assert mxc_session_settings.settings_path(
        tmp_path, first, "session"
    ) != mxc_session_settings.settings_path(tmp_path, renewed, "session")


def test_unconfigured_environment_is_empty(tmp_path, scope):
    assert mxc_session_settings.effective_environment(tmp_path, scope) == {}
