"""Regression tests for Foundry-only capability gating."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.llm_round_helpers import _resolve_round_runtime_flags


def test_explicit_responses_false_catalog_does_not_veto_other_providers(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_responses_api",
        lambda model, provider, default=None: False,
    )

    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="ollama",
        depname="llama3.3",
    )

    assert use_responses is True


def test_tool_discovery_explicit_responses_override_remains_non_foundry(
    monkeypatch,
) -> None:
    import uagent.runtime.tool_discovery as discovery

    seen: dict[str, object] = {}
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_responses_api",
        lambda model, provider, default=None: False,
    )
    monkeypatch.setattr(
        discovery,
        "resolve_tool_discovery",
        lambda **kwargs: seen.update(kwargs) or object(),
    )

    discovery.resolve_tool_discovery_from_environment(
        provider="ollama",
        depname="llama3.3",
    )

    assert seen["use_responses_api"] is True


def test_tool_discovery_foundry_explicit_responses_requires_positive_evidence(
    monkeypatch,
) -> None:
    import uagent.runtime.tool_discovery as discovery

    seen: dict[str, object] = {}
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_responses_api",
        lambda model, provider, default=None: False,
    )
    monkeypatch.setattr(
        discovery,
        "resolve_tool_discovery",
        lambda **kwargs: seen.update(kwargs) or object(),
    )

    discovery.resolve_tool_discovery_from_environment(
        provider="foundry_local",
        depname="phi-4-mini",
    )

    assert seen["use_responses_api"] is False
