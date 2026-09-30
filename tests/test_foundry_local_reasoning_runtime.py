from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.foundry_local_runtime import FoundryLocalRuntime
from uagent.providers.openai_projection_policy import build_openai_projection
from uagent.providers.runtime_registry import build_provider_runtime_registry
from uagent.runtime.context_plan_builder import build_context_plan
from uagent.runtime.round_contracts import RoundIdentifiers, validate_stream_events
from uagent.runtime.round_identity import (
    DeterministicTestWorkspaceKeyProvider,
    RoundIdentityFactory,
)


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False


class _Chat:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(self.response)
        return self.response


class _Client:
    def __init__(self, response) -> None:
        self.chat = SimpleNamespace(completions=_Chat(response))
        self.responses = SimpleNamespace()


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1)


def _plan() -> object:
    return build_context_plan(
        workspace_id="test-workspace",
        messages=[{"role": "user", "content": "solve this"}],
        policy={"provider": "foundry_local", "model": "phi-4-mini-reasoning"},
        key_provider=DeterministicTestWorkspaceKeyProvider(),
    )


def _request(runtime: FoundryLocalRuntime):
    factory = RoundIdentityFactory(
        "test-workspace", DeterministicTestWorkspaceKeyProvider()
    )
    return runtime.serialize(runtime.project(_plan(), {"identity_factory": factory}))


def test_foundry_stream_emits_explicit_reasoning_content() -> None:
    chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    reasoning_content="thinking",
                    content="answer",
                    tool_calls=[],
                )
            )
        ]
    )
    runtime = FoundryLocalRuntime(
        client=_Client([chunk]),
        provider="foundry_local",
        model="phi-4-mini-reasoning",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(runtime), _Cancellation()))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ReasoningDelta",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert events[1].data["text"] == "thinking"
    assert events[2].data["text"] == "answer"


def test_foundry_stream_splits_think_markers_across_chunks() -> None:
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="<think>ana", tool_calls=[], reasoning_content=None
                    )
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="lysis</think>answer",
                        tool_calls=[],
                        reasoning_content=None,
                    )
                )
            ]
        ),
    ]
    runtime = FoundryLocalRuntime(
        client=_Client(chunks),
        provider="foundry_local",
        model="phi-4-mini-reasoning",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(runtime), _Cancellation()))

    validate_stream_events(events)
    reasoning = "".join(
        str(event.data.get("text") or "")
        for event in events
        if event.type == "ReasoningDelta"
    )
    visible = "".join(
        str(event.data.get("text") or "")
        for event in events
        if event.type == "TextDelta"
    )
    assert reasoning == "analysis"
    assert visible == "answer"


def test_foundry_non_streaming_emits_reasoning_field() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    reasoning="thinking",
                    content="answer",
                    tool_calls=[],
                )
            )
        ]
    )
    runtime = FoundryLocalRuntime(
        client=_Client(response),
        provider="foundry_local",
        model="phi-4-mini-reasoning",
        identifiers=_identifiers(),
        streaming=False,
    )

    events = list(runtime.run(_request(runtime), _Cancellation()))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ReasoningDelta",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert events[1].data["text"] == "thinking"


def test_foundry_registry_uses_reasoning_aware_runtime() -> None:
    registry = build_provider_runtime_registry(
        provider="foundry_local",
        client=_Client([]),
        model="phi-4-mini",
        identifiers=_identifiers(),
        streaming=True,
    )

    assert isinstance(registry.resolve("foundry_local"), FoundryLocalRuntime)


def test_foundry_projection_does_not_send_reasoning_effort_with_tools(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "high")

    projection = build_openai_projection(
        provider="foundry_local",
        model="phi-4-mini-reasoning",
        transport="chat_completions",
        messages=[{"role": "user", "content": "solve this"}],
        send_tools=True,
        compaction_threshold=4096,
    )

    assert projection.options["tool_choice"] == "auto"
    assert "reasoning_effort" not in projection.options
    assert projection.effort_used == "high"


def test_openai_projection_still_disables_reasoning_when_tools_are_sent(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "high")

    projection = build_openai_projection(
        provider="openai",
        model="gpt-test",
        transport="chat_completions",
        messages=[{"role": "user", "content": "solve this"}],
        send_tools=True,
        compaction_threshold=4096,
    )

    assert projection.options["reasoning_effort"] == "none"
