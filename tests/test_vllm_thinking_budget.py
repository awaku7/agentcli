"""vLLM numeric reasoning-budget routing and validation tests."""

from types import SimpleNamespace

import pytest

from uagent.providers.openai_projection_policy import build_openai_projection


def _project(provider="vllm", transport="chat_completions"):
    return build_openai_projection(
        provider=provider,
        model="Qwen/Qwen3.6-35B-A3B",
        transport=transport,
        messages=[{"role": "user", "content": "Solve this problem"}],
        send_tools=False,
        compaction_threshold=1000,
    )


def _verified_capability(*_args, **kwargs):
    assert kwargs == {"scoped_only": True}
    return SimpleNamespace(
        supports_thinking_budget=True,
        get_thinking_control=lambda: {
            "kind": "budget",
            "parameter": "thinking_token_budget",
            "type": "token_range",
            "min": 1,
        },
    )


def test_vllm_budget_is_opt_in(monkeypatch):
    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    projection = _project()
    assert "extra_body" not in projection.options


def test_vllm_budget_uses_extra_body_only_for_verified_chat_model(monkeypatch):
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "4096")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _verified_capability,
    )
    projection = _project()
    assert projection.options["extra_body"] == {"thinking_token_budget": 4096}
    assert "reasoning_effort" not in projection.options
    assert "max_tokens" not in projection.options

    # A vLLM-only setting must never be forwarded to a different provider.
    other = _project(provider="openai")
    assert "extra_body" not in other.options


@pytest.mark.parametrize("bad", ["0", "-1", "+2", "abc", "1.5", "  "])
def test_vllm_budget_rejects_invalid_values(monkeypatch, bad):
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", bad)
    if bad.strip():
        with pytest.raises(ValueError, match="positive integer"):
            _project()
    else:
        assert "extra_body" not in _project().options


def test_vllm_budget_requires_explicit_llmcapa_evidence(monkeypatch):
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "1024")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(ValueError, match="no verified thinking_token_budget"):
        _project()


def test_vllm_budget_rejects_explicit_responses(monkeypatch):
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "4096")
    with pytest.raises(ValueError, match="UAGENT_RESPONSES=0"):
        _project(transport="responses")


def test_vllm_budget_auto_routes_to_chat_completions(monkeypatch):
    from uagent.llm_round_helpers import _resolve_round_runtime_flags
    from uagent.runtime.capability_resolver import CapabilityResolver

    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "4096")
    monkeypatch.setenv("UAGENT_RESPONSES", "auto")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: True if feature == "responses_api" else None
    )
    responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="vllm",
        depname="Qwen/Qwen3.6-35B-A3B",
        capability_resolver=resolver,
    )
    assert responses is False

    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="vllm",
        depname="Qwen/Qwen3.6-35B-A3B",
        capability_resolver=resolver,
    )
    assert responses is True
