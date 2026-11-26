from __future__ import annotations

import asyncio

from uagent.tools import nostr_transport


def test_connect_does_not_start_bitchat_beacon_or_discovery(monkeypatch) -> None:
    transport = nostr_transport.NostrTransport(
        priv_hex="01" * 32,
        pub_hex="02" * 32,
    )
    transport.relays = []
    transport._stop_event.set()
    scheduled: list[str] = []

    class FakeTask:
        def cancel(self) -> None:
            pass

    def record_task(coro):
        scheduled.append(coro.cr_code.co_name)
        coro.close()
        return FakeTask()

    monkeypatch.setattr(nostr_transport.asyncio, "create_task", record_task)
    asyncio.run(transport._run())

    assert "_beacon_loop" not in scheduled
    assert "_discovery_subscribe" not in scheduled


def test_relay_failure_is_reported_once_until_it_recovers(monkeypatch) -> None:
    """A relay that keeps rejecting must not print the same
    "disconnected" line on every retry; it reports again only
    after a successful connection in between."""
    transport = nostr_transport.NostrTransport(
        priv_hex="01" * 32,
        pub_hex="02" * 32,
    )
    shown: list[str] = []
    monkeypatch.setattr(nostr_transport, "_notify_display", shown.append)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(nostr_transport.asyncio, "sleep", no_sleep)

    url = "wss://relay.example"
    attempts = {"count": 0}
    behaviour: list[str] = []

    class FakeSocket:
        async def send(self, _data: str) -> None:
            return None

        def __aiter__(self):
            async def empty():
                if False:
                    yield None

            return empty()

    class FakeConnect:
        def __init__(self, mode: str) -> None:
            self._mode = mode

        async def __aenter__(self):
            attempts["count"] += 1
            if attempts["count"] >= 3:
                transport._stop_event.set()
            if self._mode == "fail":
                raise OSError("server rejected WebSocket connection: HTTP 503")
            return FakeSocket()

        async def __aexit__(self, *exc) -> bool:
            return False

    def fake_connect(_url, **_kwargs):
        return FakeConnect(behaviour.pop(0))

    monkeypatch.setattr("websockets.connect", fake_connect)

    # Three failures in a row: exactly one line is shown.
    behaviour.extend(["fail", "fail", "fail"])
    asyncio.run(transport._connect_relay(url))
    assert attempts["count"] == 3
    assert shown == [
        f"[nostr] Relay {url} disconnected: "
        "server rejected WebSocket connection: HTTP 503"
    ]

    # A successful connection resets the report; the next failure
    # is shown again (once).
    transport._stop_event.clear()
    attempts["count"] = 0
    behaviour.extend(["ok"])
    asyncio.run(transport._connect_relay(url))
    assert shown[-1] == f"[nostr] Connected to {url}"
    assert url not in transport._relay_failure_reported

    transport._stop_event.clear()
    attempts["count"] = 0
    behaviour.extend(["fail", "fail", "fail"])
    asyncio.run(transport._connect_relay(url))
    assert shown.count(shown[0]) == 2
    assert len(shown) == 3
