from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.openai_projection_policy import build_openai_projection
from uagent.runtime.round_identity import DeterministicTestWorkspaceKeyProvider
from uagent.uagent_llm import _try_registry_simple_chat_round


def _patch_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )
    monkeypatch.setattr("uagent.llmcapa_util.clamp_max_tokens", lambda *args: 321)
    monkeypatch.setattr("uagent.uagent_llm._get_shrink_max_tokens", lambda _: 654)


def test_registry_projects_chat_generation_options(monkeypatch, tmp_path) -> None:
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
                                delta=SimpleNamespace(content="ok", tool_calls=[])
                            )
                        ]
                    )
                ]
            )

    chat = Chat()
    _patch_identity(monkeypatch)
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setenv("UAGENT_MAX_TOKENS", "999")
    monkeypatch.setenv("UAGENT_TOP_P", "0.3")
    monkeypatch.setenv("UAGENT_OPENAI_FAST_MODE", "1")
    core = SimpleNamespace(
        workdir=str(tmp_path),
        cancellation_token=None,
        context_tool_specs=({"type": "function", "function": {"name": "read_file"}},),
    )

    result = _try_registry_simple_chat_round(
        provider="openai",
        client=SimpleNamespace(chat=SimpleNamespace(completions=chat)),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=True,
        round_count=1,
    )

    assert result == (True, "ok", "", [])
    payload = chat.calls[0]
    assert payload["max_tokens"] == 321
    assert payload["top_p"] == 0.3
    assert payload["service_tier"] == "fast"
    assert payload["tool_choice"] == "auto"
    assert payload["reasoning_effort"] == "none"


def test_registry_projects_azure_chat_structured_output(monkeypatch, tmp_path) -> None:
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
                                delta=SimpleNamespace(content="{}", tool_calls=[])
                            )
                        ]
                    )
                ]
            )

    chat = Chat()
    _patch_identity(monkeypatch)
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "1")
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_schema", lambda *args: True)
    core = SimpleNamespace(workdir=str(tmp_path), cancellation_token=None)
    messages = [
        {
            "role": "system",
            "content": (
                "response_mode: json\n\nresponse_schema:\n"
                '{"type":"object","properties":{"ok":{"type":"boolean"}}}'
            ),
        },
        {"role": "user", "content": "return JSON"},
    ]

    result = _try_registry_simple_chat_round(
        provider="azure",
        client=SimpleNamespace(chat=SimpleNamespace(completions=chat)),
        depname="gpt-test",
        call_messages=messages,
        core=core,
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "{}", "", [])
    assert chat.calls[0]["response_format"]["type"] == "json_schema"


def test_registry_projects_azure_responses_structured_output(
    monkeypatch, tmp_path
) -> None:
    class Responses:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return iter(
                [
                    SimpleNamespace(type="response.output_text.delta", delta="{}"),
                    SimpleNamespace(
                        type="response.completed",
                        response=SimpleNamespace(id="resp_structured"),
                    ),
                ]
            )

    responses = Responses()
    _patch_identity(monkeypatch)
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "1")
    monkeypatch.setattr("uagent.llmcapa_util.supports_json_schema", lambda *args: True)
    core = SimpleNamespace(
        workdir=str(tmp_path), cancellation_token=None, responses_state={}
    )
    messages = [
        {
            "role": "system",
            "content": (
                "response_mode: json\n\nresponse_schema:\n"
                '{"type":"object","properties":{"ok":{"type":"boolean"}}}'
            ),
        },
        {"role": "user", "content": "return JSON"},
    ]

    result = _try_registry_simple_chat_round(
        provider="azure",
        client=SimpleNamespace(responses=responses),
        depname="gpt-test",
        call_messages=messages,
        core=core,
        use_responses_api=True,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "{}", "", [])
    assert responses.calls[0]["text"]["format"]["type"] == "json_schema"


def test_registry_azure_responses_tool_continuation_preserves_call_id(
    monkeypatch, tmp_path
) -> None:
    class Responses:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return iter(
                [
                    SimpleNamespace(
                        type="response.output_item.added",
                        item=SimpleNamespace(
                            type="function_call",
                            id="item-1",
                            call_id="call-1",
                            name="read_file",
                        ),
                    ),
                    SimpleNamespace(
                        type="response.function_call_arguments.delta",
                        item_id="item-1",
                        delta='{"path":"a"}',
                    ),
                    SimpleNamespace(
                        type="response.completed",
                        response=SimpleNamespace(id="resp_next"),
                    ),
                ]
            )

    responses = Responses()
    _patch_identity(monkeypatch)
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_TOOLS", "1")
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_RESPONSES", "1")
    core = SimpleNamespace(
        workdir=str(tmp_path),
        cancellation_token=None,
        responses_state={"previous_response_id": "resp_prev"},
        context_tool_specs=({"type": "function", "function": {"name": "read_file"}},),
    )

    result = _try_registry_simple_chat_round(
        provider="azure",
        client=SimpleNamespace(responses=responses),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "read a"}],
        core=core,
        use_responses_api=True,
        stream_responses=True,
        send_tools_this_round=True,
        round_count=1,
    )

    assert result is not None
    assert result[3][0]["tool_call_id"] == "call-1"
    assert responses.calls[0]["previous_response_id"] == "resp_prev"
    assert core.responses_state["previous_response_id"] == "resp_next"


def test_registry_projects_responses_generation_options(monkeypatch, tmp_path) -> None:
    class Responses:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return iter(
                [
                    SimpleNamespace(type="response.output_text.delta", delta="ok"),
                    SimpleNamespace(
                        type="response.completed",
                        response=SimpleNamespace(id="resp_1"),
                    ),
                ]
            )

    responses = Responses()
    _patch_identity(monkeypatch)
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setenv("UAGENT_VERBOSITY", "low")
    monkeypatch.setenv("UAGENT_MAX_TOKENS", "999")
    monkeypatch.setenv("UAGENT_OPENAI_FAST_MODE", "1")
    core = SimpleNamespace(
        workdir=str(tmp_path), cancellation_token=None, responses_state={}
    )

    result = _try_registry_simple_chat_round(
        provider="azure",
        client=SimpleNamespace(responses=responses),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        use_responses_api=True,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "ok", "", [])
    payload = responses.calls[0]
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["text"] == {"verbosity": "low"}
    assert payload["max_output_tokens"] == 321
    assert payload["context_management"] == [
        {"type": "compaction", "compact_threshold": 654}
    ]
    assert "service_tier" not in payload


def test_projection_policy_is_pure_and_keeps_transport_shapes(monkeypatch) -> None:
    messages = [{"role": "user", "content": "hello"}]
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setenv("UAGENT_MAX_TOKENS", "999")
    monkeypatch.setenv("UAGENT_TOP_P", "0.3")
    monkeypatch.setattr("uagent.llmcapa_util.clamp_max_tokens", lambda *args: 321)

    projection = build_openai_projection(
        provider="openai",
        model="gpt-test",
        transport="chat_completions",
        messages=messages,
        send_tools=False,
        compaction_threshold=654,
    )

    assert messages == [{"role": "user", "content": "hello"}]
    assert projection.reasoning == "high"
    assert projection.effort_used == "high"
    assert projection.options == {
        "reasoning_effort": "high",
        "max_tokens": 321,
        "top_p": 0.3,
    }
