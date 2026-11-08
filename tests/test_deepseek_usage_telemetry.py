"""Provider-reported DeepSeek usage on registry and legacy chat routes."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.llm_deepseek import (
    deepseek_chat_with_tools,
    parse_deepseek_stream,
)
from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime
from uagent.runtime.round_contracts import (
    RoundIdentifiers,
    SerializedRequest,
    validate_stream_events,
)
from uagent.runtime.stream_renderer import StreamCallbacks
from uagent.runtime.telemetry import deepseek_chat_usage_to_dict


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False


class _CancelAfter:
    def __init__(self, checks: int) -> None:
        self.checks = checks

    def is_cancelled(self) -> bool:
        self.checks -= 1
        return self.checks < 0


class _Client:
    def __init__(self, result) -> None:
        self.result = result
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def _usage():
    return SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=35,
        total_tokens=135,
        prompt_cache_hit_tokens=30,
        prompt_cache_miss_tokens=70,
        prompt_tokens_details=SimpleNamespace(cached_tokens=30),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=15),
    )


def _expected():
    return {
        "input_tokens": 100,
        "output_tokens": 35,
        "total_tokens": 135,
        "cache_read_input_tokens": 30,
        "reasoning_output_tokens": 15,
    }


def _chunk(*, text=None, usage=None):
    choices = (
        [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=text, reasoning_content=None, tool_calls=[]
                )
            )
        ]
        if text is not None
        else []
    )
    return SimpleNamespace(choices=choices, usage=usage)


def _request():
    return SerializedRequest(
        identifiers=RoundIdentifiers(
            "turn", "round", "attempt", "request", "stream", 1
        ),
        plan_id="plan",
        projection_id="projection",
        provider="deepseek",
        model="deepseek-test",
        payload={"model": "deepseek-test", "messages": [], "tools": []},
    )


def _runtime(client, *, streaming=True):
    return OpenAICompatibleRuntime(
        client=client,
        provider="deepseek",
        model="deepseek-test",
        identifiers=_request().identifiers,
        streaming=streaming,
    )


def _callbacks():
    return StreamCallbacks(
        on_delta=lambda _text: None,
        on_reasoning=lambda _text: None,
    )


def test_deepseek_usage_cache_and_reasoning_are_subsets() -> None:
    assert deepseek_chat_usage_to_dict(_usage()) == _expected()
    assert deepseek_chat_usage_to_dict(
        {"prompt_tokens": 10, "completion_tokens": 2}
    ) == {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    assert deepseek_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 10,
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
    ) == {
        "input_tokens": 10,
        "output_tokens": 0,
        "total_tokens": 10,
        "cache_read_input_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    assert deepseek_chat_usage_to_dict(
        {"prompt_tokens": 10, "prompt_tokens_details": {"cached_tokens": 4}}
    ) == {"input_tokens": 10, "cache_read_input_tokens": 4}


def test_deepseek_usage_rejects_malformed_and_inconsistent_subsets() -> None:
    assert deepseek_chat_usage_to_dict(None) == {}
    assert deepseek_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_cache_hit_tokens": 15,
        }
    ) == {"output_tokens": 5}
    assert deepseek_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_cache_hit_tokens": 3,
            "prompt_cache_miss_tokens": 8,
        }
    ) == {"output_tokens": 5}
    assert deepseek_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_cache_hit_tokens": 3,
            "prompt_tokens_details": {"cached_tokens": 4},
        }
    ) == {"output_tokens": 5}
    assert (
        deepseek_chat_usage_to_dict(
            {
                "prompt_tokens": True,
                "completion_tokens": 5,
                "completion_tokens_details": {"reasoning_tokens": 6},
            }
        )
        == {}
    )
    assert deepseek_chat_usage_to_dict(
        {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "completion_tokens_details": {"reasoning_tokens": -1},
        }
    ) == {"input_tokens": 5}


def test_deepseek_registry_stream_reports_last_usage_including_empty_choices() -> None:
    client = _Client([_chunk(text="answer"), _chunk(usage=_usage())])
    events = list(_runtime(client).run(_request(), _Cancellation()))
    validate_stream_events(events)
    assert [e.type for e in events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert events[-1].data == {"usage": _expected()}
    assert client.calls[0]["stream_options"] == {"include_usage": True}


def test_deepseek_registry_nonstream_reports_usage() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="answer", tool_calls=[]))
        ],
        usage=_usage(),
    )
    client = _Client(response)
    events = list(_runtime(client, streaming=False).run(_request(), _Cancellation()))
    assert events[-1].type == "ResponseCompleted"
    assert events[-1].data == {"usage": _expected()}
    assert "stream_options" not in client.calls[0]


def test_deepseek_registry_cancel_and_error_never_export_partial_usage() -> None:
    client = _Client([_chunk(text="a", usage=_usage()), _chunk(text="b")])
    events = list(_runtime(client).run(_request(), _CancelAfter(2)))
    assert events[-1].type == "ResponseCancelled"
    assert "usage" not in events[-1].data

    def failed_stream():
        yield _chunk(text="a", usage=_usage())
        raise RuntimeError("broken stream")

    events = list(_runtime(_Client(failed_stream())).run(_request(), _Cancellation()))
    assert events[-1].type == "ResponseFailed"
    assert "usage" not in events[-1].data


def test_deepseek_legacy_stream_keeps_usage_local_until_owner_returns() -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    snapshots: list[dict[str, int]] = []
    parse_deepseek_stream(
        [_chunk(text="a"), _chunk(usage=_usage())],
        core=core,
        callbacks=_callbacks(),
        usage_sink=snapshots,
    )
    assert snapshots == [_expected()]
    # Worker must not touch the shared core, even if its owner was interrupted.
    assert core._last_responses_usage is previous

    def failed_stream():
        yield _chunk(text="b", usage=_usage())
        raise RuntimeError("broken stream")

    failed_snapshots: list[dict[str, int]] = []
    parse_deepseek_stream(
        failed_stream(),
        core=core,
        callbacks=_callbacks(),
        usage_sink=failed_snapshots,
    )
    assert failed_snapshots == []
    assert core._last_responses_usage is previous


def test_deepseek_and_mimo_legacy_stream_usage_with_provider_safe_options(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "uagent.providers.llm_deepseek.build_deepseek_chat_kwargs",
        lambda **_kwargs: ({"model": "test", "messages": []}, None),
    )
    monkeypatch.setattr(
        "uagent.providers.llm_deepseek.native_structured_output_request_for_runtime",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("uagent.providers.llm_deepseek.env_get", lambda _name: "")

    for provider in ("deepseek", "mimo"):
        core = SimpleNamespace(_last_responses_usage={"input_tokens": 999})
        client = _Client([_chunk(text="answer"), _chunk(usage=_usage())])
        result = deepseek_chat_with_tools(
            client=client,
            depname="test",
            call_messages=[],
            core=core,
            make_client_fn=lambda _core: (None, client),
            call_maybe_thread_fn=lambda fn: fn(),
            send_tools_this_round=False,
            max_retries_429=0,
            retry_base=0.0,
            retry_cap=0.0,
            stream=True,
            provider=provider,
            callbacks=_callbacks(),
        )
        assert result[0] is True
        if provider == "deepseek":
            assert client.calls[0]["stream_options"] == {"include_usage": True}
            assert core._last_responses_usage == _expected()
        else:
            assert "stream_options" not in client.calls[0]
            assert core._last_responses_usage == _expected()


def test_mimo_legacy_nonstream_uses_reported_usage(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.llm_deepseek.build_deepseek_chat_kwargs",
        lambda **_kwargs: ({"model": "mimo", "messages": []}, None),
    )
    monkeypatch.setattr(
        "uagent.providers.llm_deepseek.native_structured_output_request_for_runtime",
        lambda *_args, **_kwargs: None,
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="answer", reasoning_content=None, tool_calls=[]
                )
            )
        ],
        usage=_usage(),
    )
    previous = {"input_tokens": 900}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client(response)
    result = deepseek_chat_with_tools(
        client=client,
        depname="mimo-v2.6-pro",
        call_messages=[],
        core=core,
        make_client_fn=lambda _core: (None, client),
        call_maybe_thread_fn=lambda fn: fn(),
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        stream=False,
        provider="mimo",
        callbacks=_callbacks(),
    )
    assert result[0] is True
    assert "stream_options" not in client.calls[0]
    assert core._last_responses_usage == _expected()
    assert core._last_responses_usage is not previous


def test_mimo_stream_error_does_not_publish_partial_usage(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.llm_deepseek.build_deepseek_chat_kwargs",
        lambda **_kwargs: ({"model": "mimo", "messages": []}, None),
    )
    monkeypatch.setattr(
        "uagent.providers.llm_deepseek.native_structured_output_request_for_runtime",
        lambda *_args, **_kwargs: None,
    )

    def broken_stream():
        yield _chunk(text="partial", usage=_usage())
        raise OSError("stream interrupted")

    previous = {"input_tokens": 900}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client(broken_stream())
    result = deepseek_chat_with_tools(
        client=client,
        depname="mimo-v2.6-pro",
        call_messages=[],
        core=core,
        make_client_fn=lambda _core: (None, client),
        call_maybe_thread_fn=lambda fn: fn(),
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        stream=True,
        provider="mimo",
        callbacks=_callbacks(),
    )
    assert result[0] is True
    assert core._last_responses_usage is previous
    assert "stream_options" not in client.calls[0]
