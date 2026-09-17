"""Contract tests for provider-neutral round identities and event contracts.

These tests intentionally use only deterministic workspace keys.  They must not
create or access OS credential-store entries.
"""

from __future__ import annotations

from dataclasses import replace
from math import inf, nan
from typing import Any, Iterator

import pytest

from uagent.runtime import round_contracts
from uagent.runtime.round_contracts import (
    ContextPlan,
    ProviderProjection,
    ProviderRuntimeRegistry,
    RoundIdentifiers,
    SerializedRequest,
    StreamEvent,
)
from uagent.runtime.round_runtime import StreamEventValidator
from uagent.runtime.round_identity import (
    CanonicalJsonError,
    DeterministicTestWorkspaceKeyProvider,
    RoundIdentityFactory,
    canonical_json,
)


class _FakeRuntime:
    def __init__(self, name: str = "fake") -> None:
        self.name = name
        self.capabilities = {"streaming": True}

    def project(self, plan: ContextPlan, session: dict[str, Any]) -> ProviderProjection:
        return ProviderProjection(
            plan_id=plan.plan_id,
            projection_id=f"projection:{self.name}",
            provider=self.name,
            model="test-model",
            transport="test",
            messages=plan.messages,
            metadata={"session": dict(session)},
        )

    def serialize(self, projection: ProviderProjection) -> SerializedRequest:
        return SerializedRequest(
            identifiers=_identifiers(),
            plan_id=projection.plan_id,
            projection_id=projection.projection_id,
            provider=projection.provider,
            model=projection.model,
            payload={"messages": list(projection.messages)},
        )

    def run(
        self, request: SerializedRequest, cancellation: Any
    ) -> Iterator[StreamEvent]:
        yield StreamEvent(
            type="ResponseStarted",
            identifiers=request.identifiers,
            sequence_number=0,
            timestamp=0.0,
        )


def _identifiers(**overrides: Any) -> RoundIdentifiers:
    values: dict[str, Any] = {
        "turn_id": "turn-1",
        "round_id": "round-1",
        "attempt_id": "attempt-1",
        "request_id": "request-1",
        "stream_id": "stream-1",
        "session_generation": 1,
    }
    values.update(overrides)
    return RoundIdentifiers(**values)


def _factory(key: bytes = b"uagent-round-identity-test-key-v1") -> RoundIdentityFactory:
    return RoundIdentityFactory(
        workspace_id="test-workspace",
        key_provider=DeterministicTestWorkspaceKeyProvider(key=key),
    )


def test_context_plan_identity_does_not_mutate_input() -> None:
    messages = ({"role": "user", "content": "hello"},)
    plan = ContextPlan(plan_id="plan-1", messages=messages)
    payload = {
        "messages": plan.messages,
        "policy": {"budget": 1000},
        "schema_revision": "tools-v1",
    }
    before = repr(payload)

    plan_id = _factory().plan_id_for(payload)

    assert plan_id
    assert repr(payload) == before
    assert plan.messages == messages


def test_round_identifier_hierarchy_is_preserved_across_contracts() -> None:
    identifiers = _identifiers(round_id="round-2", attempt_id="attempt-3")
    request = SerializedRequest(
        identifiers=identifiers,
        plan_id="plan-1",
        projection_id="projection-1",
        provider="test",
        model="model",
        payload={},
    )
    event = StreamEvent(
        type="TextDelta",
        identifiers=identifiers,
        sequence_number=1,
        timestamp=0.0,
        data={"text": "ok"},
    )

    assert request.identifiers.turn_id == "turn-1"
    assert request.identifiers.round_id == "round-2"
    assert request.identifiers.attempt_id == "attempt-3"
    assert event.identifiers == request.identifiers


def test_registry_resolves_normalized_provider_names() -> None:
    registry = ProviderRuntimeRegistry()
    runtime = _FakeRuntime()

    registry.register("  OpenAI  ", runtime)

    assert registry.resolve("openai") is runtime
    assert registry.resolve("OPENAI") is runtime
    assert registry.providers() == ("openai",)


def test_registry_rejects_empty_and_duplicate_provider_names() -> None:
    registry = ProviderRuntimeRegistry()
    registry.register("demo", _FakeRuntime("first"))

    with pytest.raises(ValueError):
        registry.register("demo", _FakeRuntime("second"))
    with pytest.raises(ValueError):
        registry.register("   ", _FakeRuntime("empty"))
    with pytest.raises(round_contracts.UnknownProviderRuntime):
        registry.resolve("missing")


def test_canonical_json_is_independent_of_object_key_order() -> None:
    left = canonical_json({"b": 2, "a": 1})
    right = canonical_json({"a": 1, "b": 2})

    assert left == right


def test_canonical_json_normalizes_unicode_nfc() -> None:
    composed = canonical_json({"text": "é"})
    decomposed = canonical_json({"text": "e\u0301"})

    assert composed == decomposed


def test_canonical_json_distinguishes_null_from_missing() -> None:
    explicit_null = canonical_json({"value": None})
    missing = canonical_json({})

    assert explicit_null != missing


def test_canonical_json_rejects_non_finite_numbers() -> None:
    for value in (nan, inf, -inf):
        with pytest.raises(CanonicalJsonError):
            canonical_json({"value": value})


def test_canonical_json_rejects_non_string_keys() -> None:
    with pytest.raises(CanonicalJsonError):
        canonical_json({1: "not-a-string-key"})


def test_canonical_json_rejects_keys_colliding_after_nfc_normalization() -> None:
    with pytest.raises(CanonicalJsonError):
        canonical_json({"é": 1, "e\u0301": 2})


def test_canonical_json_uses_jcs_number_representation() -> None:
    assert canonical_json(1.0) == canonical_json(1)


def test_plan_id_is_reproducible_for_same_payload() -> None:
    factory = _factory()
    payload_a = {"messages": [{"role": "user", "content": "hello"}], "policy": "v1"}
    payload_b = {"policy": "v1", "messages": [{"content": "hello", "role": "user"}]}

    assert factory.plan_id_for(payload_a) == factory.plan_id_for(payload_b)


def test_plan_id_changes_when_key_or_policy_changes() -> None:
    payload = {"messages": [{"role": "user", "content": "hello"}], "policy": "v1"}
    factory = _factory()
    other_key_factory = _factory(b"uagent-round-identity-other-key-v1")

    assert factory.plan_id_for(payload) != other_key_factory.plan_id_for(payload)
    assert factory.plan_id_for(payload) != factory.plan_id_for(
        {**payload, "policy": "v2"}
    )


def test_projection_id_changes_with_projection_policy() -> None:
    factory = _factory()
    base = {
        "plan_id": "plan-1",
        "provider": "openai",
        "model": "model",
        "transport": "responses",
    }

    assert factory.projection_id_for(base) != factory.projection_id_for(
        {**base, "reasoning_policy": "high"}
    )
    assert factory.plan_id_for(base) != factory.projection_id_for(base)


def test_stream_validator_accepts_one_terminal_event() -> None:
    validator = getattr(round_contracts, "validate_stream_events", None)
    if validator is None:
        pytest.skip("StreamEvent validator is supplied by the primary workstream")

    events = [
        StreamEvent("ResponseStarted", _identifiers(), 0, 0.0),
        StreamEvent("TextDelta", _identifiers(), 1, 0.1, {"text": "ok"}),
        StreamEvent("ResponseCompleted", _identifiers(), 2, 0.2),
    ]
    validator(events)


@pytest.mark.parametrize(
    "events",
    [
        [
            StreamEvent("ResponseStarted", _identifiers(), 0, 0.0),
            StreamEvent("ResponseCompleted", _identifiers(), 1, 0.1),
            StreamEvent("ResponseFailed", _identifiers(), 2, 0.2),
        ],
        [
            StreamEvent("ResponseStarted", _identifiers(), 0, 0.0),
            StreamEvent("TextDelta", _identifiers(), 1, 0.1),
        ],
        [
            StreamEvent("ResponseStarted", _identifiers(), 0, 0.0),
            StreamEvent("TextDelta", _identifiers(), 2, 0.1),
            StreamEvent("ResponseCompleted", _identifiers(), 2, 0.2),
        ],
    ],
)
def test_stream_validator_rejects_invalid_terminal_or_sequence(
    events: list[StreamEvent],
) -> None:
    validator = getattr(round_contracts, "validate_stream_events", None)
    if validator is None:
        pytest.skip("StreamEvent validator is supplied by the primary workstream")

    with pytest.raises(ValueError):
        validator(events)


def test_stream_validator_requires_started_event() -> None:
    validator = StreamEventValidator()
    with pytest.raises(ValueError):
        validator.accept(StreamEvent("TextDelta", _identifiers(), 0, 0.0))


def test_stream_validator_rejects_duplicate_or_incomplete_tool_completion() -> None:
    validator = StreamEventValidator()
    validator.accept(StreamEvent("ResponseStarted", _identifiers(), 0, 0.0))
    validator.accept(
        StreamEvent(
            "ToolCallDelta",
            _identifiers(),
            1,
            0.1,
            {"tool_call_id": "call-1"},
        )
    )
    with pytest.raises(ValueError):
        validator.accept(
            StreamEvent(
                "ResponseCompleted",
                _identifiers(),
                2,
                0.2,
            )
        )

    validator.accept(
        StreamEvent(
            "ToolCallCompleted",
            _identifiers(),
            2,
            0.2,
            {"tool_call_id": "call-1", "name": "tool"},
        )
    )
    with pytest.raises(ValueError):
        validator.accept(
            StreamEvent(
                "ToolCallCompleted",
                _identifiers(),
                3,
                0.3,
                {"tool_call_id": "call-1", "name": "tool"},
            )
        )


def test_projection_can_be_derived_without_mutating_context_plan() -> None:
    original = ContextPlan(
        plan_id="plan-1",
        messages=({"role": "user", "content": "hello"},),
        telemetry={"raw_chars": 5},
    )
    runtime = _FakeRuntime()
    before = original

    projection = runtime.project(original, {"session_generation": 1})
    changed = replace(original, telemetry={"raw_chars": 10})

    assert projection.plan_id == original.plan_id
    assert original == before
    assert changed != original
    assert original.telemetry == {"raw_chars": 5}


def test_input_fingerprint_is_opaque_and_keyed() -> None:
    factory = _factory()
    payload = {"messages": [{"role": "user", "content": "private text"}]}

    fingerprint = factory.input_fingerprint_for(payload)

    assert fingerprint
    assert "private text" not in fingerprint
    assert fingerprint != _factory(
        b"uagent-round-identity-other-key-v1"
    ).input_fingerprint_for(payload)
    assert fingerprint != factory.input_fingerprint_for(
        {"messages": [{"role": "user", "content": "changed"}]}
    )
