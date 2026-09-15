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
    _try_registry_simple_chat_round,
    _record_responses_runtime_response,
    _record_round_context_plan,
)
from uagent.llm_helpers import _env_default_on


def test_registry_simple_chat_round_is_opt_in_and_parity_safe(
    monkeypatch, tmp_path
) -> None:
    class Chat:
        def create(self, **kwargs):
            return iter(
                [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content="registry-ok", tool_calls=[]
                                )
                            )
                        ]
                    )
                ]
            )

    class Client:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=Chat())

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    core = SimpleNamespace(workdir=str(tmp_path), cancellation_token=None)
    result = _try_registry_simple_chat_round(
        provider="openai",
        client=Client(),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "registry-ok", "", [])


def test_registry_tool_round_is_explicitly_opt_in(monkeypatch, tmp_path) -> None:
    class Chat:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return iter(
                [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    tool_calls=[
                                        SimpleNamespace(
                                            index=0,
                                            id="call-1",
                                            function=SimpleNamespace(
                                                name="read_file",
                                                arguments='{"path":"a"}',
                                            ),
                                        )
                                    ],
                                )
                            )
                        ]
                    )
                ]
            )

    chat = Chat()
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_TOOLS", "1")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    core = SimpleNamespace(
        workdir=str(tmp_path),
        cancellation_token=None,
        context_tool_specs=({"type": "function", "function": {"name": "read_file"}},),
        response_format=None,
    )

    result = _try_registry_simple_chat_round(
        provider="openai",
        client=client,
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "read a"}],
        core=core,
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=True,
        round_count=1,
    )

    assert result is not None
    assert result[3][0]["tool_call_id"] == "call-1"
    assert chat.calls[0]["tools"] == list(core.context_tool_specs)


def test_registry_rollout_falls_back_for_multimodal_and_structured_content(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    core = SimpleNamespace(workdir=str(tmp_path), response_format=None)

    assert (
        _try_registry_simple_chat_round(
            provider="openai",
            client=SimpleNamespace(),
            depname="gpt-test",
            call_messages=[{"role": "user", "content": [{"type": "input_image"}]}],
            core=core,
            use_responses_api=False,
            stream_responses=True,
            send_tools_this_round=False,
            round_count=1,
        )
        is None
    )

    core.response_format = {"type": "json_schema"}
    assert (
        _try_registry_simple_chat_round(
            provider="openai",
            client=SimpleNamespace(),
            depname="gpt-test",
            call_messages=[{"role": "user", "content": "hello"}],
            core=core,
            use_responses_api=False,
            stream_responses=True,
            send_tools_this_round=False,
            round_count=1,
        )
        is None
    )


def test_registry_responses_round_updates_legacy_response_state(
    monkeypatch, tmp_path
) -> None:
    class Responses:
        def create(self, **kwargs):
            return iter(
                [
                    SimpleNamespace(type="response.output_text.delta", delta="hello"),
                    SimpleNamespace(
                        type="response.completed",
                        response=SimpleNamespace(id="resp_new"),
                    ),
                ]
            )

    class Client:
        def __init__(self) -> None:
            self.responses = Responses()

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_RESPONSES", "1")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    core = SimpleNamespace(
        workdir=str(tmp_path),
        cancellation_token=None,
        responses_state={},
        responses_runtime=None,
    )
    result = _try_registry_simple_chat_round(
        provider="openai",
        client=Client(),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        use_responses_api=True,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "hello", "", [])
    assert core.responses_state["previous_response_id"] == "resp_new"


def test_round_contract_flags_are_on_by_default_and_opt_out_explicitly(
    monkeypatch,
) -> None:
    monkeypatch.delenv("UAGENT_ROUND_CONTRACTS", raising=False)
    monkeypatch.delenv("UAGENT_ROUND_ORCHESTRATOR", raising=False)
    assert _env_default_on("UAGENT_ROUND_CONTRACTS") is True
    assert _env_default_on("UAGENT_ROUND_ORCHESTRATOR") is True

    monkeypatch.setenv("UAGENT_ROUND_CONTRACTS", "0")
    monkeypatch.setenv("UAGENT_ROUND_ORCHESTRATOR", "off")
    assert _env_default_on("UAGENT_ROUND_CONTRACTS") is False
    assert _env_default_on("UAGENT_ROUND_ORCHESTRATOR") is False


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
