import pytest

from uagent.computer_use.actions import ComputerAction, normalize_action
from uagent.computer_use.capability import (
    ComputerUseCapabilityError,
    get_computer_use_capability,
)
from uagent.computer_use.policy import ComputerUsePolicy


def test_normalize_action_preserves_action_id_and_fields():
    action = normalize_action(
        action_id="call-1",
        payload={
            "action": "left_click",
            "coordinate": [100, 200],
        },
        provider="anthropic",
    )

    assert isinstance(action, ComputerAction)
    assert action.action_id == "call-1"
    assert action.action == "click"
    assert action.coordinate == (100, 200)
    assert action.provider == "anthropic"


def test_normalize_action_rejects_unknown_action():
    with pytest.raises(ValueError, match="unsupported computer action"):
        normalize_action(
            action_id="call-2",
            payload={"action": "launch_missiles"},
            provider="anthropic",
        )


def test_policy_allows_configured_action_and_environment():
    policy = ComputerUsePolicy(
        enabled=True,
        environment="desktop",
        require_confirmation=False,
        allowed_actions=frozenset({"screenshot", "click", "type"}),
        allowed_domains=frozenset({"example.com"}),
        max_actions=10,
        max_turns=3,
        timeout=30.0,
    )

    decision = policy.check(
        ComputerAction(action_id="a1", action="click"),
        domain="example.com",
    )
    assert decision.allowed is True


def test_policy_rejects_disabled_or_disallowed_action():
    policy = ComputerUsePolicy(
        enabled=False,
        environment="desktop",
        require_confirmation=True,
        allowed_actions=frozenset({"screenshot"}),
        allowed_domains=frozenset(),
        max_actions=10,
        max_turns=3,
        timeout=30.0,
    )

    decision = policy.check(
        ComputerAction(action_id="a2", action="click"),
    )
    assert decision.allowed is False
    assert decision.reason


def test_capability_lookup_uses_llmcapa(monkeypatch):
    class FakeComputerUse:
        supported = True

    class FakeCapability:
        computer_use = FakeComputerUse()

    monkeypatch.setattr(
        "uagent.computer_use.capability.get_capability",
        lambda model, provider: FakeCapability(),
    )
    assert get_computer_use_capability("claude-sonnet", "claude") is not None


def test_capability_lookup_stops_when_llmcapa_has_no_record(monkeypatch):
    monkeypatch.setattr(
        "uagent.computer_use.capability.get_capability",
        lambda model, provider: None,
    )
    with pytest.raises(ComputerUseCapabilityError):
        get_computer_use_capability("unknown", "claude")
