from uagent.computer_use.actions import SUPPORTED_ACTIONS
from uagent.computer_use.config import computer_use_policy_from_env


def test_policy_from_env_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("UAGENT_COMPUTER_USE", raising=False)
    policy = computer_use_policy_from_env()
    assert policy.enabled is True


def test_policy_allows_all_actions_when_action_list_is_omitted(monkeypatch):
    monkeypatch.setenv("UAGENT_COMPUTER_USE", "1")
    monkeypatch.delenv("UAGENT_COMPUTER_ALLOWED_ACTIONS", raising=False)

    policy = computer_use_policy_from_env()

    assert policy.allowed_actions == SUPPORTED_ACTIONS


def test_policy_from_env_is_shared_across_entrypoints(monkeypatch):
    monkeypatch.setenv("UAGENT_COMPUTER_USE", "1")
    monkeypatch.setenv("UAGENT_COMPUTER_ALLOWED_ACTIONS", "screenshot,click,type")
    monkeypatch.setenv("UAGENT_COMPUTER_ALLOWED_DOMAINS", "example.com,example.org")
    monkeypatch.setenv("UAGENT_COMPUTER_REQUIRE_CONFIRMATION", "1")
    monkeypatch.setenv("UAGENT_COMPUTER_MAX_ACTIONS", "20")
    monkeypatch.setenv("UAGENT_COMPUTER_MAX_TURNS", "5")
    monkeypatch.setenv("UAGENT_COMPUTER_TIMEOUT", "45")

    policy = computer_use_policy_from_env()

    assert policy.enabled is True
    assert policy.environment == "desktop"
    assert policy.allowed_actions == frozenset({"screenshot", "click", "type"})
    assert policy.allowed_domains == frozenset({"example.com", "example.org"})
    assert policy.require_confirmation is True
    assert policy.max_actions == 20
    assert policy.max_turns == 5
    assert policy.timeout == 45.0
