from __future__ import annotations

from types import SimpleNamespace

from uagent.uagent_llm import _try_registry_simple_chat_round
from uagent.runtime.provider_round_dispatcher import RegistryRoundRoute
from uagent.runtime.round_identity import (
    DeterministicTestWorkspaceKeyProvider,
    RoundIdentityFactory,
)


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False


class _PfnCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(
            [
                {"choices": [{"delta": {"content": "pfn-ok"}}]},
            ]
        )


class _PfnToolCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="call-pfn",
                                function=SimpleNamespace(
                                    name="read_file", arguments='{"path":"a"}'
                                ),
                            )
                        ],
                    )
                )
            ]
        )


class _GrokChat:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stream=lambda: iter(()), sample=lambda: SimpleNamespace()
        )


def _core(tmp_path, *, context_tool_specs=()):
    return SimpleNamespace(
        workdir=str(tmp_path),
        cancellation_token=_Cancellation(),
        context_tool_specs=context_tool_specs,
        responses_state={},
        round_identity_factory=RoundIdentityFactory(
            str(tmp_path), DeterministicTestWorkspaceKeyProvider()
        ),
    )


def test_pfn_registry_route_runs_through_round_orchestrator(tmp_path) -> None:
    completions = _PfnCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = _try_registry_simple_chat_round(
        provider="pfn",
        client=client,
        depname="plamo-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=_core(tmp_path),
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
        registry_route=RegistryRoundRoute(True, "eligible"),
    )

    assert result == (True, "pfn-ok", "", [])
    assert completions.calls[0]["stream"] is True


def test_pfn_registry_tool_call_returns_to_shared_continuation(tmp_path) -> None:
    completions = _PfnToolCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    tool_specs = (
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    )

    result = _try_registry_simple_chat_round(
        provider="pfn",
        client=client,
        depname="plamo-test",
        call_messages=[{"role": "user", "content": "read a"}],
        core=_core(tmp_path, context_tool_specs=tool_specs),
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=True,
        round_count=1,
        registry_route=RegistryRoundRoute(True, "eligible"),
    )

    assert result[0:3] == (True, "", "")
    assert result[3][0]["function"]["name"] == "read_file"
    assert completions.calls[0]["stream"] is False


def test_grok_registry_route_runs_through_round_orchestrator(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )

    def parse_stream(stream, *, callbacks):
        callbacks.on_delta("grok-ok")
        return "grok-ok", []

    monkeypatch.setattr("uagent.providers.grok_runtime.parse_xai_stream", parse_stream)
    chat = _GrokChat()
    client = SimpleNamespace(chat=chat)

    result = _try_registry_simple_chat_round(
        provider="grok",
        client=client,
        depname="grok-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=_core(tmp_path),
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
        registry_route=RegistryRoundRoute(True, "eligible"),
    )

    assert result == (True, "grok-ok", "", [])
    assert chat.calls[0]["messages"] == ["native-message"]


__all__ = []
