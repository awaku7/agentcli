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
    assert deepseek_chat_usage_to_dict(
        {
            "prompt_tokens": True,
            "completion_tokens": 5,
            "completion_tokens_details": {"reasoning_tokens": 6},
        }
    ) == {}
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


def test_deepseek_legacy_stream_keeps_only_successful_final_usage() -> None:
    core = SimpleNamespace(_last_responses_usage={"input_tokens": 999})
    parse_deepseek_stream(
        [_chunk(text="a"), _chunk(usage=_usage())],
        core=core,
        callbacks=_callbacks(),
        capture_usage=True,
    )
    assert core._last_responses_usage == _expected()

    previous = core._last_responses_usage

    def failed_stream():
        yield _chunk(text="b", usage=_usage())
        raise RuntimeError("broken stream")

    parse_deepseek_stream(
        failed_stream(),
        core=core,
        callbacks=_callbacks(),
        capture_usage=True,
    )
    assert core._last_responses_usage is previous


def test_deepseek_legacy_round_requests_final_usage_without_affecting_mimo(
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
            assert core._last_responses_usage == {"input_tokens": 999}
