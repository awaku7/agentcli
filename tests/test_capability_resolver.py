from uagent.runtime.capability_resolver import (
    CapabilityResolver,
    CapabilityState,
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


def test_unknown_provider_is_conservatively_disabled() -> None:
    snapshot = CapabilityResolver(feature_lookup=lambda *_: None).resolve("unknown")

    assert snapshot.responses_create.state is CapabilityState.FALSE
    assert snapshot.tools.state is CapabilityState.FALSE
