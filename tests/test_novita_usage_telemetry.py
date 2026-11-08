"""Novita usage telemetry and stream ownership regression tests."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.llm_novita import _parse_novita_stream, novita_chat_with_tools
from uagent.providers.llm_novita_usage import (
    novita_chat_usage_to_dict,
    request_novita_stream_usage,
)
from uagent.runtime.stream_renderer import StreamCallbacks


class _Client:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _usage():
    return SimpleNamespace(
        prompt_tokens=90,
        completion_tokens=25,
        total_tokens=115,
        prompt_tokens_details=SimpleNamespace(
            cached_tokens=20, cache_write_tokens=10
        ),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=7),
    )


def _expected():
    return {
        "input_tokens": 90,
        "output_tokens": 25,
        "total_tokens": 115,
        "cache_read_input_tokens": 20,
        "cache_write_input_tokens": 10,
        "reasoning_output_tokens": 7,
    }


def _chunk(*, content=None, usage=None, tool_calls=None):
    delta = SimpleNamespace(
        content=content, reasoning_content=None, tool_calls=tool_calls or []
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta)] if content is not None or tool_calls else [],
        usage=usage,
    )


def _callbacks():
    return StreamCallbacks(on_delta=lambda _text: None, on_reasoning=lambda _text: None)


def _round(monkeypatch, client, core, *, stream=True, wait=None):
    monkeypatch.setattr(
        "uagent.providers.llm_novita.build_novita_chat_kwargs",
        lambda **_kwargs: ({"model": "test-model", "messages": []}, None),
    )
    return novita_chat_with_tools(
        client=client,
        depname="test-model",
        call_messages=[],
        core=core,
        make_client_fn=lambda _core: (None, client),
        call_maybe_thread_fn=wait or (lambda fn: fn()),
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        stream=stream,
        callbacks=_callbacks(),
    )


def test_novita_native_openai_sdk_accepts_stream_options() -> None:
    from inspect import signature

    from openai.resources.chat.completions import Completions

    assert "stream_options" in signature(Completions.create).parameters


def test_novita_measured_counts_and_subsets() -> None:
    assert novita_chat_usage_to_dict(_usage()) == _expected()
    assert novita_chat_usage_to_dict(
        {"prompt_tokens": 12, "completion_tokens": 5}
    ) == {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}
    assert novita_chat_usage_to_dict(
        {
            "prompt_tokens": 4,
            "completion_tokens": 0,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "cache_write_tokens": 0,
            },
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
    ) == {
        "input_tokens": 4,
        "output_tokens": 0,
        "total_tokens": 4,
        "cache_read_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "reasoning_output_tokens": 0,
    }


def test_novita_missing_invalid_and_inconsistent_values() -> None:
    assert novita_chat_usage_to_dict(None) == {}
    assert novita_chat_usage_to_dict({"completion_tokens": 3}) == {
        "output_tokens": 3
    }
    assert novita_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 999,
            "prompt_tokens_details": {
                "cached_tokens": 11,
                "cache_write_tokens": 20,
            },
            "completion_tokens_details": {"reasoning_tokens": 6},
        }
    ) == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert novita_chat_usage_to_dict(
        {"prompt_tokens": True, "completion_tokens": -1}
    ) == {}
    assert novita_chat_usage_to_dict(
        {"prompt_tokens": 10**12, "completion_tokens": 2}
    ) == {"input_tokens": 10**12, "output_tokens": 2}


def test_novita_stream_option_preserves_caller_choices() -> None:
    payload = {
        "stream_options": {"include_usage": False, "include_obfuscation": False}
    }
    request_novita_stream_usage(payload)
    assert payload["stream_options"] == {
        "include_usage": False,
        "include_obfuscation": False,
    }


def test_novita_usage_only_terminal_chunk_is_collected_not_published() -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    sink: list[dict[str, int]] = []
    text, _reasoning, _tools = _parse_novita_stream(
        [_chunk(content="answer"), _chunk(usage=_usage())],
        core=core,
        callbacks=_callbacks(),
        usage_sink=sink,
    )
    assert text == "answer"
    assert sink == [_expected()]
    assert core._last_responses_usage is previous


def test_novita_stream_drops_partial_measurement_on_error() -> None:
    def interrupted():
        yield _chunk(content="partial", usage=_usage())
        raise RuntimeError("connection dropped")

    sink: list[dict[str, int]] = []
    _parse_novita_stream(
        interrupted(), callbacks=_callbacks(), usage_sink=sink
    )
    assert sink == []


def test_novita_stream_round_requests_usage_and_publishes(monkeypatch) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer"), _chunk(usage=_usage())])

    result = _round(monkeypatch, client, core)

    assert result[0] is True
    assert result[2] == "answer"
    assert client.calls[0]["stream"] is True
    assert client.calls[0]["stream_options"] == {"include_usage": True}
    assert core._last_responses_usage == _expected()
    assert core._last_responses_usage is not previous


def test_novita_nonstream_round_publishes_usage(monkeypatch) -> None:
    core = SimpleNamespace(_last_responses_usage={})
    resp = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="answer", reasoning_content="", tool_calls=[]
                )
            )
        ],
        usage=_usage(),
    )
    client = _Client(resp)

    result = _round(monkeypatch, client, core, stream=False)

    assert result[0] is True
    assert result[2] == "answer"
    assert "stream_options" not in client.calls[0]
    assert core._last_responses_usage == _expected()


def test_novita_stream_without_usage_keeps_old_snapshot(monkeypatch) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer")])

    result = _round(monkeypatch, client, core)

    assert result[0] is True
    assert core._last_responses_usage is previous


def test_novita_interrupted_wait_does_not_publish_worker_usage(monkeypatch) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer"), _chunk(usage=_usage())])

    def interrupted_wait(fn):
        fn()
        raise RuntimeError("caller interrupted")

    result = _round(monkeypatch, client, core, wait=interrupted_wait)

    assert result[0] is False
    assert core._last_responses_usage is previous


def test_novita_stream_preserves_tool_calls() -> None:
    tc = SimpleNamespace(
        index=0,
        id="tool_1",
        function=SimpleNamespace(name="lookup", arguments='{"q":1}'),
    )
    result = _parse_novita_stream(
        [_chunk(tool_calls=[tc]), _chunk(usage=_usage())],
        callbacks=_callbacks(),
        usage_sink=[],
    )
    assert result[2] == [
        {
            "id": "tool_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"q":1}'},
        }
    ]
