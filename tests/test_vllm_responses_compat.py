from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.providers.llm_vllm_responses import (
    create_vllm_responses,
    is_vllm_string_input_schema_error,
)


class _Responses:
    def __init__(self, *, reject_structured_input: bool = True) -> None:
        self.calls: list[dict[str, object]] = []
        self.reject_structured_input = reject_structured_input

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_structured_input and isinstance(kwargs.get("input"), list):
            raise RuntimeError(
                "400 validation error: {'type': 'string_type', "
                "'loc': 'body.input', 'msg': 'Input should be a valid string'}"
            )
        return SimpleNamespace(ok=True, kwargs=kwargs)


class _Client:
    def __init__(self) -> None:
        self.responses = _Responses()


def test_detects_only_vllm_string_input_schema_error() -> None:
    error = RuntimeError(
        "{'loc': 'body.input.1.content', " "'msg': 'Input should be a valid string'}"
    )
    assert is_vllm_string_input_schema_error(error)
    assert not is_vllm_string_input_schema_error(
        RuntimeError("previous_response_id not found")
    )


def test_retries_vllm_responses_with_json_transcript_after_schema_error() -> None:
    client = _Client()
    original = [
        {"role": "user", "content": [{"type": "input_text", "text": "Hello"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "Hi"}]},
    ]

    result = create_vllm_responses(
        client,
        {"model": "served-model", "input": original},
        provider="vllm",
        stream=True,
    )

    assert result.ok
    assert len(client.responses.calls) == 2
    assert client.responses.calls[0]["input"] == original
    assert client.responses.calls[0]["stream"] is True
    retry_input = client.responses.calls[1]["input"]
    assert client.responses.calls[1]["stream"] is True
    assert isinstance(retry_input, str)
    assert '"role":"user"' in retry_input
    assert '"text":"Hello"' in retry_input
    assert getattr(client, "_uagent_vllm_responses_string_input") is True


def test_remembers_string_input_schema_for_subsequent_vllm_calls() -> None:
    client = _Client()
    request = {"model": "served-model", "input": [{"role": "user", "content": "Hi"}]}

    create_vllm_responses(client, request, provider="vllm")
    create_vllm_responses(client, request, provider="vllm")

    assert len(client.responses.calls) == 3
    assert isinstance(client.responses.calls[1]["input"], str)
    assert isinstance(client.responses.calls[2]["input"], str)


def test_does_not_retry_other_vllm_errors() -> None:
    class _RejectAll:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            raise RuntimeError("invalid tool schema")

    client = SimpleNamespace(responses=_RejectAll())
    with pytest.raises(RuntimeError, match="invalid tool schema"):
        create_vllm_responses(
            client,
            {"model": "served-model", "input": [{"role": "user", "content": "Hi"}]},
            provider="vllm",
        )
    assert client.responses.calls == 1


def test_non_vllm_provider_keeps_the_structured_request_unchanged() -> None:
    client = _Client()
    client.responses.reject_structured_input = False
    request = {"model": "served-model", "input": [{"role": "user", "content": "Hi"}]}

    result = create_vllm_responses(client, request, provider="openai")

    assert result.ok
    assert client.responses.calls == [request]
