"""Isolated relay I/O tests for the experimental Nostr remote transport."""

from __future__ import annotations

import asyncio
import json

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
    create_nip17_relay_list_event,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_state import SQLiteReplayStore
from uagent.nostr_remote_transport import (
    fetch_nip17_relay_list,
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


def test_publish_waits_for_auth_challenge_after_auth_required_ok() -> None:
    event = create_nip17_private_messages(
        "auth-required first", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    socket = FakeWebSocket(
        [
            ["OK", event["id"], False, "auth-required: please authenticate"],
            ["AUTH", "relay-challenge-after-rejection"],
        ]
    )

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
    assert [frame[0] for frame in socket.sent] == ["EVENT", "AUTH", "EVENT"]
    assert socket.sent[1][1]["tags"] == [
        ["relay", "wss://relay.example.org"],
        ["challenge", "relay-challenge-after-rejection"],
    ]


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


def test_listener_requires_exactly_one_deduplication_store(
    replay_store: SQLiteReplayStore, tmp_path
) -> None:
    common = (
        "wss://recipient-inbox.example.org",
        _secret(2),
        lambda _rumor: None,
    )
    with pytest.raises(ValueError, match="exactly one"):
        asyncio.run(
            listen_nip17_messages(
                *common,
                authorize_sender=_authorize_sender,
                connect_factory=lambda *_a, **_k: None,
            )
        )

    with SQLiteNostrInboxStore(tmp_path / "listener-both-stores.sqlite3") as inbox:
        with pytest.raises(ValueError, match="exactly one"):
            asyncio.run(
                listen_nip17_messages(
                    *common,
                    authorize_sender=_authorize_sender,
                    replay_store=replay_store,
                    inbox_store=inbox,
                    target_session_id="active-session",
                    connect_factory=lambda *_a, **_k: None,
                )
            )


def test_listener_persists_encrypted_wrap_before_callback(tmp_path) -> None:
    gift_wrap = create_nip17_private_messages(
        "do not store plaintext", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    relay_plaintext = "relay-added field must not be persisted"
    relayed_event = {**gift_wrap, "relay_added_plaintext": relay_plaintext}
    rumor = unwrap_nip17_private_message(gift_wrap, _secret(2))
    socket = FakeListenSocket(relayed_event)
    stop_event = asyncio.Event()
    callback_messages: list[dict] = []

    with SQLiteNostrInboxStore(tmp_path / "durable-inbox.sqlite3") as inbox:

        def on_message(received_rumor: dict) -> None:
            # The durable handoff must exist before the callback can enqueue
            # work into the in-memory CLI event queue.
            record = inbox.get(received_rumor["pubkey"], received_rumor["id"])
            assert record is not None
            assert record.status == "pending"
            assert record.wrapped_event == gift_wrap
            callback_messages.append(received_rumor)
            stop_event.set()

        asyncio.run(
            listen_nip17_messages(
                "wss://recipient-inbox.example.org",
                _secret(2),
                on_message,
                authorize_sender=_authorize_sender,
                inbox_store=inbox,
                target_session_id="active-session",
                now_fn=lambda: 1_700_000_000,
                stop_event=stop_event,
                connect_factory=lambda _url, **_kwargs: socket,
            )
        )

        pending = inbox.list_pending()
        assert len(pending) == 1
        assert pending[0].session_id == "active-session"
        assert pending[0].created_at == rumor["created_at"]
        assert pending[0].received_at == 1_700_000_000
        assert "do not store plaintext" not in json.dumps(pending[0].wrapped_event)
        assert relay_plaintext not in json.dumps(pending[0].wrapped_event)
        assert len(callback_messages) == 1


def test_listener_keeps_running_when_durable_inbox_is_full(tmp_path) -> None:
    existing_wrap = create_nip17_private_messages(
        "already pending", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    existing_rumor = unwrap_nip17_private_message(existing_wrap, _secret(2))
    incoming_wrap = create_nip17_private_messages(
        "inbox capacity exceeded", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    stop_event = asyncio.Event()

    class StopAfterOneListenSocket(FakeListenSocket):
        async def recv(self) -> str:
            raw = await super().recv()
            stop_event.set()
            return raw

    with SQLiteNostrInboxStore(
        tmp_path / "full-listener-inbox.sqlite3", max_pending=1
    ) as inbox:
        assert inbox.enqueue_verified_wrap(
            existing_rumor["pubkey"],
            existing_rumor["id"],
            existing_wrap,
            created_at=existing_rumor["created_at"],
            session_id="active-session",
        )
        callback_calls: list[dict] = []
        socket = StopAfterOneListenSocket(incoming_wrap)

        asyncio.run(
            listen_nip17_messages(
                "wss://recipient-inbox.example.org",
                _secret(2),
                callback_calls.append,
                authorize_sender=_authorize_sender,
                inbox_store=inbox,
                target_session_id="active-session",
                now_fn=lambda: 1_700_000_000,
                stop_event=stop_event,
                connect_factory=lambda _url, **_kwargs: socket,
            )
        )

        assert callback_calls == []
        assert len(inbox.list_pending()) == 1
        assert inbox.list_pending()[0].rumor_id == existing_rumor["id"]


def test_listener_callback_failure_leaves_durable_pending_request(tmp_path) -> None:
    gift_wrap = create_nip17_private_messages(
        "persist before callback", _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    socket = FakeListenSocket(gift_wrap)

    def fail_callback(_rumor: dict) -> None:
        raise RuntimeError("simulated queue handoff failure")

    with SQLiteNostrInboxStore(tmp_path / "callback-failure.sqlite3") as inbox:
        with pytest.raises(RuntimeError, match="simulated"):
            asyncio.run(
                listen_nip17_messages(
                    "wss://recipient-inbox.example.org",
                    _secret(2),
                    fail_callback,
                    authorize_sender=_authorize_sender,
                    inbox_store=inbox,
                    target_session_id="active-session",
                    now_fn=lambda: 1_700_000_000,
                    connect_factory=lambda _url, **_kwargs: socket,
                )
            )

        pending = inbox.list_pending()
        assert len(pending) == 1
        assert pending[0].status == "pending"
        assert pending[0].wrapped_event == gift_wrap


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


class FakeRelayListSocket:
    def __init__(
        self,
        event: dict,
        *,
        require_auth: bool = False,
        close_before_auth_ack: bool = False,
    ) -> None:
        self.event = event
        self.require_auth = require_auth
        self.close_before_auth_ack = close_before_auth_ack
        self.authenticated = False
        self.frames: list[list[object]] = []
        self.subscription_id = ""
        self.sent: list[list[object]] = []

    async def __aenter__(self) -> "FakeRelayListSocket":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def send(self, raw: str) -> None:
        frame = json.loads(raw)
        self.sent.append(frame)
        if frame[0] == "REQ":
            self.subscription_id = frame[1]
            if self.require_auth and not self.authenticated:
                self.frames = [["AUTH", "relay-auth-challenge"]]
                if self.close_before_auth_ack:
                    self.frames.append(
                        [
                            "CLOSED",
                            self.subscription_id,
                            "auth-required: authentication required",
                        ]
                    )
            else:
                self.frames = [
                    ["EVENT", self.subscription_id, self.event],
                    ["EOSE", self.subscription_id],
                ]
        elif frame[0] == "AUTH":
            self.authenticated = True
            acknowledgement = ["OK", frame[1]["id"], True, "authenticated"]
            if self.close_before_auth_ack:
                self.frames.append(acknowledgement)
            else:
                self.frames = [acknowledgement]

    async def recv(self) -> str:
        return json.dumps(self.frames.pop(0))


def test_fetch_relay_list_verifies_author_and_uses_local_lookup_relay() -> None:
    signed_event = create_nip17_relay_list_event(
        ["wss://recipient-inbox.example.org"], _secret(3), now=1_700_000_000
    )
    socket = FakeRelayListSocket(signed_event)
    result = asyncio.run(
        fetch_nip17_relay_list(
            signed_event["pubkey"],
            ["wss://local-lookup.example.org"],
            allowed_relay_urls=["wss://local-lookup.example.org"],
            connect_factory=lambda *_args, **_kwargs: socket,
        )
    )
    assert result == ["wss://recipient-inbox.example.org"]
    assert socket.sent[0][2]["kinds"] == [10050]
    assert socket.sent[-1] == ["CLOSE", socket.subscription_id]


def test_fetch_relay_list_refuses_unapproved_lookup_destination() -> None:
    called = False

    def no_connect(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unapproved destination must not connect")

    with pytest.raises(ValueError, match="local relay allowlist"):
        asyncio.run(
            fetch_nip17_relay_list(
                SENDER_PUBLIC_HEX,
                ["wss://attacker.example"],
                allowed_relay_urls=["wss://local.example"],
                connect_factory=no_connect,
            )
        )
    assert not called


def test_fetch_relay_list_handles_nip42_auth() -> None:
    signed_event = create_nip17_relay_list_event(
        ["wss://recipient-inbox.example.org"], _secret(3), now=1_700_000_000
    )
    socket = FakeRelayListSocket(signed_event, require_auth=True)
    result = asyncio.run(
        fetch_nip17_relay_list(
            signed_event["pubkey"],
            ["wss://local-lookup.example.org"],
            allowed_relay_urls=["wss://local-lookup.example.org"],
            auth_private_key=_secret(2),
            connect_factory=lambda *_args, **_kwargs: socket,
        )
    )
    assert result == ["wss://recipient-inbox.example.org"]
    assert any(frame[0] == "AUTH" for frame in socket.sent)
    assert sum(frame[0] == "REQ" for frame in socket.sent) == 2


def test_fetch_relay_list_waits_for_auth_ack_after_auth_required_closed() -> None:
    signed_event = create_nip17_relay_list_event(
        ["wss://recipient-inbox.example.org"], _secret(3), now=1_700_000_000
    )
    socket = FakeRelayListSocket(
        signed_event, require_auth=True, close_before_auth_ack=True
    )

    result = asyncio.run(
        fetch_nip17_relay_list(
            signed_event["pubkey"],
            ["wss://local-lookup.example.org"],
            allowed_relay_urls=["wss://local-lookup.example.org"],
            auth_private_key=_secret(2),
            connect_factory=lambda *_args, **_kwargs: socket,
        )
    )

    assert result == ["wss://recipient-inbox.example.org"]
    assert [frame[0] for frame in socket.sent] == ["REQ", "AUTH", "REQ", "CLOSE"]
