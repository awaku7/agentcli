from uagent.tools.enterprise_policy import EnterprisePolicy


def test_tool_policy_actions_and_network_default_deny() -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "tools": {
                "shell": {"action": "deny"},
                "delete_file": {"action": "confirm"},
            },
            "network": {"default": "deny", "allowlist": ["trusted.example"]},
        }
    )
    assert policy.decide("shell").denied
    assert policy.decide("delete_file").requires_confirmation
    assert policy.decide("http_request", {"url": "https://evil.example"}).denied
    assert not policy.decide(
        "http_request", {"url": "https://trusted.example/api"}
    ).denied


def test_network_allowlist_uses_host_boundaries_and_ports() -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "network": {
                "default": "deny",
                "allowlist": ["trusted.example.com"],
            }
        }
    )
    assert not policy.decide("http_request", {"url": "https://trusted.example.com/api"}).denied
    assert not policy.decide("http_request", {"url": "https://api.trusted.example.com/api"}).denied
    assert policy.decide("http_request", {"url": "https://trusted.example.com.attacker.test"}).denied
    assert policy.decide("http_request", {"url": "https://trusted.example.com:8443"}).denied
    assert policy.decide("http_request", {"url": "https://user:pass@trusted.example.com"}).denied


def test_mcp_allowlist_uses_url_scheme_port_and_path_boundaries() -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "mcp_servers": {
                "https://trusted.example.com/mcp": {"action": "allow"},
                "https://blocked.example.com": {"action": "deny"},
            }
        }
    )
    assert not policy.decide_mcp_server("https://trusted.example.com/mcp/tools").denied
    assert policy.decide_mcp_server("https://trusted.example.com/mcp-evil").denied
    assert policy.decide_mcp_server("http://trusted.example.com/mcp/tools").denied
    assert policy.decide_mcp_server("https://blocked.example.com/api").denied


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
            "mcp_servers": {
                "trusted.example": {"action": "allow"},
                "evil.example": {"action": "deny"},
            },
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


def test_role_overrides_tool_policy(monkeypatch) -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "tools": {"shell": {"action": "allow"}},
            "roles": {"viewer": {"tools": {"shell": {"action": "deny"}}}},
        }
    )
    assert policy.decide("shell", {"role": "viewer"}).denied
    assert not policy.decide("shell", {"role": "admin"}).denied


def test_missing_policy_file_is_created_as_allow_all(tmp_path, monkeypatch) -> None:
    from uagent.tools.enterprise_policy import EnterprisePolicy

    path = tmp_path / "missing-policy.yaml"
    monkeypatch.setenv("UAGENT_POLICY_FILE", str(path))
    policy = EnterprisePolicy.from_environment()
    assert path.exists()
    assert not policy.decide("any_tool").denied
    assert not policy.decide_mcp_server("https://example.test").denied


def test_replace_in_file_preview_and_write_are_not_destructive() -> None:
    from uagent.tools.tool_policy import SideEffect, policy_for

    preview = policy_for("replace_in_file", {"path": "a.txt", "preview": True})
    write = policy_for("replace_in_file", {"path": "a.txt", "preview": False})
    assert preview.side_effect is SideEffect.READ_ONLY
    assert preview.requires_confirmation is False
    assert write.requires_confirmation is False
