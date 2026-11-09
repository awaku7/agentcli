"""Isolated relay I/O tests for the experimental Nostr remote transport."""

from __future__ import annotations

import asyncio
import json

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_state import SQLiteReplayStore
from uagent.nostr_remote_transport import (
    listen_nip17_messages,
    publish_nip17_gift_wrap,
    publish_nip17_gift_wraps,
)
from uagent.tools.nostr_transport import _verify_event


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


RECIPIENT_PUBLIC = bytes.fromhex(
    "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
)
SENDER_PUBLIC_HEX = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"


@pytest.fixture
def replay_store(tmp_path):
    with SQLiteReplayStore(tmp_path / "remote-replay.sqlite3") as store:
        yield store


def _authorize_sender(pubkey_hex: str) -> bool:
    return pubkey_hex == SENDER_PUBLIC_HEX


class FakeWebSocket:
    def __init__(self, scripted_frames: list[list[object]] | None = None) -> None:
        self.sent: list[list[object]] = []
        self.scripted_frames = list(scripted_frames or [])
        self.receive_event: dict | None = None

    async def __aenter__(self) -> "FakeWebSocket":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def send(self, raw: str) -> None:
        frame = json.loads(raw)
        self.sent.append(frame)
        if frame[0] == "EVENT":
            self.receive_event = frame[1]
        elif frame[0] == "AUTH":
            self.scripted_frames.insert(
                0, ["OK", frame[1]["id"], True, "authenticated"]
            )

    async def recv(self) -> str:
        if self.scripted_frames:
            return json.dumps(self.scripted_frames.pop(0))
        if self.receive_event is not None:
            event = self.receive_event
            self.receive_event = None
            return json.dumps(["OK", event["id"], True, "stored"])
        await asyncio.sleep(0.01)
        raise RuntimeError("fake socket has no scripted response")


class FakeListenSocket(FakeWebSocket):
    def __init__(self, event: dict) -> None:
        super().__init__()
        self.event = event
        self.delivered = False
        self.request_count = 0

    async def send(self, raw: str) -> None:
        frame = json.loads(raw)
        if frame[0] == "REQ":
            self.request_count += 1
        await super().send(raw)

    async def recv(self) -> str:
        if not self.delivered:
            self.delivered = True
            subscription_id = self.sent[0][1]
            return json.dumps(["EVENT", subscription_id, self.event])
        await asyncio.sleep(0.01)
        raise RuntimeError("listener should stop after callback")


class FakeListenAuthSocket(FakeListenSocket):
    def __init__(self, event: dict) -> None:
        super().__init__(event)
        self.challenge_sent = False

    async def recv(self) -> str:
        if not self.challenge_sent:
            self.challenge_sent = True
            return json.dumps(["AUTH", "inbox-challenge"])
        if self.scripted_frames:
            return json.dumps(self.scripted_frames.pop(0))
        if self.request_count >= 2 and not self.delivered:
            self.delivered = True
            subscription_id = self.sent[-1][1]
            return json.dumps(["EVENT", subscription_id, self.event])
        await asyncio.sleep(0.01)
        raise RuntimeError("listener should stop after callback")


def test_publish_nip17_wrap_handles_nip42_auth() -> None:
    event = create_nip17_private_messages(
        "hello", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    socket = FakeWebSocket([["AUTH", "relay-challenge"]])

    result = asyncio.run(
        publish_nip17_gift_wrap(
            "wss://relay.example.org",
            event,
            _secret(1),
            allowed_relay_urls=["wss://relay.example.org"],
            connect_factory=lambda _url, **_kwargs: socket,
        )
    )

    assert result.accepted is True
    assert result.event_id == event["id"]
    assert [frame[0] for frame in socket.sent] == ["EVENT", "AUTH", "EVENT"]
    auth_event = socket.sent[1][1]
    assert auth_event["kind"] == 22242
    assert auth_event["tags"] == [
        ["relay", "wss://relay.example.org"],
        ["challenge", "relay-challenge"],
    ]
    assert _verify_event(auth_event)


def test_publish_routes_each_wrap_only_to_its_recipient_inboxes() -> None:
    wraps = create_nip17_private_messages(
        "hello", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )
    sender_relay = "wss://sender-inbox.example.org"
    recipient_relay = "wss://recipient-inbox.example.org"
    connected: list[str] = []

    def connect(url: str, **_kwargs: object) -> FakeWebSocket:
        connected.append(url)
        return FakeWebSocket()

    results = asyncio.run(
        publish_nip17_gift_wraps(
            wraps,
            {
                RECIPIENT_PUBLIC.hex(): [recipient_relay],
                SENDER_PUBLIC_HEX: [sender_relay],
            },
            _secret(1),
            allowed_relay_urls=[recipient_relay, sender_relay],
            connect_factory=connect,
        )
    )

    assert connected == [recipient_relay, sender_relay]
    assert len(results) == 2
    assert all(result.accepted for result in results)


def test_publish_refuses_missing_recipient_inbox_list() -> None:
    wraps = create_nip17_private_messages(
        "hello", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )
    with pytest.raises(ValueError, match="no verified inbox relays"):
        asyncio.run(
            publish_nip17_gift_wraps(
                wraps[:1],
                {},
                _secret(1),
                allowed_relay_urls=["wss://relay.example.org"],
                connect_factory=lambda *_a, **_k: None,
            )
        )


def test_listener_subscribes_for_own_p_tag_and_delivers_unwrapped_rumor(
    replay_store: SQLiteReplayStore,
) -> None:
    private_key = _secret(2)
    gift_wrap = create_nip17_private_messages(
        "hello from relay", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    socket = FakeListenSocket(gift_wrap)
    stop_event = asyncio.Event()
    received: list[dict] = []

    def connect(_url: str, **_kwargs: object) -> FakeListenSocket:
        return socket

    def on_message(rumor: dict) -> None:
        received.append(rumor)
        stop_event.set()

    asyncio.run(
        listen_nip17_messages(
            "wss://recipient-inbox.example.org",
            private_key,
            on_message,
            authorize_sender=_authorize_sender,
            replay_store=replay_store,
            since=1_699_999_000,
            now_fn=lambda: 1_700_000_000,
            stop_event=stop_event,
            connect_factory=connect,
        )
    )

    request = socket.sent[0]
    assert request[0] == "REQ"
    assert request[2]["kinds"] == [1059]
    assert request[2]["#p"] == [RECIPIENT_PUBLIC.hex()]
    assert request[2]["since"] == 1_699_999_000
    assert [frame[0] for frame in socket.sent if frame[0] == "CLOSE"] == ["CLOSE"]
    assert len(received) == 1
    assert received[0]["content"] == "hello from relay"
    assert received[0]["pubkey"] == SENDER_PUBLIC_HEX


def test_publish_never_connects_to_relay_outside_local_egress_allowlist() -> None:
    wraps = create_nip17_private_messages(
        "hello", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )
    attempted: list[str] = []

    def connect(url: str, **_kwargs: object) -> FakeWebSocket:
        attempted.append(url)
        return FakeWebSocket()

    with pytest.raises(ValueError, match="no recipient inbox relay is allowed"):
        asyncio.run(
            publish_nip17_gift_wraps(
                wraps[:1],
                {RECIPIENT_PUBLIC.hex(): ["wss://127.0.0.1:443"]},
                _secret(1),
                allowed_relay_urls=["wss://relay.example.org"],
                connect_factory=connect,
            )
        )
    assert attempted == []


def test_listener_retries_subscription_after_nip42_auth(
    replay_store: SQLiteReplayStore,
) -> None:
    private_key = _secret(2)
    gift_wrap = create_nip17_private_messages(
        "authenticated inbox", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    socket = FakeListenAuthSocket(gift_wrap)
    stop_event = asyncio.Event()
    received: list[dict] = []

    def on_message(rumor: dict) -> None:
        received.append(rumor)
        stop_event.set()

    asyncio.run(
        listen_nip17_messages(
            "wss://recipient-inbox.example.org",
            private_key,
            on_message,
            authorize_sender=_authorize_sender,
            replay_store=replay_store,
            now_fn=lambda: 1_700_000_000,
            stop_event=stop_event,
            connect_factory=lambda _url, **_kwargs: socket,
        )
    )

    assert [frame[0] for frame in socket.sent] == ["REQ", "AUTH", "REQ", "CLOSE"]
    auth_event = socket.sent[1][1]
    assert auth_event["kind"] == 22242
    assert _verify_event(auth_event)
    assert len(received) == 1
    assert received[0]["content"] == "authenticated inbox"


def test_listener_rejects_unpaired_sender_before_replay_claim(replay_store) -> None:
    gift_wrap = create_nip17_private_messages(
        "unauthorized", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    socket = FakeListenSocket(gift_wrap)
    delivered: list[dict] = []

    with pytest.raises(RuntimeError, match="listener should stop"):
        asyncio.run(
            listen_nip17_messages(
                "wss://recipient-inbox.example.org",
                _secret(2),
                delivered.append,
                authorize_sender=lambda _sender: False,
                replay_store=replay_store,
                now_fn=lambda: 1_700_000_000,
                connect_factory=lambda _url, **_kwargs: socket,
            )
        )

    assert delivered == []
    # The unpaired sender was denied before its rumor ID was claimed.
    rumor = unwrap_nip17_private_message(gift_wrap, _secret(2))
    assert replay_store.claim(SENDER_PUBLIC_HEX, rumor["id"], received_at=1_700_000_000)
