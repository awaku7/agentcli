from __future__ import annotations

from types import SimpleNamespace

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
