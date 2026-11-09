"""LM Studio native SDK measured-usage contract without a live LM Studio server."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from uagent.providers import llm_lmstudio_sdk as sdk
from uagent.providers.openai_compatible_runtime import _reported_usage


def _stats(prompt=20, completion=7):
    return SimpleNamespace(
        prompt_tokens_count=prompt,
        predicted_tokens_count=completion,
    )


def _client(monkeypatch, model, *, use_tools=False):
    monkeypatch.setitem(
        sys.modules,
        "lmstudio",
        SimpleNamespace(Chat=SimpleNamespace(from_history=lambda _history: "chat")),
    )
    monkeypatch.setattr(
        sdk,
        "_sdk_tools",
        lambda _specs, _core: [object()] if use_tools else [],
    )
    client = sdk.LMStudioSDKClient.__new__(sdk.LMStudioSDKClient)
    client._core = SimpleNamespace()
    client._model = model
    return client


@pytest.mark.parametrize("stream_result", ["valid", "invalid", "missing", "failure"])
def test_respond_stream_reports_usage_only_after_success(
    monkeypatch, stream_result: str
) -> None:
    class PredictionStream:
        def __iter__(self):
            yield SimpleNamespace(content="hello")

        def result(self):
            if stream_result == "failure":
                raise RuntimeError("no completed result")
            stats = None
            if stream_result == "valid":
                stats = _stats(20, 7)
            elif stream_result == "invalid":
                stats = _stats(True, -1)
            return SimpleNamespace(stats=stats)

    client = _client(
        monkeypatch,
        SimpleNamespace(respond_stream=lambda _prompt: PredictionStream()),
    )
    chunks = list(
        client.create(messages=[{"role": "user", "content": "hello"}], stream=True)
    )
    assert chunks[0].choices[0].delta.content == "hello"
    if stream_result == "valid":
        assert len(chunks) == 2
        assert chunks[-1].choices == []
        assert _reported_usage(chunks[-1].usage, responses=False) == {
            "input_tokens": 20,
            "output_tokens": 7,
            "total_tokens": 27,
        }
    else:
        assert len(chunks) == 1


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("kind", ["complete", "partial", "missing"])
def test_act_collects_all_completed_rounds_without_partial_totals(
    monkeypatch, streaming: bool, kind: str
) -> None:
    rounds = {
        "complete": [_stats(10, 3), _stats(20, 7)],
        "partial": [_stats(10, 3), _stats(20, None)],
        "missing": [SimpleNamespace(), SimpleNamespace()],
    }[kind]

    def act(_prompt, _tools, *, on_prediction_fragment, on_prediction_completed):
        for index, stats in enumerate(rounds):
            on_prediction_completed(SimpleNamespace(stats=stats))
            on_prediction_fragment(SimpleNamespace(content="visible"), index)
        return SimpleNamespace(content="visible")

    client = _client(monkeypatch, SimpleNamespace(act=act), use_tools=True)
    response = client.create(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"function": {"name": "demo"}}],
        stream=streaming,
    )
    if streaming:
        chunks = list(response)
        usages = [chunk.usage for chunk in chunks if hasattr(chunk, "usage")]
        assert any(chunk.choices for chunk in chunks)
        assert all(chunk.choices == [] for chunk in chunks if hasattr(chunk, "usage"))
        measured = usages[-1] if usages else {}
    else:
        measured = response.usage
        assert response.choices[0].message.content

    if kind == "complete":
        assert measured == {
            "prompt_tokens": 30,
            "completion_tokens": 10,
            "total_tokens": 40,
        }
    elif kind == "partial":
        assert measured == {"prompt_tokens": 30}
    else:
        assert measured == {}


@pytest.mark.parametrize("streaming", [True, False])
def test_act_failure_never_reports_partial_usage(monkeypatch, streaming: bool) -> None:
    def act(_prompt, _tools, *, on_prediction_fragment, on_prediction_completed):
        on_prediction_completed(SimpleNamespace(stats=_stats(10, 3)))
        raise RuntimeError("act interrupted")

    client = _client(monkeypatch, SimpleNamespace(act=act), use_tools=True)
    with pytest.raises(RuntimeError, match="act interrupted"):
        response = client.create(
            messages=[{"role": "user", "content": "hello"}],
            tools=[{"function": {"name": "demo"}}],
            stream=streaming,
        )
        if streaming:
            list(response)


def test_act_usage_is_not_reused_across_requests(monkeypatch) -> None:
    responses = iter([_stats(11, 5), SimpleNamespace()])

    def act(_prompt, _tools, *, on_prediction_fragment, on_prediction_completed):
        on_prediction_completed(SimpleNamespace(stats=next(responses)))
        return SimpleNamespace(content="ok")

    client = _client(monkeypatch, SimpleNamespace(act=act), use_tools=True)
    kwargs = {
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"function": {"name": "demo"}}],
    }
    assert client.create(**kwargs).usage["total_tokens"] == 16
    assert client.create(**kwargs).usage == {}
