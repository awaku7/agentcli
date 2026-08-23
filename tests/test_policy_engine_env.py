from __future__ import annotations

from uagent.runtime.policy_engine import Permission, permission_from_environment


def test_policy_level_is_opt_in(monkeypatch):
    monkeypatch.delenv("UAGENT_POLICY_LEVEL", raising=False)
    assert permission_from_environment() is None


def test_policy_level_accepts_named_permission(monkeypatch):
    monkeypatch.setenv("UAGENT_POLICY_LEVEL", "read_only")
    assert permission_from_environment() is Permission.READ_ONLY


def test_invalid_policy_level_is_conservative(monkeypatch):
    monkeypatch.setenv("UAGENT_POLICY_LEVEL", "unknown")
    assert permission_from_environment() is Permission.READ_ONLY
