"""NVIDIA NIM streaming usage compatibility regression tests."""

from types import SimpleNamespace

import pytest

from uagent.providers.llm_nvidia_usage import create_nvidia_chat_completion


class _APIError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.body = {"error": {"message": message}}


class _Chat:
    def __init__(self, first_error=None):
        self.calls = []
        self.first_error = first_error

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.first_error is not None:
            error = self.first_error
            self.first_error = None
            raise error
        return {"choices": []}


def test_nvidia_usage_option_success_does_not_retry():
    chat = _Chat()
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    result = create_nvidia_chat_completion(
        client,
        {"model": "supported", "stream_options": {"include_usage": True}},
        streaming=True,
    )
    assert result == {"choices": []}
    assert len(chat.calls) == 1
    assert chat.calls[0]["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize("status", [400, 422])
def test_nvidia_unsupported_stream_option_retries_once_without_option(status):
    chat = _Chat(_APIError(status, "stream_options is not supported"))
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    result = create_nvidia_chat_completion(
        client,
        {"model": "unsupported", "stream_options": {"include_usage": True}},
        streaming=True,
    )
    assert result == {"choices": []}
    assert len(chat.calls) == 2
    assert chat.calls[0]["stream_options"] == {"include_usage": True}
    assert "stream_options" not in chat.calls[1]
    assert chat.calls[1]["stream"] is True


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "stream_options is not supported"),
        (422, "invalid model identifier"),
        (500, "stream_options is invalid"),
    ],
)
def test_nvidia_unrelated_api_error_does_not_retry(status, message):
    chat = _Chat(_APIError(status, message))
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    with pytest.raises(_APIError):
        create_nvidia_chat_completion(
            client,
            {"model": "model", "stream_options": {"include_usage": True}},
            streaming=True,
        )
    assert len(chat.calls) == 1


def test_nvidia_no_stream_options_does_not_retry():
    chat = _Chat(_APIError(422, "stream_options unsupported"))
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    with pytest.raises(_APIError):
        create_nvidia_chat_completion(client, {"model": "model"}, streaming=True)
    assert len(chat.calls) == 1


def test_nvidia_explicit_stream_option_preserved_until_rejection():
    chat = _Chat(_APIError(422, "stream_options is not supported"))
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    create_nvidia_chat_completion(
        client,
        {"model": "model", "stream_options": {"include_usage": False}},
        streaming=True,
    )
    assert chat.calls[0]["stream_options"]["include_usage"] is False
    assert "stream_options" not in chat.calls[1]
