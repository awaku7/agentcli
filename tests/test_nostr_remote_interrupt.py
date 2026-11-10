from __future__ import annotations

from types import SimpleNamespace

from uagent.cli_impl.main import _interrupt_nostr_remote_request


def test_interrupted_remote_request_is_terminally_failed_and_notified() -> None:
    calls: list[tuple[str, object, object]] = []
    request = {"sender_pubkey": "ab" * 32, "rumor_id": "cd" * 32}

    class FakeRuntime:
        def finish_event(self, event: dict[str, str], outcome: str) -> bool:
            calls.append(("finish", event, outcome))
            return True

        def send_reply(self, event: dict[str, str], text: str) -> dict[str, object]:
            calls.append(("reply", event, text))
            return {"ok": True, "event_ids": ["event-id"]}

    core = SimpleNamespace(_nostr_remote_runtime=FakeRuntime())

    _interrupt_nostr_remote_request(core, request)

    assert calls[0] == ("finish", request, "failed")
    assert calls[1] == (
        "reply",
        request,
        "The remote request was interrupted on the CLI.",
    )
