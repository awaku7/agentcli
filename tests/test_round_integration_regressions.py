from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.capability_resolver import CapabilityResolver, CapabilityState
from uagent.runtime.context_plan_builder import build_context_plan
from uagent.runtime.message_transform import MessageTransformPipeline
from uagent.runtime.provider_context import project_messages_for_provider
from uagent.runtime.round_identity import DeterministicTestWorkspaceKeyProvider
from uagent.runtime.round_runtime import RoundAttemptBudget
from uagent.uagent_llm import (
    _begin_responses_runtime,
    _record_responses_runtime_response,
    _record_round_context_plan,
)


def test_round_contracts_off_leaves_legacy_bridge_and_core_untouched(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_ROUND_CONTRACTS", "0")
    core = SimpleNamespace(
        context_plan="legacy-sentinel",
        responses_state={"previous_response_id": "resp_legacy"},
    )

    _record_round_context_plan(
        provider="openai",
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
    )

    assert core.context_plan == "legacy-sentinel"
    assert (
        _begin_responses_runtime(
            core=core, provider="openai", model="gpt-test", enabled=False
        )
        is None
    )
    assert not hasattr(core, "responses_runtime")


def test_responses_bridge_preserves_tool_output_and_stale_retry_invariants() -> None:
    core = SimpleNamespace(
        responses_state={"previous_response_id": "resp_legacy"},
    )

    runtime = _begin_responses_runtime(
        core=core, provider="openai", model="gpt-test", enabled=True
    )
    assert runtime is not None
    assert runtime.state == "Active"
    assert runtime.previous_response_id == "resp_legacy"

    _record_responses_runtime_response(
        core=core,
        enabled=True,
        tool_calls=[{"id": "call-1", "type": "function"}],
    )
    assert runtime.state == "AwaitingToolOutput"
    runtime.accept_tool_output("resp_legacy", "call-1", {"ok": True})
    assert runtime.state == "Continuing"

    retry = runtime.request_stale_retry()
    budget = RoundAttemptBudget(total_limit=1)
    assert budget.try_consume(retry)
    assert runtime.accept_retry(retry, authorized=True)
    assert runtime.state == "Fresh"

    runtime.interrupt()
    assert runtime.previous_response_id is None
    assert runtime.active_response_id is None


def test_message_transform_precedes_projection_without_mutating_history() -> None:
    history = [
        {
            "role": "user",
            "content": "hello" + chr(0xD800),
            "_uagent_internal": "remove only at projection",
        }
    ]
    transformed = MessageTransformPipeline().apply(history).messages
    projected = project_messages_for_provider(
        [dict(message) for message in transformed],
        provider="openai",
        model="gpt-test",
    )

    assert history[0]["content"] == "hello" + chr(0xD800)
    assert transformed[0]["content"] == "hello�"
    assert projected[0]["content"] == "hello�"
    assert "_uagent_internal" not in projected[0]


def test_unknown_capability_uses_conservative_native_fallback() -> None:
    snapshot = CapabilityResolver(feature_lookup=lambda *_: None).resolve(
        "unknown-provider", "unknown-model"
    )

    assert snapshot.responses_create.state is CapabilityState.FALSE
    assert not snapshot.responses_create.is_native_allowed()
    assert snapshot.tools.state is CapabilityState.FALSE
    assert not snapshot.tools.is_native_allowed()


def test_context_plan_builder_is_observational_for_legacy_messages() -> None:
    messages = [{"role": "user", "content": "hello"}]
    before = [dict(message) for message in messages]

    plan = build_context_plan(
        workspace_id="test-workspace",
        messages=messages,
        tool_specs=(),
        policy={"provider": "openai", "model": "gpt-test"},
        key_provider=DeterministicTestWorkspaceKeyProvider(),
    )

    assert messages == before
    assert plan.messages[0]["content"] == "hello"
