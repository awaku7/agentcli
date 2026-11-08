"""Regression tests for provider-reported Z.AI SDK usage."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.llm_deepseek import parse_deepseek_stream
from uagent.providers.llm_zai import zai_chat_with_tools
from uagent.runtime.stream_renderer import StreamCallbacks
from uagent.runtime.telemetry import zai_chat_usage_to_dict


class _Client:
    def __init__(self, result):
        self.result = result
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def _usage(*, cached=30, reasoning=15):
    return SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=35,
        total_tokens=135,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
    )


def _expected():
    return {
        "input_tokens": 100,
        "output_tokens": 35,
        "total_tokens": 135,
        "cache_read_input_tokens": 30,
        "reasoning_output_tokens": 15,
    }


def _chunk(*, content=None, usage=None):
    delta = SimpleNamespace(
        content=content,
        reasoning_content=None,
        tool_calls=[],
    )
    choices = [SimpleNamespace(delta=delta)] if content is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


def _callbacks():
    return StreamCallbacks(
        on_delta=lambda _text: None,
        on_reasoning=lambda _text: None,
    )


def _round(monkeypatch, client, core, *, stream=True, wait=None):
    monkeypatch.setattr(
        "uagent.providers.llm_zai.build_zai_chat_kwargs",
        lambda **_kwargs: ({"model": "glm-test", "messages": []}, None),
    )
    monkeypatch.setattr(
        "uagent.providers.llm_zai.native_structured_output_request_for_runtime",
        lambda *_args, **_kwargs: None,
    )
    return zai_chat_with_tools(
        client=client,
        depname="glm-test",
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


def test_zai_normalizes_reported_cache_and_optional_reasoning_subsets() -> None:
    assert zai_chat_usage_to_dict(_usage()) == _expected()
    assert zai_chat_usage_to_dict(
        {"prompt_tokens": 14, "completion_tokens": 5}
    ) == {
        "input_tokens": 14,
        "output_tokens": 5,
        "total_tokens": 19,
    }
    assert zai_chat_usage_to_dict(
        {
            "prompt_tokens": 12,
            "completion_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
    ) == {
        "input_tokens": 12,
        "output_tokens": 0,
        "total_tokens": 12,
        "cache_read_input_tokens": 0,
    }


def test_zai_invalid_usage_is_never_fabricated() -> None:
    assert zai_chat_usage_to_dict(None) == {}
    assert zai_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 11},
        }
    ) == {"output_tokens": 5}
    assert zai_chat_usage_to_dict(
        {
            "prompt_tokens": True,
            "completion_tokens": 5,
            "completion_tokens_details": {"reasoning_tokens": 6},
        }
    ) == {}
    assert zai_chat_usage_to_dict(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "completion_tokens_details": {"reasoning_tokens": -1},
        }
    ) == {"input_tokens": 10}
    assert zai_chat_usage_to_dict(
        {"prompt_tokens": 10**12, "completion_tokens": 2}
    ) == {
        "input_tokens": 10**12,
        "output_tokens": 2,
    }


def test_zai_stream_parser_collects_final_usage_without_mutating_core() -> None:
    before = {"input_tokens": 777}
    core = SimpleNamespace(_last_responses_usage=before)
    snapshots: list[dict[str, int]] = []
    result = parse_deepseek_stream(
        [_chunk(content="answer"), _chunk(usage=_usage())],
        core=core,
        callbacks=_callbacks(),
        usage_sink=snapshots,
        usage_normalizer=zai_chat_usage_to_dict,
    )
    assert result[0] == "answer"
    assert snapshots == [_expected()]
    assert core._last_responses_usage is before


def test_zai_stream_parser_ignores_incomplete_usage_after_error() -> None:
    def failed_stream():
        yield _chunk(content="partial", usage=_usage())
        raise RuntimeError("interrupted stream")

    snapshots: list[dict[str, int]] = []
    parse_deepseek_stream(
        failed_stream(),
        callbacks=_callbacks(),
        usage_sink=snapshots,
        usage_normalizer=zai_chat_usage_to_dict,
    )
    assert snapshots == []


def test_zai_legacy_round_stream_reports_usage_after_wait_returns(monkeypatch) -> None:
    core = SimpleNamespace(_last_responses_usage={"input_tokens": 999})
    client = _Client([_chunk(content="answer"), _chunk(usage=_usage())])

    result = _round(monkeypatch, client, core)

    assert result[0] is True
    assert result[2] == "answer"
    assert core._last_responses_usage == _expected()
    assert client.calls[0]["stream"] is True
    # Z.AI sends usage with its last chunk without stream_options.
    assert "stream_options" not in client.calls[0]


def test_zai_legacy_round_nonstream_reports_usage(monkeypatch) -> None:
    core = SimpleNamespace(_last_responses_usage={})
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="answer", reasoning_content="", tool_calls=[]
                )
            )
        ],
        usage=_usage(),
    )
    client = _Client(response)

    result = _round(monkeypatch, client, core, stream=False)

    assert result[0] is True
    assert result[2] == "answer"
    assert core._last_responses_usage == _expected()
    assert "stream_options" not in client.calls[0]


def test_zai_legacy_round_no_usage_does_not_reuse_previous_counts(
    monkeypatch,
) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer")])

    result = _round(monkeypatch, client, core)

    assert result[0] is True
    assert core._last_responses_usage is previous


def test_zai_legacy_round_interrupted_wait_cannot_publish_worker_usage(
    monkeypatch,
) -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    client = _Client([_chunk(content="answer"), _chunk(usage=_usage())])

    def interrupted_wait(fn):
        fn()  # Simulate an abandoned worker finishing after its owner has stopped.
        raise RuntimeError("owner interrupted")

    result = _round(monkeypatch, client, core, wait=interrupted_wait)

    assert result[0] is False
    assert core._last_responses_usage is previous
