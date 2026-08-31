from __future__ import annotations

from uagent.providers.provider_caps import DEFAULT_PROVIDER_REGISTRY
from uagent.tools.tool_policy import (
    SideEffect,
    default_confirmation_callback,
    policy_for,
)


def test_tool_policy_defaults_to_conservative_side_effects() -> None:
    assert policy_for("calculator").side_effect is SideEffect.READ_ONLY
    assert policy_for("gmail_send").requires_confirmation
    assert policy_for("delete_file").side_effect is SideEffect.DESTRUCTIVE
    assert policy_for("unknown_future_tool").parallel_safe is False


def test_provider_registry_distinguishes_unknown_capability() -> None:
    openai = DEFAULT_PROVIDER_REGISTRY.resolve("openai")
    llama_cpp = DEFAULT_PROVIDER_REGISTRY.resolve("llama_cpp")
    unknown = DEFAULT_PROVIDER_REGISTRY.resolve("future-provider")
    assert openai.supports_tools
    assert llama_cpp.supports_tools
    assert "tools" in llama_cpp.capabilities
    assert "unknown" not in openai.capabilities
    assert unknown.capabilities == frozenset({"unknown"})
    assert not unknown.supports_tools


def test_provider_registry_classifies_auth_requirements() -> None:
    assert (
        DEFAULT_PROVIDER_REGISTRY.resolve("ollama").auth_requirement == "local_endpoint"
    )
    assert (
        DEFAULT_PROVIDER_REGISTRY.resolve("llama_cpp").auth_requirement
        == "local_endpoint"
    )
    assert (
        DEFAULT_PROVIDER_REGISTRY.resolve("lmstudio").auth_requirement
        == "local_endpoint"
    )
    assert (
        DEFAULT_PROVIDER_REGISTRY.resolve("bedrock").auth_requirement
        == "cloud_credentials"
    )
    assert DEFAULT_PROVIDER_REGISTRY.resolve("openai").auth_requirement == "api_key"
    assert (
        DEFAULT_PROVIDER_REGISTRY.resolve("future-provider").auth_requirement
        == "unknown"
    )


def test_provider_registry_exposes_deterministic_metadata() -> None:
    specs = DEFAULT_PROVIDER_REGISTRY.list()
    assert [spec.name for spec in specs] == sorted(spec.name for spec in specs)
    openai = DEFAULT_PROVIDER_REGISTRY.resolve("openai")
    assert openai.credential_sources == ("credential_store", "environment")
    assert openai.routing_policy == "default"
    assert openai.cost_hint is None
    assert openai.context_limit is None


def test_default_confirmation_uses_human_ask(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_CONFIRM_TOOLS", raising=False)
    monkeypatch.setattr(
        "uagent.tools.human_ask_tool.run_tool",
        lambda _args: '{"user_reply": "yes", "cancelled": false}',
    )
    assert default_confirmation_callback("delete_file", {}, policy_for("delete_file"))

    monkeypatch.setattr(
        "uagent.tools.human_ask_tool.run_tool",
        lambda _args: '{"user_reply": "no", "cancelled": false}',
    )
    assert not default_confirmation_callback(
        "delete_file", {}, policy_for("delete_file")
    )
