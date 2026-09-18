from __future__ import annotations

from uagent.runtime.responses_command_service import ResponsesCommandService


class _Manager:
    def __init__(self) -> None:
        self.calls = []

    def count_input_tokens(self, **kwargs):
        self.calls.append(("tokens", kwargs))
        return 12

    def compact(self, response_id):
        self.calls.append(("compact", response_id))
        return {"id": response_id, "status": "completed"}

    def list_input_items(self, response_id):
        self.calls.append(("items", response_id))
        return [{"id": response_id}]


def test_count_tokens_uses_service_payload_and_known_usage(monkeypatch) -> None:
    manager = _Manager()
    monkeypatch.setattr(
        ResponsesCommandService,
        "build_token_count_payload",
        staticmethod(lambda messages, provider: ("instructions", [], [])),
    )

    result = ResponsesCommandService.count_tokens(
        manager,
        [],
        provider="openai",
        previous_response_id="resp-1",
        last_usage={"total_tokens": 20},
    )

    assert result == {
        "input_token_count": 12,
        "last_response_usage": {"total_tokens": 20},
    }
    assert manager.calls[0][1]["previous_response_id"] == "resp-1"
    assert manager.calls[0][1]["input"] == [{"role": "user", "content": " "}]


def test_compact_and_items_delegate_without_formatting() -> None:
    manager = _Manager()

    assert ResponsesCommandService.compact(manager, "resp-1")["id"] == "resp-1"
    assert ResponsesCommandService.list_items(manager, "resp-1") == [{"id": "resp-1"}]
    assert manager.calls == [("compact", "resp-1"), ("items", "resp-1")]
