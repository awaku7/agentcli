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
    assert not policy.decide(
        "http_request", {"url": "https://trusted.example.com/api"}
    ).denied
    assert not policy.decide(
        "http_request", {"url": "https://api.trusted.example.com/api"}
    ).denied
    assert policy.decide(
        "http_request", {"url": "https://trusted.example.com.attacker.test"}
    ).denied
    assert policy.decide(
        "http_request", {"url": "https://trusted.example.com:8443"}
    ).denied
    assert policy.decide(
        "http_request", {"url": "https://user:pass@trusted.example.com"}
    ).denied


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


def test_mcp_tool_level_gate_confirm() -> None:
    policy = EnterprisePolicy.from_mapping(
        {
            "mcp_tools": {
                "physical_vision:arm_sort": {"action": "confirm"},
                "physical_vision:erase": {"action": "deny"},
            }
        }
    )
    # 指定機能は承認が必要
    decision = policy.decide(
        "handle_mcp_v2",
        {"server_name": "physical_vision", "tool_name": "arm_sort"},
    )
    assert decision.requires_confirmation
    assert decision.reason == "mcp_tool:physical_vision:arm_sort"
    # deny 指定は実行不可
    assert policy.decide(
        "handle_mcp_v2",
        {"server_name": "physical_vision", "tool_name": "erase"},
    ).denied
    # 未指定の機能は従来どおり許可
    assert not policy.decide(
        "handle_mcp_v2",
        {"server_name": "physical_vision", "tool_name": "scan_and_judge"},
    ).denied
    # server / tool が欠けている場合は判定しない
    assert not policy.decide("handle_mcp_v2", {"tool_name": "arm_sort"}).denied
    assert not policy.decide("handle_mcp_v2", {"server_name": "physical_vision"}).denied
    # 他ツールには影響しない
    assert not policy.decide("read_file", {"path": "x"}).denied


def test_mcp_tool_gate_falls_back_to_tool_level() -> None:
    # tools で handle_mcp_v2 を deny すれば mcp_tools の allow より優先(安全側)
    policy = EnterprisePolicy.from_mapping(
        {
            "tools": {"handle_mcp_v2": {"action": "deny"}},
            "mcp_tools": {"physical_vision:arm_sort": {"action": "confirm"}},
        }
    )
    decision = policy.decide(
        "handle_mcp_v2",
        {"server_name": "physical_vision", "tool_name": "arm_sort"},
    )
    assert decision.denied
    assert decision.reason == "tool:handle_mcp_v2"
