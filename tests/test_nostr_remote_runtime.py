from __future__ import annotations

import queue
import time
from types import SimpleNamespace

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_dispatch import RemoteCLIRequestError
from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.nostr_remote_runtime import (
    NostrRemoteRuntime,
    dispatch_nostr_remote_inbox_event,
    start_nostr_remote_runtime,
    stop_nostr_remote_runtime,
)


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _setup_request(tmp_path, text: str = "hello"):
    sender_key = _secret(1)
    recipient_key = _secret(2)
    now = int(time.time())
    wrap = create_nip17_private_messages(
        text, sender_key, _public_key_bytes(recipient_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, recipient_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "pairings.sqlite3")
    pairings.pair(rumor["pubkey"], "phone", approved=True, paired_at=now)
    inbox.enqueue_verified_wrap(
        rumor["pubkey"],
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=now,
        session_id="active-session",
    )
    event = {
        "kind": "nostr_remote_request",
        "sender_pubkey": rumor["pubkey"],
        "rumor_id": rumor["id"],
        "created_at": rumor["created_at"],
        "session_id": "active-session",
        "text": text,
    }
    return inbox, pairings, recipient_key, event


def _public_key_bytes(secret: bytes) -> bytes:
    from uagent.nostr_nip17 import _public_key_x

    return _public_key_x(secret)


def test_durable_dispatch_stays_claimed_until_foreground_finishes(tmp_path) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        runtime = NostrRemoteRuntime(
            event_queue=queue.Queue(),
            private_key=private_key,
            relays=["wss://relay.example.org"],
            session_id="active-session",
            inbox_store=inbox,
            pairing_store=pairings,
        )
        action = runtime.dispatch_event(event, current_session_id="active-session")
        assert action.kind == "user"
        assert action.text == "hello"
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "dispatching"
        assert record.wrapped_event is not None
        assert runtime.finish_event(event, "completed")
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "completed"
        assert record.wrapped_event is None

        with pytest.raises(RemoteCLIRequestError, match="already claimed"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
    finally:
        inbox.close()
        pairings.close()


def test_durable_dispatch_rejects_revoked_sender_and_finishes_tombstone(
    tmp_path,
) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
        assert record.wrapped_event is None
    finally:
        inbox.close()
        pairings.close()


def test_durable_dispatch_rejects_queue_ciphertext_mismatch(tmp_path) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        event["text"] = "altered message"
        with pytest.raises(RemoteCLIRequestError, match="does not match"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
    finally:
        inbox.close()
        pairings.close()


def test_runtime_recovery_and_dispatch_are_scoped_to_session(
    tmp_path, monkeypatch
) -> None:
    import uagent.nostr_remote_runtime as runtime_module

    async def wait_for_stop(_relay, _key, _callback, *, stop_event, **_kwargs):
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", wait_for_stop)
    inbox, pairings, private_key, session_a_event = _setup_request(tmp_path)
    sender_key = _secret(1)
    other_wrap = create_nip17_private_messages(
        "session B request", sender_key, _public_key_bytes(private_key)
    )[0]
    other_rumor = unwrap_nip17_private_message(other_wrap, private_key)
    inbox.enqueue_verified_wrap(
        other_rumor["pubkey"],
        other_rumor["id"],
        other_wrap,
        created_at=other_rumor["created_at"],
        session_id="session-b",
    )
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=private_key,
        relays=["wss://relay.example.org"],
        session_id="session-b",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        with pytest.raises(RemoteCLIRequestError, match="different CLI session"):
            runtime.dispatch_event(session_a_event, current_session_id="session-b")
        session_a_record = inbox.get(
            session_a_event["sender_pubkey"], session_a_event["rumor_id"]
        )
        assert session_a_record is not None
        assert session_a_record.status == "pending"

        runtime.start()
        recovered = runtime.event_queue.get_nowait()
        assert recovered["rumor_id"] == other_rumor["id"]
        assert recovered["session_id"] == "session-b"
        assert runtime.event_queue.empty()
        assert inbox.list_pending(session_id="active-session")
    finally:
        runtime.stop()


def test_listener_runtime_stops_cleanly(tmp_path, monkeypatch) -> None:
    import uagent.nostr_remote_runtime as runtime_module

    async def wait_for_stop(_relay, _key, _callback, *, stop_event, **_kwargs):
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", wait_for_stop)
    monkeypatch.setattr("uagent.utils.paths.get_dbs_dir", lambda: tmp_path / "db")
    core = SimpleNamespace(event_queue=queue.Queue(), session_id="active-session")
    runtime = start_nostr_remote_runtime(
        core,
        private_key=_secret(2),
        relays=["wss://relay.example.org"],
    )
    try:
        assert runtime.status()["state"] == "running"
        assert callable(core._nostr_remote_authorize_sender)
        assert stop_nostr_remote_runtime(core)["stopped"]
        assert runtime.status()["state"] == "stopped"
        assert not hasattr(core, "_nostr_remote_runtime")
    finally:
        if not runtime._closed:
            stop_nostr_remote_runtime(core)


def test_listener_runtime_retries_failed_relay_independently(
    tmp_path, monkeypatch
) -> None:
    import asyncio
    import uagent.nostr_remote_runtime as runtime_module

    calls: dict[str, int] = {}

    async def flaky_listener(relay, _key, _callback, *, stop_event, **_kwargs):
        calls[relay] = calls.get(relay, 0) + 1
        if relay == "wss://broken.example.org" and calls[relay] == 1:
            raise RuntimeError("temporary relay failure")
        if relay == "wss://broken.example.org":
            stop_event.set()
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", flaky_listener)
    monkeypatch.setattr("uagent.utils.paths.get_dbs_dir", lambda: tmp_path / "db")
    inbox = SQLiteNostrInboxStore(tmp_path / "retry-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "retry-pairings.sqlite3")
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=_secret(2),
        relays=["wss://broken.example.org", "wss://healthy.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        asyncio.run(runtime._listen())
        assert calls["wss://broken.example.org"] == 2
        assert calls["wss://healthy.example.org"] == 1
        assert "temporary relay failure" in runtime._error
    finally:
        inbox.close()
        pairings.close()


def test_invalid_rumor_is_queued_by_reference_without_plaintext(tmp_path) -> None:
    event_queue = queue.Queue()
    inbox = SQLiteNostrInboxStore(tmp_path / "invalid-rumor-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "invalid-rumor-pairings.sqlite3")
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=_secret(2),
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        runtime._queue_rumor(
            {
                "kind": 14,
                "pubkey": "ab" * 32,
                "id": "cd" * 32,
                "created_at": int(time.time()),
                "content": "",
            }
        )
        queued = event_queue.get_nowait()
        assert queued["kind"] == "nostr_remote_request"
        assert queued["text"] == ""
    finally:
        inbox.close()
        pairings.close()


def test_receive_diagnostics_track_connections_and_drop_counts_in_memory(
    tmp_path,
) -> None:
    inbox = SQLiteNostrInboxStore(tmp_path / "diagnostics-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "diagnostics-pairings.sqlite3")
    relay = "wss://relay.example.org"
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=_secret(2),
        relays=[relay],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        runtime._record_receive_diagnostic(relay, "connected")
        runtime._record_receive_diagnostic(relay, "gift_wraps")
        runtime._record_receive_diagnostic(relay, "unauthorized")
        runtime._record_receive_diagnostic(relay, "queued")
        status = runtime.status()
        diagnostics = status["diagnostics"]
        assert diagnostics["connected_relays"] == 1
        assert diagnostics["gift_wraps"] == 1
        assert diagnostics["unauthorized"] == 1
        assert diagnostics["queued"] == 1
        assert diagnostics["decrypt_failed"] == 0
        assert set(diagnostics) == {
            "connected_relays",
            "gift_wraps",
            "invalid",
            "decrypt_failed",
            "unauthorized",
            "stale",
            "duplicate",
            "inbox_rejected",
            "queued",
            "delivery_rejections",
            "delivery_readback",
            "last_unwrap_error",
            "own_relay_list_accepted",
        }
        assert diagnostics["delivery_rejections"] == []
        assert diagnostics["delivery_readback"] == []
        assert diagnostics["last_unwrap_error"] == ""
        assert diagnostics["own_relay_list_accepted"] == 0
        runtime._record_receive_diagnostic(
            relay, "unwrap_error:gift wrap is not addressed to this recipient"
        )
        assert (
            runtime.status()["diagnostics"]["last_unwrap_error"]
            == "gift wrap is not addressed to this recipient"
        )
        runtime._record_receive_diagnostic(relay, "disconnected")
        assert runtime.status()["diagnostics"]["connected_relays"] == 0
    finally:
        inbox.close()
        pairings.close()


def test_publish_own_relay_list_counts_accepting_relays(tmp_path, monkeypatch) -> None:
    import asyncio

    import uagent.nostr_remote_transport as transport
    from uagent.nostr_nip17 import _public_key_x

    inbox = SQLiteNostrInboxStore(tmp_path / "relay-list-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "relay-list-pairings.sqlite3")
    relays = ["wss://relay-a.example", "wss://relay-b.example"]
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=_secret(2),
        relays=relays,
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    calls: list[tuple[str, dict]] = []

    async def fake_publish(relay_url, event, _key, *, allowed_relay_urls):
        calls.append((relay_url, event))
        return SimpleNamespace(
            accepted=relay_url == "wss://relay-a.example",
            relay_url=relay_url,
            event_id=event["id"],
            message="",
        )

    monkeypatch.setattr(transport, "publish_relay_list_event", fake_publish)
    try:
        asyncio.run(runtime._publish_own_relay_list())  # noqa: SLF001
        assert [relay for relay, _event in calls] == relays
        event = calls[0][1]
        assert event["kind"] == 10050
        assert event["pubkey"] == _public_key_x(_secret(2)).hex()
        assert event["tags"] == [["relay", relay] for relay in relays]
        assert runtime.status()["diagnostics"]["own_relay_list_accepted"] == 1
    finally:
        inbox.close()
        pairings.close()


def test_authenticated_incoming_message_is_echoed_once(tmp_path) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming

    inbox, pairings, private_key, request = _setup_request(
        tmp_path, text="hello from 0xChat"
    )
    event_queue = queue.Queue()
    core = SimpleNamespace(prompt_needs_redraw=False)
    seen: list[dict] = []
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=private_key,
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        incoming_message_display=lambda rumor: (
            seen.append(rumor),
            _display_nostr_incoming(core, rumor),
        ),
    )
    try:
        sender = request["sender_pubkey"]
        rumor = {
            "kind": 14,
            "pubkey": sender,
            "id": request["rumor_id"],
            "created_at": request["created_at"],
            "content": request["text"],
        }
        runtime._queue_rumor(rumor)
        assert event_queue.get_nowait()["text"] == "hello from 0xChat"
        assert len(seen) == 1
        assert core.prompt_needs_redraw is True

        # An invalid/empty command must never be printed to the terminal.
        runtime._queue_rumor({**rumor, "content": ""})
        assert len(seen) == 1
    finally:
        inbox.close()
        pairings.close()


def test_remote_cli_echo_stops_spinner_before_serialized_output(
    monkeypatch, capsys
) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    actions: list[str] = []

    class RecordingLock:
        def __enter__(self):
            actions.append("lock")
            return self

        def __exit__(self, *_args):
            actions.append("unlock")

    monkeypatch.setattr(spinner, "is_running", lambda: False)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: actions.append("stop_spinner"))
    core = SimpleNamespace(
        print_lock=RecordingLock(),
        _stream_line_open=True,
        _reasoning_stream_open=True,
        _prompt_line_open=True,
        _cli_prompt_toolkit_active=False,
        prompt_needs_redraw=False,
    )

    _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello from Nostr"})

    assert actions == ["stop_spinner", "lock", "unlock"]
    assert capsys.readouterr().out == (
        "\n[NOSTR] Received from abababababab: hello from Nostr\n"
    )
    assert core._stream_line_open is False
    assert core._reasoning_stream_open is False
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True


@pytest.mark.parametrize(
    ("busy", "stream_open", "expected_resume"),
    [(True, False, True), (False, False, False), (True, True, False)],
)
def test_remote_cli_echo_restores_only_active_busy_spinner(
    monkeypatch, capsys, busy, stream_open, expected_resume
) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    actions: list[str] = []

    class RecordingLock:
        def __enter__(self):
            actions.append("lock")
            return self

        def __exit__(self, *_args):
            actions.append("unlock")

    monkeypatch.setattr(spinner, "is_running", lambda: True)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: actions.append("stop"))
    monkeypatch.setattr(spinner, "start", lambda: actions.append("start"))
    core = SimpleNamespace(
        print_lock=RecordingLock(),
        status_busy=busy,
        _stream_line_open=stream_open,
        _reasoning_stream_open=False,
        _prompt_line_open=False,
        _cli_prompt_toolkit_active=False,
        prompt_needs_redraw=False,
    )
    _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello"})
    capsys.readouterr()

    assert actions == [
        "stop",
        "lock",
        "unlock",
        *(["start"] if expected_resume else []),
    ]


def test_remote_cli_echo_leaves_prompt_toolkit_redraw_to_patch_stdout(
    monkeypatch, capsys
) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    monkeypatch.setattr(spinner, "is_running", lambda: False)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: None)
    core = SimpleNamespace(
        _cli_prompt_toolkit_active=True,
        _prompt_line_open=True,
        prompt_needs_redraw=False,
    )

    _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello"})

    assert "[NOSTR] Received from abababababab: hello" in capsys.readouterr().out
    assert core._prompt_line_open is True
    assert core.prompt_needs_redraw is False


def test_remote_cli_echo_escapes_terminal_controls(capsys) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming

    core = SimpleNamespace(prompt_needs_redraw=False)
    _display_nostr_incoming(
        core,
        {"pubkey": "ab" * 32, "content": "hello\n\x1b[31mRED\x1b[0m"},
    )
    printed = capsys.readouterr().out
    assert "[NOSTR] Received from abababababab: hello" in printed
    assert "RED" in printed
    assert "\x1b" not in printed
    assert "hello\n" not in printed
    assert core.prompt_needs_redraw is True
