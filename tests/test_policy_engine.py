from __future__ import annotations

import pytest

from uagent.runtime.policy_engine import Permission, PolicyDecision, evaluate_tool


def test_read_only_tool_is_allowed_for_read_only_task():
    decision = evaluate_tool("read_file", {}, Permission.READ_ONLY)
    assert decision == PolicyDecision.ALLOW


def test_write_tool_requires_confirmation_for_propose_only():
    decision = evaluate_tool("create_file", {}, Permission.PROPOSE_ONLY)
    assert decision == PolicyDecision.CONFIRM


def test_write_tool_is_denied_for_read_only_task():
    decision = evaluate_tool("create_file", {}, Permission.READ_ONLY)
    assert decision == PolicyDecision.DENY


def test_external_send_requires_confirmation_even_for_write():
    decision = evaluate_tool("gmail_send", {}, Permission.WRITE)
    assert decision == PolicyDecision.CONFIRM


def test_child_permission_cannot_exceed_parent():
    with pytest.raises(ValueError):
        Permission.assert_child_allowed(Permission.READ_ONLY, Permission.WRITE)


def test_unknown_tool_is_conservative():
    assert evaluate_tool("future_tool", {}, Permission.READ_ONLY) == PolicyDecision.DENY
