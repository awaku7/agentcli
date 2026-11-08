"""vLLM measured usage for Chat Completions and Responses API."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.providers.llm_vllm_usage import (
    capture_vllm_responses_usage,
    request_vllm_chat_stream_usage,
    vllm_usage_to_dict,
)
from uagent.providers.openai_compatible_runtime import (
    OpenAICompatibleRuntime,
    _reported_usage,
)
from uagent.runtime.round_contracts import RoundIdentifiers, SerializedRequest


class _Cancellation:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def is_cancelled(self):
        return self.cancelled


class _Completions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _Client:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_Completions(response))
        self.responses = _Completions(response)


def _runtime(client, *, transport="chat_completions", streaming=True, provider="vllm"):
    return OpenAICompatibleRuntime(
        client=client,
        provider=provider,
        model="served-model",
        identifiers=RoundIdentifiers(
            "turn", "round", "attempt", "request", "stream", 1
        ),
        transport=transport,
        streaming=streaming,
    )


def _run(runtime, *, responses=False, options=None, cancellation=None):
    request = SerializedRequest(
        RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1),
        "plan",
        "projection",
        runtime._provider,
        "served-model",
        {
            "model": "served-model",
            "input" if responses else "messages": "PRIVATE" if responses else [],
            **(options or {}),
        },
    )
    return list(runtime.run(request, cancellation or _Cancellation()))


def _chat_usage():
    return {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "prompt_tokens_details": {"cached_tokens": 55, "created_cache_tokens": 20},
        "completion_tokens_details": {"reasoning_tokens": 12},
    }


def _responses_usage():
    return SimpleNamespace(
        input_tokens=120,
        output_tokens=30,
        input_tokens_details=SimpleNamespace(cached_tokens=55, cache_write_tokens=20),
        output_tokens_details=SimpleNamespace(reasoning_tokens=12),
    )


def _expected():
    return {
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
        "cache_read_input_tokens": 55,
        "cache_write_input_tokens": 20,
        "reasoning_output_tokens": 12,
    }


def _chunk(*, content=None, usage=None):
    return SimpleNamespace(
        choices=(
            [SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=[]))]
            if content is not None
            else []
        ),
        usage=usage,
    )


@pytest.mark.parametrize(
    ("responses", "usage"),
    [(False, _chat_usage()), (True, _responses_usage())],
)
def test_vllm_normalizes_chat_and_responses_subsets(responses, usage):
    assert vllm_usage_to_dict(usage, responses=responses) == _expected()
    assert _reported_usage(usage, responses=responses, provider="vllm") == _expected()


@pytest.mark.parametrize("responses", [False, True])
def test_vllm_missing_invalid_and_inconsistent_usage(responses):
    assert vllm_usage_to_dict(None, responses=responses) == {}
    inp = "input_tokens" if responses else "prompt_tokens"
    out = "output_tokens" if responses else "completion_tokens"
    details = "input_tokens_details" if responses else "prompt_tokens_details"
    write = "cache_write_tokens" if responses else "created_cache_tokens"
    response = {
        inp: 10,
        out: 5,
        "total_tokens": 999,
        details: {"cached_tokens": 12, write: 11},
        "output_tokens_details" if responses else "completion_tokens_details": {
            "reasoning_tokens": 6
        },
    }
    assert vllm_usage_to_dict(response, responses=responses) == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    assert vllm_usage_to_dict({inp: True, out: 6}, responses=responses) == {
        "output_tokens": 6
    }
    assert vllm_usage_to_dict({inp: 7, out: -1}, responses=responses) == {
        "input_tokens": 7
    }
    assert vllm_usage_to_dict({inp: 10**12, out: 2}, responses=responses) == {
        "input_tokens": 10**12,
        "output_tokens": 2,
    }


def test_vllm_stream_request_preserves_explicit_options():
    payload = {
        "stream_options": {"include_usage": False, "continuous_usage_stats": True}
    }
    request_vllm_chat_stream_usage(payload)
    assert payload == {
        "stream_options": {
            "include_usage": False,
            "continuous_usage_stats": True,
        }
    }


def test_vllm_chat_stream_requests_usage_and_emits_final_subsets():
    client = _Client(
        [_chunk(content="answer"), _chunk(usage=SimpleNamespace(**_chat_usage()))]
    )
    events = _run(_runtime(client))
    assert client.chat.completions.calls[0]["stream_options"] == {"include_usage": True}
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert events[-1].data["usage"] == _expected()


def test_vllm_chat_nonstream_reports_usage_without_stream_options():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="answer", tool_calls=[]))
        ],
        usage=_chat_usage(),
    )
    client = _Client(response)
    events = _run(_runtime(client, streaming=False))
    assert "stream_options" not in client.chat.completions.calls[0]
    assert events[-1].data["usage"] == _expected()


@pytest.mark.parametrize("provider", ["sarashina", "foundry_local"])
def test_vllm_does_not_change_other_chat_providers(provider):
    client = _Client([_chunk(content="answer")])
    _run(_runtime(client, provider=provider))
    assert "stream_options" not in client.chat.completions.calls[0]


def test_vllm_stream_failure_does_not_report_partial_usage():
    def broken():
        yield _chunk(content="partial", usage=_chat_usage())
        raise OSError("stream interrupted")

    events = _run(_runtime(_Client(broken())))
    assert events[-1].type == "ResponseFailed"
    assert not any(event.type == "ResponseCompleted" for event in events)


def test_vllm_cancelled_stream_does_not_report_usage():
    client = _Client([_chunk(content="answer", usage=_chat_usage())])
    events = _run(_runtime(client), cancellation=_Cancellation(cancelled=True))
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ResponseCancelled",
    ]


def test_vllm_responses_nonstream_emits_usage():
    response = SimpleNamespace(
        id="resp_1", output_text="answer", output=[], usage=_responses_usage()
    )
    client = _Client(response)
    events = _run(
        _runtime(client, transport="responses", streaming=False), responses=True
    )
    assert client.responses.calls[0]["stream"] is False
    assert events[-1].data["usage"] == _expected()


def test_vllm_responses_stream_emits_usage():
    completed = SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(
            id="resp_1", output_text="answer", output=[], usage=_responses_usage()
        ),
    )
    client = _Client([completed])
    events = _run(_runtime(client, transport="responses"), responses=True)
    assert client.responses.calls[0]["stream"] is True
    assert events[-1].data["usage"] == _expected()


def test_vllm_without_usage_does_not_fabricate_counts():
    events = _run(_runtime(_Client([_chunk(content="answer")])))
    assert events[-1].type == "ResponseCompleted"
    assert "usage" not in events[-1].data


def test_vllm_legacy_publication_uses_fresh_normalized_snapshot():
    from uagent.providers.llm_vllm_usage import publish_vllm_legacy_usage

    old = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=old)
    publish_vllm_legacy_usage(core, None, responses=False)
    assert core._last_responses_usage is old

    publish_vllm_legacy_usage(core, _chat_usage(), responses=False)
    assert core._last_responses_usage == _expected()
    assert core._last_responses_usage is not old

    raw = {
        "input_tokens": 20,
        "output_tokens": 4,
        "input_tokens_details": {"cached_tokens": 7, "cache_write_tokens": 3},
    }
    publish_vllm_legacy_usage(core, raw, responses=True)
    assert core._last_responses_usage == {
        "input_tokens": 20,
        "output_tokens": 4,
        "total_tokens": 24,
        "cache_read_input_tokens": 7,
        "cache_write_input_tokens": 3,
    }


def test_vllm_captures_completed_responses_even_after_created_event():
    from uagent.providers.llm_vllm_usage import publish_vllm_legacy_usage

    sink: list[object] = []
    usage = _responses_usage()
    source = [
        SimpleNamespace(
            type="response.created",
            response=SimpleNamespace(id="resp_1"),
        ),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(id="resp_1", usage=usage),
        ),
    ]
    assert (
        list(capture_vllm_responses_usage(source, provider="vllm", sink=sink)) == source
    )
    assert sink == [usage]
    # Exercise the capture -> owner publication boundary, including subsets.
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    publish_vllm_legacy_usage(core, sink[-1], responses=True)
    assert core._last_responses_usage == _expected()
    assert core._last_responses_usage is not previous


def test_vllm_responses_capture_skips_incomplete_and_other_provider():
    sink: list[object] = []
    incomplete = [SimpleNamespace(type="response.created")]
    assert (
        list(capture_vllm_responses_usage(incomplete, provider="vllm", sink=sink))
        == incomplete
    )
    assert sink == []

    other = [SimpleNamespace(type="response.completed")]
    assert capture_vllm_responses_usage(other, provider="openai", sink=sink) is other
    assert sink == []
