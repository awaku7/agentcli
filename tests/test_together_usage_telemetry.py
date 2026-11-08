"""Tests for Together AI SDK usage accounting and stream ownership."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.llm_together import (
    _parse_together_stream,
    together_chat_with_tools,
)
from uagent.runtime.stream_renderer import StreamCallbacks
from uagent.runtime.telemetry import together_chat_usage_to_dict


class _Client:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _usage(*, cached=20, reasoning=7):
    return SimpleNamespace(
        prompt_tokens=90,
        completion_tokens=25,
        total_tokens=115,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
    )


def _expected():
    return {
        "input_tokens": 90,
        "output_tokens": 25,
        "total_tokens": 115,
        "cache_read_input_tokens": 20,
        "reasoning_output_tokens": 7,
    }


def _chunk(*, content=None, usage=None):
    delta = SimpleNamespace(content=content, reasoning_content=None, tool_calls=[])
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta)] if content is not None else [],
        usage=usage,
    )


def _callbacks():
    return StreamCallbacks(
        on_delta=lambda _text: None,
        on_reasoning=lambda _text: None,
    )


def _round(monkeypatch, client, core, *, stream=True, wait=None):
    monkeypatch.setattr(
        "uagent.providers.llm_together.build_together_chat_kwargs",
        lambda **_kwargs: ({"model": "test-model", "messages": []}, None),
    )
    return together_chat_with_tools(
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


def test_together_normalizes_reported_subset_counts() -> None:
    assert together_chat_usage_to_dict(_usage()) == _expected()
    assert together_chat_usage_to_dict(
        {"prompt_tokens": 12, "completion_tokens": 5, "cached_tokens": 4}
    ) == {
        "input_tokens": 12,
        "output_tokens": 5,
        "total_tokens": 17,
        "cache_read_input_tokens": 4,
    }
    assert together_chat_usage_to_dict(
        {
            "prompt_tokens": 5,
            "completion_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
    ) == {
        "input_tokens": 5,
        "output_tokens": 0,
        "total_tokens": 5,
        "cache_read_input_tokens": 0,
        "reasoning_output_tokens": 0,
    }


def test_together_invalid_or_missing_counts_are_not_invented() -> None:
    assert together_chat_usage_to_dict(None) == {}
    assert together_chat_usage_to_dict({"completion_tokens": 2}) == {
        "output_tokens": 2
    }
    assert together_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "cached_tokens": 11,
            "completion_tokens_details": {"reasoning_tokens": 8},
            "total_tokens": 999,
        }
    ) == {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}
    assert together_chat_usage_to_dict(
        {"prompt_tokens": True, "completion_tokens": -3}
    ) == {}
    assert together_chat_usage_to_dict(
        {"prompt_tokens": 10**12, "completion_tokens": 4}
    ) == {"input_tokens": 10**12, "output_tokens": 4}


def test_together_stream_parser_collects_usage_only_final_chunk() -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    usage_sink: list[dict[str, int]] = []
    text, _reasoning, _tools = _parse_together_stream(
        [_chunk(content="answer"), _chunk(usage=_usage())],
        core=core,
        callbacks=_callbacks(),
        usage_sink=usage_sink,
    )
    assert text == "answer"
    assert usage_sink == [_expected()]
    assert core._last_responses_usage is previous


def test_together_stream_drops_partial_usage_if_iteration_fails() -> None:
    def failed_stream():
        yield _chunk(content="partial", usage=_usage())
        raise RuntimeError("network stream failed")

    sink: list[dict[str, int]] = []
    _parse_together_stream(
        failed_stream(),
        callbacks=_callbacks(),
        usage_sink=sink,
    )
    assert sink == []


def test_together_stream_round_requests_and_publishes_usage(monkeypatch) -> None:
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


def test_together_nonstream_round_publishes_usage_without_stream_options(
    monkeypatch,
) -> None:
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


def test_together_missing_terminal_usage_does_not_reuse_old_snapshot(
    monkeypatch,
) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer")])

    result = _round(monkeypatch, client, core)

    assert result[0] is True
    assert core._last_responses_usage is previous


def test_together_abandoned_worker_does_not_publish_usage(monkeypatch) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer"), _chunk(usage=_usage())])

    def interrupted_wait(fn):
        fn()  # The abandoned worker completes after the caller stops waiting.
        raise RuntimeError("caller interrupted")

    result = _round(monkeypatch, client, core, wait=interrupted_wait)

    assert result[0] is False
    assert core._last_responses_usage is previous
