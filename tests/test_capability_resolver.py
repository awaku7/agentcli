import pytest

from uagent.llmcapa_util import provider_allows_responses_api
from uagent.runtime.capability_resolver import (
    CapabilityResolver,
    CapabilityState,
    native_structured_output_request_for_runtime,
    structured_output_native_enabled,
)


def test_known_responses_provider_is_unknown_without_model_evidence() -> None:
    snapshot = CapabilityResolver(feature_lookup=lambda *_: None).resolve(
        "openai", "gpt-example"
    )

    assert snapshot.responses_create.state is CapabilityState.UNKNOWN
    assert not snapshot.responses_create.is_native_allowed()
    assert snapshot.responses_streaming.is_native_allowed()
    assert snapshot.responses_continuation.is_native_allowed()


def test_model_evidence_can_enable_or_disable_responses() -> None:
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: True if feature == "responses_api" else False
    )
    snapshot = resolver.resolve("openai", "gpt-example")

    assert snapshot.responses_create.state is CapabilityState.TRUE_DOCUMENTED
    assert snapshot.structured_output.state is CapabilityState.FALSE


def test_tool_search_uses_llmcapa_evidence_and_fails_closed_when_unknown() -> None:
    supported = CapabilityResolver(
        feature_lookup=lambda feature, *_: feature == "tool_search"
    ).resolve("openai", "custom-deployment", transport="responses")
    unsupported = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "tool_search" else None
    ).resolve("openai", "custom-deployment", transport="responses")
    unknown = CapabilityResolver(feature_lookup=lambda *_: None).resolve(
        "openai", "custom-deployment", transport="responses"
    )

    assert supported.tool_search.state is CapabilityState.TRUE_DOCUMENTED
    assert supported.tool_search.is_native_allowed()
    assert unsupported.tool_search.state is CapabilityState.FALSE
    assert not unsupported.tool_search.is_native_allowed()
    assert unknown.tool_search.state is CapabilityState.UNKNOWN
    assert not unknown.tool_search.is_native_allowed()


def test_unknown_provider_is_conservatively_disabled() -> None:
    snapshot = CapabilityResolver(feature_lookup=lambda *_: None).resolve("unknown")

    assert snapshot.responses_create.state is CapabilityState.FALSE
    assert snapshot.tools.state is CapabilityState.FALSE


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("openai", "gpt-4o", True),
        ("azure", "unknown-model", True),
        ("openrouter", "unknown-model", True),
        ("deepseek", "unknown-model", True),
        ("claude", "unknown-model", False),
        ("gemini", "unknown-model", False),
        ("unknown-provider", "unknown-model", False),
    ],
)
def test_legacy_responses_gate_characterization(
    provider: str, model: str, expected: bool
) -> None:
    assert provider_allows_responses_api(provider, model) is expected


@pytest.mark.parametrize(
    "provider",
    ["openai", "azure", "openrouter", "deepseek"],
)
def test_resolver_keeps_model_unknown_distinct_from_legacy_allowance(
    provider: str,
) -> None:
    snapshot = CapabilityResolver(feature_lookup=lambda *_: None).resolve(
        provider, "unknown-model", transport="responses"
    )

    assert snapshot.responses_create.state is CapabilityState.UNKNOWN
    assert not snapshot.responses_create.is_native_allowed()
    assert provider_allows_responses_api(provider, "unknown-model") is True


def test_structured_output_requires_positive_model_evidence() -> None:
    supported = CapabilityResolver(
        feature_lookup=lambda feature, *_: feature == "json_schema"
    )
    unknown = CapabilityResolver(feature_lookup=lambda *_: None)

    assert structured_output_native_enabled(
        "claude", "claude-model", resolver=supported
    )
    assert not structured_output_native_enabled(
        "claude", "claude-model", resolver=unknown
    )


def test_structured_output_accepts_json_mode_evidence() -> None:
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: feature == "json_mode"
    )

    assert structured_output_native_enabled("gemini", "gemini-model", resolver=resolver)


def test_structured_output_fails_closed_when_resolution_fails() -> None:
    class FailingResolver:
        def resolve(self, *_args, **_kwargs):
            raise RuntimeError("catalog unavailable")

    assert not structured_output_native_enabled(
        "claude", "claude-model", resolver=FailingResolver()
    )


def test_runtime_structured_output_request_respects_capability_gate() -> None:
    messages = [
        {
            "role": "system",
            "content": 'response_mode: json\n\nresponse_schema:\n{"type":"object"}',
        }
    ]
    allowed = CapabilityResolver(
        feature_lookup=lambda feature, *_: feature == "json_schema"
    )
    unknown = CapabilityResolver(feature_lookup=lambda *_: None)

    assert (
        native_structured_output_request_for_runtime(
            messages, provider="claude", model="model", resolver=allowed
        )["type"]
        == "json_schema"
    )
    assert (
        native_structured_output_request_for_runtime(
            messages, provider="claude", model="model", resolver=unknown
        )
        is None
    )
