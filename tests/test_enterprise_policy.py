from uagent.tools.enterprise_policy import EnterprisePolicy


def test_tool_policy_actions_and_network_default_deny() -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "tools": {"shell": {"action": "deny"}, "delete_file": {"action": "confirm"}},
            "network": {"default": "deny", "allowlist": ["trusted.example"]},
        }
    )
    assert policy.decide("shell").denied
    assert policy.decide("delete_file").requires_confirmation
    assert policy.decide("http_request", {"url": "https://evil.example"}).denied
    assert not policy.decide("http_request", {"url": "https://trusted.example/api"}).denied


def test_unknown_action_is_rejected() -> None:
    try:
        EnterprisePolicy.from_mapping({"tools": {"shell": {"action": "maybe"}}})
    except ValueError as exc:
        assert "unsupported policy action" in str(exc)
    else:
        raise AssertionError("invalid action was accepted")


def test_mcp_skill_plugin_and_credential_decisions() -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "mcp_servers": {"trusted.example": {"action": "allow"}, "evil.example": {"action": "deny"}},
            "credentials": {"provider/openai": {"action": "deny"}},
            "skills": {"unsafe": {"action": "deny"}},
            "plugins": {"unknown": {"action": "confirm"}},
        }
    )
    assert policy.decide_mcp_server("https://evil.example/mcp").denied
    assert not policy.decide_mcp_server("https://trusted.example/mcp").denied
    assert policy.decide_credential("provider/openai").denied
    assert policy.decide_skill("unsafe").denied
    assert policy.decide_plugin("unknown").requires_confirmation
