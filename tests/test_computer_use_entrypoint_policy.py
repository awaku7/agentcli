from uagent import core


def test_core_exposes_shared_policy_lazily(monkeypatch):
    monkeypatch.setenv("UAGENT_COMPUTER_USE", "1")
    monkeypatch.setenv("UAGENT_COMPUTER_ENVIRONMENT", "browser")
    monkeypatch.setenv("UAGENT_COMPUTER_ALLOWED_ACTIONS", "screenshot")

    policy = core.get_computer_use_policy()

    assert policy.enabled is True
    assert policy.environment == "browser"
    assert policy.allowed_actions == frozenset({"screenshot"})
