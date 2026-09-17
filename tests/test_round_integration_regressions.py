from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.capability_resolver import CapabilityResolver, CapabilityState
from uagent.runtime.context_manager import ContextManager
from uagent.runtime.context_policy import ContextPolicy
from uagent.runtime.round_contracts import ContextPlan
from uagent.runtime.context_plan_builder import build_context_plan
from uagent.runtime.message_transform import MessageTransformPipeline
from uagent.runtime.provider_context import project_messages_for_provider
from uagent.runtime.round_identity import DeterministicTestWorkspaceKeyProvider
from uagent.runtime.round_runtime import RoundAttemptBudget
from uagent.uagent_llm import (
    _begin_responses_runtime,
    _sync_registry_responses_terminal,
    _try_registry_simple_chat_round,
    _record_responses_runtime_response,
    _record_round_context_plan,
    _responses_session_generation,
)
from uagent.llm_helpers import _env_default_on
from uagent.llm_round_helpers import _inception_registry_enabled


def test_registry_simple_chat_round_is_default_on_and_parity_safe(
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

    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY", raising=False)
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_RESPONSES", raising=False)
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_TOOLS", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "off")
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

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "off")
    assert (
        _try_registry_simple_chat_round(
            provider="openai",
            client=Client(),
            depname="gpt-test",
            call_messages=[{"role": "user", "content": "hello"}],
            core=core,
            use_responses_api=False,
            stream_responses=True,
            send_tools_this_round=False,
            round_count=2,
        )
        is None
    )


def test_registry_chat_round_supports_non_streaming_mode(monkeypatch, tmp_path) -> None:
    class Chat:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="registry-ok", tool_calls=[])
                    )
                ]
            )

    chat = Chat()
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    result = _try_registry_simple_chat_round(
        provider="openai",
        client=SimpleNamespace(chat=SimpleNamespace(completions=chat)),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=SimpleNamespace(workdir=str(tmp_path), cancellation_token=None),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "registry-ok", "", [])
    assert chat.calls[0]["stream"] is False


def test_registry_tool_round_is_default_on(monkeypatch, tmp_path) -> None:
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
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_TOOLS", raising=False)
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


def test_registry_round_supports_multimodal_content_and_structured_output(
    monkeypatch, tmp_path
) -> None:
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
                                    content="registry-ok", tool_calls=[]
                                )
                            )
                        ]
                    )
                ]
            )

    chat = Chat()
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    monkeypatch.setattr(
        "uagent.providers.structured_output.native_structured_output_request",
        lambda *args, **kwargs: {"type": "json_object"},
    )
    core = SimpleNamespace(workdir=str(tmp_path), cancellation_token=None)
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))

    result = _try_registry_simple_chat_round(
        provider="openai",
        client=client,
        depname="gpt-test",
        call_messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe this image"},
                    {"type": "image_url", "image_url": {"url": "https://x/y.png"}},
                ],
            }
        ],
        core=core,
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "registry-ok", "", [])
    assert chat.calls[0]["messages"][0]["content"][1]["type"] == "image_url"
    assert chat.calls[0]["response_format"] == {"type": "json_object"}


def test_registry_responses_round_updates_legacy_response_state(
    monkeypatch, tmp_path
) -> None:
    class Responses:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
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
            self.responses = responses

    responses = Responses()
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "low")
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_RESPONSES", raising=False)
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
    assert responses.calls[0]["reasoning"] == {"effort": "low"}
    assert "reasoning_effort" not in responses.calls[0]


def test_registry_responses_tool_round_continues_after_output(
    monkeypatch, tmp_path
) -> None:
    class Responses:
        def __init__(self) -> None:
            self.calls = []
            self.streams = [
                [
                    SimpleNamespace(
                        type="response.output_item.added",
                        item=SimpleNamespace(
                            type="function_call",
                            id="fc_1",
                            call_id="call_1",
                            name="read_file",
                            arguments="",
                        ),
                    ),
                    SimpleNamespace(
                        type="response.function_call_arguments.delta",
                        item_id="fc_1",
                        delta='{"path":"a"}',
                    ),
                    SimpleNamespace(
                        type="response.completed",
                        response=SimpleNamespace(id="resp_1"),
                    ),
                ],
                [
                    SimpleNamespace(
                        type="response.completed",
                        response=SimpleNamespace(id="resp_2"),
                    )
                ],
            ]

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return iter(self.streams.pop(0))

    responses = Responses()
    client = SimpleNamespace(responses=responses)
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY", raising=False)
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_RESPONSES", raising=False)
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_TOOLS", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    core = SimpleNamespace(
        workdir=str(tmp_path),
        cancellation_token=None,
        responses_state={},
        context_tool_specs=({"type": "function", "function": {"name": "read_file"}},),
    )
    runtime = _begin_responses_runtime(
        core=core, provider="openai", model="gpt-test", enabled=True
    )
    assert runtime is not None

    first = _try_registry_simple_chat_round(
        provider="openai",
        client=client,
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "read a"}],
        core=core,
        use_responses_api=True,
        stream_responses=True,
        send_tools_this_round=True,
        round_count=1,
    )

    assert first is not None
    assert first[3][0]["tool_call_id"] == "call_1"
    assert runtime.state == "AwaitingToolOutput"
    runtime.accept_tool_output("resp_1", "call_1", {"content": "ok"})
    assert runtime.state == "Continuing"

    second = _try_registry_simple_chat_round(
        provider="openai",
        client=client,
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "continue"}],
        core=core,
        use_responses_api=True,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=2,
    )

    assert second == (True, "", "", [])
    assert responses.calls[1]["previous_response_id"] == "resp_1"
    assert core.responses_state["previous_response_id"] == "resp_2"
    assert runtime.state == "Fresh"


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


def test_inception_registry_has_independent_opt_out(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_ROUND_ORCHESTRATOR", raising=False)
    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY_INCEPTION", raising=False)
    assert _inception_registry_enabled() is True

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_INCEPTION", "off")
    assert _inception_registry_enabled() is False

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_INCEPTION", "1")
    monkeypatch.setenv("UAGENT_ROUND_ORCHESTRATOR", "0")
    assert _inception_registry_enabled() is False


def test_registry_response_terminal_clears_persisted_continuation() -> None:
    for status in ("cancelled", "timed_out", "interrupted", "failed"):
        core = SimpleNamespace(
            responses_state={
                "previous_response_id": "resp_1",
                "active_response_id": "resp_1",
                "_stale_rid_occurred": True,
            }
        )

        _sync_registry_responses_terminal(core, status)

        assert "previous_response_id" not in core.responses_state
        assert "active_response_id" not in core.responses_state
        assert "_stale_rid_occurred" not in core.responses_state
        assert core.responses_state["last_response_status"] == status


def test_registry_terminal_sync_clears_runtime_continuation() -> None:
    expected_states = {
        "cancelled": "Cancelled",
        "timed_out": "TimedOut",
        "interrupted": "Interrupted",
        "failed": "Failed",
    }
    for status, expected_state in expected_states.items():
        core = SimpleNamespace(
            responses_state={"previous_response_id": "resp_1"},
        )
        runtime = _begin_responses_runtime(
            core=core, provider="openai", model="gpt-test", enabled=True
        )
        assert runtime is not None
        runtime.record_response("resp_1")

        _sync_registry_responses_terminal(core, status)

        assert runtime.state == expected_state
        assert runtime.previous_response_id is None


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


def test_context_manager_enables_plan_handoff_when_flag_is_off(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_ROUND_CONTRACTS", "0")
    manager = ContextManager(policy=ContextPolicy(provider="openai", model="gpt-test"))
    prepared = ContextPlan("manager-plan", (("role", "user"),))

    def build_context_plan(**kwargs):
        return prepared

    monkeypatch.setattr(manager, "build_context_plan", build_context_plan)
    core = SimpleNamespace(
        context_manager=manager,
        context_plan=None,
        context_tool_specs=(),
        workdir=".",
    )

    plan = _record_round_context_plan(
        provider="openai",
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
    )

    assert plan is prepared
    assert core.context_plan is prepared


def test_registry_round_identifiers_use_responses_session_generation() -> None:
    runtime = SimpleNamespace(session_generation=7)
    core = SimpleNamespace(
        responses_runtime=runtime,
        responses_state={"session_generation": 3},
    )

    assert _responses_session_generation(core) == 7
    assert (
        _responses_session_generation(
            SimpleNamespace(responses_state={"session_generation": 5})
        )
        == 5
    )


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


def test_responses_bridge_restores_persisted_session_generation() -> None:
    core = SimpleNamespace(
        responses_state={
            "previous_response_id": "resp_legacy",
            "session_generation": "7",
        }
    )

    runtime = _begin_responses_runtime(
        core=core, provider="openai", model="gpt-test", enabled=True
    )

    assert runtime is not None
    assert runtime.session_generation == 7
    assert runtime.previous_response_id == "resp_legacy"


def test_message_transform_precedes_projection_without_mutating_history() -> None:
    history = [
        {
            "role": "user",
            "content": "hello" + chr(0xD800),
            "_uagent_internal": "remove only at projection",
            "response_id": "resp_internal",
            "reasoning_content": "internal reasoning",
            "_responses_output_items": [{"type": "reasoning"}],
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
    assert "response_id" not in projected[0]
    assert "reasoning_content" not in projected[0]
    assert "_responses_output_items" not in projected[0]


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


def test_registry_simple_chat_round_supports_azure(monkeypatch, tmp_path) -> None:
    class Chat:
        def create(self, **kwargs):
            return iter(
                [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content="azure-registry-ok", tool_calls=[]
                                )
                            )
                        ]
                    )
                ]
            )

    monkeypatch.delenv("UAGENT_PROVIDER_REGISTRY", raising=False)
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    result = _try_registry_simple_chat_round(
        provider="azure",
        client=SimpleNamespace(chat=SimpleNamespace(completions=Chat())),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=SimpleNamespace(workdir=str(tmp_path), cancellation_token=None),
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "azure-registry-ok", "", [])


def test_registry_allowlist_and_migration_boundary_are_explicit(
    monkeypatch, tmp_path
) -> None:
    core = SimpleNamespace(workdir=str(tmp_path), cancellation_token=None)
    kwargs = {
        "client": object(),
        "depname": "gpt-test",
        "call_messages": [{"role": "user", "content": "hello"}],
        "core": core,
        "use_responses_api": False,
        "stream_responses": True,
        "send_tools_this_round": False,
        "round_count": 1,
    }

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "azure")
    assert _try_registry_simple_chat_round(provider="openai", **kwargs) is None

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "all")
    assert _try_registry_simple_chat_round(provider="gemini", **kwargs) is None
