from types import SimpleNamespace

from uagent.providers.inception_runtime import InceptionProviderRuntime
from uagent.runtime.round_contracts import ContextPlan, RoundIdentifiers
from uagent.runtime.round_identity import (
    DeterministicTestWorkspaceKeyProvider,
    RoundIdentityFactory,
)


class _Cancellation:
    def is_cancelled(self):
        return False


class _Completions:
    def create(self, **kwargs):
        self.kwargs = kwargs
        return []


def _identifiers():
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 0)


def test_inception_runtime_projects_serializes_and_emits_events() -> None:
    completions = _Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    runtime = InceptionProviderRuntime(
        client=client, model="mercury", identifiers=_identifiers()
    )
    plan = ContextPlan("plan", ({"role": "user", "content": "hello"},))

    identity_factory = RoundIdentityFactory(
        workspace_id="test", key_provider=DeterministicTestWorkspaceKeyProvider()
    )
    projection = runtime.project(plan, {"identity_factory": identity_factory})
    request = runtime.serialize(projection)
    events = list(runtime.run(request, _Cancellation()))

    assert request.payload["model"] == "mercury"
    assert completions.kwargs["stream"] is True
    assert [event.type for event in events] == ["ResponseStarted", "ResponseCompleted"]
