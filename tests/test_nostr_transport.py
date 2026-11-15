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
