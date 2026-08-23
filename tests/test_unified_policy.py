from __future__ import annotations

from uagent.runtime.policy_engine import Permission, PolicyDecision, UnifiedPolicy


def test_unified_policy_combines_permission_and_enterprise_rules(tmp_path):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("tools:\n  delete_file: deny\n", encoding="utf-8")
    policy = UnifiedPolicy.from_file(policy_file, permission=Permission.WRITE)

    assert policy.decide("delete_file", {}) is PolicyDecision.DENY
    assert policy.decide("read_file", {}) is PolicyDecision.ALLOW


def test_unified_policy_permission_is_stricter_than_yaml(tmp_path):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("tools:\n  create_file: allow\n", encoding="utf-8")
    policy = UnifiedPolicy.from_file(policy_file, permission=Permission.READ_ONLY)

    assert policy.decide("create_file", {}) is PolicyDecision.DENY
