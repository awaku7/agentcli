from __future__ import annotations

import pytest

from uagent.providers.responses_manager import (
    ResponsesManager,
    UnsupportedResponsesOperation,
    cancel_active_response,
    get_responses_capabilities,
)


class _InputTokens:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def count(self, **kwargs):
        self.calls.append(kwargs)
        return {"input_tokens": 7}


class _InputItems:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def list(self, response_id: str, **kwargs):
        self.calls.append((response_id, kwargs))
        return {"data": []}


class _Responses:
    def __init__(self) -> None:
        self.input_tokens = _InputTokens()
        self.input_items = _InputItems()
        self.calls: list[tuple[str, str]] = []

    def retrieve(self, response_id: str):
        self.calls.append(("retrieve", response_id))
        return {"id": response_id}

    def cancel(self, response_id: str):
        self.calls.append(("cancel", response_id))
        return {"id": response_id, "status": "cancelled"}

    def delete(self, response_id: str):
        self.calls.append(("delete", response_id))
        return {"id": response_id, "deleted": True}

    def compact(self, **kwargs):
        self.calls.append(("compact", kwargs["response_id"]))
        return {"id": kwargs["response_id"]}


class _Client:
    def __init__(self) -> None:
        self.responses = _Responses()


def test_openai_management_operations() -> None:
    client = _Client()
    manager = ResponsesManager(client, provider="openai", model="gpt-5.4")

    assert manager.retrieve("resp_1")["id"] == "resp_1"
    assert manager.cancel("resp_1")["status"] == "cancelled"
    assert manager.delete("resp_1")["deleted"] is True
    assert manager.list_input_items("resp_1", limit=5) == {"data": []}
    assert manager.count_input_tokens(input="hello")["input_tokens"] == 7
    assert manager.compact("resp_1")["id"] == "resp_1"
    assert client.responses.input_tokens.calls[0]["model"] == "gpt-5.4"
    assert client.responses.input_items.calls == [("resp_1", {"limit": 5})]


def test_cancel_active_response_uses_tracked_id() -> None:
    client = _Client()

    class Core:
        responses_state = {"active_response_id": "resp_active"}
        _responses_client = client
        _responses_provider = "openai"
        _responses_model = "gpt-5.4"

    assert cancel_active_response(Core()) is True
    assert client.responses.calls == [("cancel", "resp_active")]


def test_cancel_active_response_without_state_is_noop() -> None:
    class Core:
        responses_state = {}
        _responses_client = _Client()
        _responses_provider = "openai"
        _responses_model = "gpt-5.4"

    assert cancel_active_response(Core()) is False


def test_unsupported_provider_is_conservative() -> None:
    manager = ResponsesManager(_Client(), provider="openrouter")

    with pytest.raises(UnsupportedResponsesOperation):
        manager.retrieve("resp_1")
    with pytest.raises(UnsupportedResponsesOperation):
        manager.count_input_tokens(input="hello")


def test_unknown_provider_has_no_management_capabilities() -> None:
    capabilities = get_responses_capabilities("unknown")
    assert capabilities.create is False
    assert capabilities.retrieve is False
    assert capabilities.cancel is False
