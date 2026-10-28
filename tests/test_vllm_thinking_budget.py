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


def _both_controls_capability(*_args, **kwargs):
    assert kwargs == {"scoped_only": True}
    return SimpleNamespace(
        supports_reasoning_effort=True,
        reasoning_effort_values=["none", "high"],
        supports_thinking_budget=True,
        get_thinking_control=lambda: {
            "kind": "budget",
            "parameter": "thinking_token_budget",
            "type": "token_range",
            "min": 1,
        },
    )


@pytest.mark.parametrize("reasoning", ["high", "off", "auto"])
def test_vllm_budget_takes_priority_even_when_both_controls_are_supported(
    monkeypatch, reasoning
):
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "4096")
    monkeypatch.setenv("UAGENT_REASONING", reasoning)
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _both_controls_capability,
    )
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._is_thinking_task",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._choose_auto_effort",
        lambda *_args: "high",
    )

    projection = _project()
    assert projection.options["extra_body"] == {"thinking_token_budget": 4096}
    assert "reasoning_effort" not in projection.options
    assert "reasoning" not in projection.options
    assert projection.effort_used is None


def test_vllm_common_reasoning_uses_budget_when_both_supported(monkeypatch):
    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _both_controls_capability,
    )
    projection = _project()
    assert projection.options["extra_body"] == {"thinking_token_budget": 4096}
    assert "reasoning_effort" not in projection.options
    assert projection.effort_used is None


def test_vllm_budget_suppresses_unverified_effort_warning(monkeypatch):
    import warnings

    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "4096")
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _verified_capability,
    )
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        projection = _project()

    assert projection.options["extra_body"] == {"thinking_token_budget": 4096}
    assert "reasoning_effort" not in projection.options
    assert not any("reasoning_effort" in str(item.message) for item in recorded)


@pytest.mark.parametrize(
    ("reasoning", "budget"),
    [
        ("minimal", 128),
        ("low", 512),
        ("medium", 2048),
        ("high", 4096),
        ("xhigh", 8192),
    ],
)
def test_vllm_common_reasoning_levels_map_to_budget(monkeypatch, reasoning, budget):
    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", reasoning)
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _both_controls_capability,
    )
    projection = _project()
    assert projection.options["extra_body"] == {"thinking_token_budget": budget}
    assert "reasoning_effort" not in projection.options
    assert projection.effort_used is None


def test_vllm_explicit_budget_overrides_derived_budget(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "1000")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _both_controls_capability,
    )
    assert _project().options["extra_body"] == {"thinking_token_budget": 1000}


def test_vllm_derived_budget_clamps_to_model_range(monkeypatch):
    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "high")

    def limited(*_args, **kwargs):
        assert kwargs == {"scoped_only": True}
        return SimpleNamespace(
            supports_thinking_budget=True,
            supports_reasoning_effort=True,
            reasoning_effort_values=["high"],
            get_thinking_control=lambda: {
                "kind": "budget",
                "parameter": "thinking_token_budget",
                "type": "token_range",
                "min": 200,
                "max": 1024,
            },
        )

    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        limited,
    )
    assert _project().options["extra_body"] == {"thinking_token_budget": 1024}
    monkeypatch.setenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "2048")
    with pytest.raises(ValueError, match="outside the llmcapa model range"):
        _project()


def test_vllm_derived_budget_auto_respects_thinking_task(monkeypatch):
    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "auto")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _both_controls_capability,
    )
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._is_thinking_task",
        lambda *_args: False,
    )
    assert "extra_body" not in _project().options
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._is_thinking_task",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._choose_auto_effort",
        lambda *_args: "medium",
    )
    assert _project().options["extra_body"] == {"thinking_token_budget": 2048}


def test_vllm_derived_budget_chooses_chat_and_explicit_responses_errors(
    monkeypatch,
):
    from uagent.llm_round_helpers import _resolve_round_runtime_flags
    from uagent.runtime.capability_resolver import CapabilityResolver

    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setenv("UAGENT_RESPONSES", "auto")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        _both_controls_capability,
    )
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
    with pytest.raises(ValueError, match="UAGENT_RESPONSES=0"):
        _project(transport="responses")


def test_vllm_effort_only_model_remains_effort_based(monkeypatch):
    monkeypatch.delenv("UAGENT_VLLM_THINKING_TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        lambda *_args, **kwargs: SimpleNamespace(
            supports_thinking_budget=False,
            supports_reasoning_effort=True,
            reasoning_effort_values=["low", "medium", "high"],
        ),
    )
    projection = _project()
    assert projection.options["reasoning_effort"] == "high"
    assert "extra_body" not in projection.options
