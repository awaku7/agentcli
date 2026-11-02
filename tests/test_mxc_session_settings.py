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


def test_unconfigured_environment_is_empty(tmp_path, scope):
    assert mxc_session_settings.effective_environment(tmp_path, scope) == {}
