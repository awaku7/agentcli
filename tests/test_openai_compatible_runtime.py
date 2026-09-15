from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime
from uagent.runtime.context_plan_builder import build_context_plan
from uagent.runtime.round_contracts import RoundIdentifiers, validate_stream_events
from uagent.runtime.round_identity import (
    DeterministicTestWorkspaceKeyProvider,
    RoundIdentityFactory,
)


class _Cancellation:
    def __init__(self, cancelled: bool = False) -> None:
        self.cancelled = cancelled

    def is_cancelled(self) -> bool:
        return self.cancelled


class _Chat:
    def __init__(self, chunks) -> None:
        self.chunks = chunks
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.chunks)


class _Responses:
    def __init__(self, events) -> None:
        self.events = events
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.events)


class _Client:
    def __init__(self, *, chunks=(), events=()) -> None:
        self.chat = SimpleNamespace(completions=_Chat(chunks))
        self.responses = _Responses(events)


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1)


def _plan() -> object:
    return build_context_plan(
        workspace_id="test-workspace",
        messages=[
            {
                "role": "user",
                "content": "hello",
                "_uagent_internal": "remove",
            }
        ],
        policy={"provider": "openai", "model": "gpt-test"},
        key_provider=DeterministicTestWorkspaceKeyProvider(),
    )


def test_chat_runtime_projects_and_normalizes_events() -> None:
    chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="hello", tool_calls=[]))]
    )
    client = _Client(chunks=[chunk])
    runtime = OpenAICompatibleRuntime(
        client=client,
        provider="openai",
        model="gpt-test",
        identifiers=_identifiers(),
    )
    plan = _plan()
    projection = runtime.project(
        plan,
        {
            "identity_factory": RoundIdentityFactory(
                "test-workspace", DeterministicTestWorkspaceKeyProvider()
            )
        },
    )
    request = runtime.serialize(projection)
    events = list(runtime.run(request, _Cancellation()))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert "_uagent_internal" not in request.payload["messages"][0]
    assert client.chat.completions.calls[0]["model"] == "gpt-test"


def test_responses_runtime_normalizes_text_and_completion() -> None:
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(type="response.completed"),
    ]
    client = _Client(events=events)
    runtime = OpenAICompatibleRuntime(
        client=client,
        provider="azure",
        model="gpt-test",
        identifiers=_identifiers(),
        transport="responses",
    )
    plan = _plan()
    factory = RoundIdentityFactory(
        "test-workspace", DeterministicTestWorkspaceKeyProvider()
    )
    request = runtime.serialize(runtime.project(plan, {"identity_factory": factory}))
    normalized = list(runtime.run(request, _Cancellation()))

    validate_stream_events(normalized)
    assert [event.type for event in normalized] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert client.responses.calls[0]["model"] == "gpt-test"


def test_runtime_cancellation_is_terminal() -> None:
    client = _Client(chunks=[])
    runtime = OpenAICompatibleRuntime(
        client=client,
        provider="openai",
        model="gpt-test",
        identifiers=_identifiers(),
    )
    plan = _plan()
    factory = RoundIdentityFactory(
        "test-workspace", DeterministicTestWorkspaceKeyProvider()
    )
    request = runtime.serialize(runtime.project(plan, {"identity_factory": factory}))
    normalized = list(runtime.run(request, _Cancellation(cancelled=True)))

    validate_stream_events(normalized)
    assert normalized[-1].type == "ResponseCancelled"
