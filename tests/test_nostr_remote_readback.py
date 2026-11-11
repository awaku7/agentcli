"""Readback diagnostics for delivered encrypted NIP-17 replies."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from uagent.nostr_nip17 import _public_key_x, create_nip17_private_messages
from uagent.nostr_remote_outbox import SQLiteNostrOutboxStore
from uagent.nostr_remote_transport import read_back_nip17_gift_wrap
from uagent.tools import nostr_transport


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


class FakeReadbackSocket:
    def __init__(self, outcome: str, event: dict[str, object]) -> None:
        self.outcome = outcome
        self.event = event
        self.request: list[object] | None = None

    async def __aenter__(self) -> "FakeReadbackSocket":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def send(self, raw: str) -> None:
        self.request = json.loads(raw)

    async def recv(self) -> str:
        assert self.request is not None
        sub_id = self.request[1]
        if self.outcome == "found":
            return json.dumps(["EVENT", sub_id, self.event])
        if self.outcome == "missing":
            return json.dumps(["EOSE", sub_id])
        if self.outcome == "closed":
            return json.dumps(["CLOSED", sub_id, "auth-required"])
        if self.outcome == "auth":
            return json.dumps(["AUTH", "challenge"])
        if self.outcome == "invalid":
            return json.dumps(["EVENT", sub_id, {**self.event, "content": "invalid"}])
        raise AssertionError("unexpected outcome")


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("found", "found"),
        ("missing", "not_returned"),
        ("closed", "unavailable"),
        ("auth", "unavailable"),
    ],
)
def test_readback_queries_exact_encrypted_event_id(outcome, expected) -> None:
    recipient = _public_key_x(_secret(2))
    event = create_nip17_private_messages("test reply", _secret(1), recipient)[0]
    socket = FakeReadbackSocket(outcome, event)

    def connect(url, **kwargs):
        assert url == "wss://allowed.example"
        assert kwargs["ssl"] is not None
        return socket

    result = asyncio.run(
        read_back_nip17_gift_wrap(
            "wss://allowed.example",
            event["id"],
            allowed_relay_urls=["wss://allowed.example"],
            connect_factory=connect,
        )
    )
    assert result == expected
    assert socket.request is not None
    assert socket.request[0] == "REQ"
    assert socket.request[2] == {
        "ids": [event["id"]],
        "kinds": [1059],
        "limit": 1,
    }



def test_readback_authenticates_and_retries_subscription() -> None:
    recipient = _public_key_x(_secret(2))
    event = create_nip17_private_messages("test reply", _secret(1), recipient)[0]

    class AuthSocket(FakeReadbackSocket):
        def __init__(self) -> None:
            super().__init__("found", event)
            self.sent: list[list[object]] = []
            self.step = 0

        async def send(self, raw: str) -> None:
            message = json.loads(raw)
            self.sent.append(message)
            if message[0] == "REQ":
                self.request = message

        async def recv(self) -> str:
            self.step += 1
            if self.step == 1:
                return json.dumps(["AUTH", "test-challenge"])
            if self.step == 2:
                assert self.sent[-1][0] == "AUTH"
                auth_event = self.sent[-1][1]
                assert auth_event["kind"] == 22242
                return json.dumps(["OK", auth_event["id"], True, ""])
            assert self.sent[-1][0] == "REQ"
            return json.dumps(["EVENT", self.request[1], self.event])

    socket = AuthSocket()
    result = asyncio.run(
        read_back_nip17_gift_wrap(
            "wss://allowed.example",
            event["id"],
            allowed_relay_urls=["wss://allowed.example"],
            auth_private_key=_secret(1),
            connect_factory=lambda *_args, **_kwargs: socket,
        )
    )
    assert result == "found"
    assert [message[0] for message in socket.sent] == ["REQ", "AUTH", "REQ"]


def test_readback_does_not_treat_invalid_event_as_found() -> None:
    recipient = _public_key_x(_secret(2))
    event = create_nip17_private_messages("test reply", _secret(1), recipient)[0]

    class InvalidThenEOSE(FakeReadbackSocket):
        async def recv(self) -> str:
            if self.outcome == "invalid":
                self.outcome = "missing"
                return json.dumps(
                    [
                        "EVENT",
                        self.request[1],
                        {**self.event, "content": "invalid"},
                    ]
                )
            return await super().recv()

    socket = InvalidThenEOSE("invalid", event)
    result = asyncio.run(
        read_back_nip17_gift_wrap(
            "wss://allowed.example",
            event["id"],
            allowed_relay_urls=["wss://allowed.example"],
            connect_factory=lambda *_a, **_kw: socket,
        )
    )
    assert result == "unavailable"


def test_readback_default_websocket_connector_never_follows_redirects() -> None:
    from websockets.asyncio.client import connect
    from websockets.datastructures import Headers
    from websockets.exceptions import InvalidStatus
    from websockets.http11 import Response

    from uagent.nostr_remote_transport import _readback_connect_factory

    factory = _readback_connect_factory(None)
    assert issubclass(factory, connect)

    redirect = InvalidStatus(
        Response(
            302,
            "Found",
            Headers({"Location": "wss://unapproved.example/private"}),
        )
    )
    connection = factory("wss://allowed.example")
    assert connection.process_redirect(redirect) is redirect


def test_readback_rejects_unapproved_relay_without_connecting() -> None:
    called = []

    with pytest.raises(ValueError, match="not permitted"):
        asyncio.run(
            read_back_nip17_gift_wrap(
                "wss://unapproved.example",
                "ab" * 32,
                allowed_relay_urls=["wss://allowed.example"],
                connect_factory=lambda *_args, **_kwargs: called.append(True),
            )
        )
    assert called == []


def test_latest_delivered_reply_keeps_only_event_ids(tmp_path) -> None:
    store = SQLiteNostrOutboxStore(tmp_path / "outbox.sqlite")
    sender = _public_key_x(_secret(2)).hex()
    events = create_nip17_private_messages(
        "test reply", _secret(1), _public_key_x(_secret(2))
    )
    routes = {
        sender: ["wss://allowed.example"],
        _public_key_x(_secret(1)).hex(): ["wss://allowed.example"],
    }
    try:
        assert store.latest_delivered() is None
        store.enqueue(sender, "ab" * 32, events, routes)
        assert store.claim(sender, "ab" * 32) is not None
        assert store.mark_delivered(sender, "ab" * 32)
        latest = store.latest_delivered()
        assert latest is not None
        assert latest.status == "delivered"
        assert latest.event_ids == tuple(event["id"] for event in events)
        assert latest.events is None
        assert latest.relay_lists_by_pubkey is None
    finally:
        store.close()


def test_remote_verify_command_prints_only_identifiers_and_results(
    capsys,
) -> None:
    runtime = SimpleNamespace(
        verify_latest_reply=lambda: {
            "state": "complete",
            "event_ids": ["ab" * 32, "cd" * 32],
            "relays": [
                {
                    "relay": "wss://allowed.example",
                    "recipient": "found",
                    "sender_copy": "not_returned",
                }
            ],
        }
    )
    core = SimpleNamespace(_nostr_remote_runtime=runtime)
    nostr_transport._cmd_nostr_remote("verify", core=core)
    output = capsys.readouterr().out
    assert "recipient=found; sender_copy=not_returned" in output
    assert "ab" * 32 in output
    assert "does not confirm delivery to 0xChat" in output


def test_runtime_readback_uses_latest_tombstone_and_local_relays(
    monkeypatch,
) -> None:
    from uagent import nostr_remote_transport
    from uagent.nostr_remote_runtime import NostrRemoteRuntime

    checked = []

    async def fake_readback(
        relay, event_id, *, allowed_relay_urls, auth_private_key, timeout
    ):
        checked.append(
            (relay, event_id, list(allowed_relay_urls), auth_private_key, timeout)
        )
        return "found" if event_id == "ab" * 32 else "not_returned"

    monkeypatch.setattr(
        nostr_remote_transport,
        "read_back_nip17_gift_wrap",
        fake_readback,
    )
    runtime = SimpleNamespace(
        _closed=False,
        outbox_store=SimpleNamespace(
            latest_delivered=lambda: SimpleNamespace(event_ids=("ab" * 32, "cd" * 32))
        ),
        relays=("wss://allowed-a.example", "wss://allowed-b.example"),
        private_key=_secret(1),
    )
    result = NostrRemoteRuntime.verify_latest_reply(runtime)
    assert result["state"] == "complete"
    assert len(result["relays"]) == 2
    assert all(
        row["recipient"] == "found" and row["sender_copy"] == "not_returned"
        for row in result["relays"]
    )
    assert len(checked) == 4
    assert all(
        allowlist == list(runtime.relays)
        and auth_private_key == runtime.private_key
        and timeout == 3.0
        for _, _, allowlist, auth_private_key, timeout in checked
    )
