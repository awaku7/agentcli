from __future__ import annotations

import queue
import threading
import time
from threading import Lock
from types import SimpleNamespace

from uagent.cli_impl.main import _nostr_remote_status_text
from uagent.nostr_nip17 import (
    _public_key_x,
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.nostr_remote_runtime import NostrRemoteRuntime


def test_status_summary_includes_cli_activity_and_remote_queue_state() -> None:
    runtime = SimpleNamespace(
        status=lambda: {
            "state": "running",
            "pending": 2,
            "dispatching": 1,
            "outbox_pending": 3,
        }
    )
    core = SimpleNamespace(
        status_lock=Lock(),
        status_busy=True,
        status_label="LLM\nworking",
        session_id="active-session",
        human_ask_lock=Lock(),
        human_ask_active=True,
        _sub_agent_job_manager=SimpleNamespace(
            running_count=lambda *, owner: 3 if owner == "owner" else 0
        ),
        _sub_agent_job_owner="owner",
        _nostr_remote_runtime=runtime,
    )

    status = _nostr_remote_status_text(core)

    assert "CLI: busy" in status
    assert "Activity: LLM working" in status
    assert "Session: active-session" in status
    assert "Waiting for human input: yes" in status
    assert "Background jobs: 3" in status
    assert "Nostr remote listener: running" in status
    assert "Pending remote requests: 2" in status
    assert "Requests needing reconciliation: 1" in status
    assert "Pending encrypted replies: 3" in status
    assert "LLM\nworking" not in status


def test_live_status_query_bypasses_busy_foreground_event_queue(tmp_path) -> None:
    sender_key = (1).to_bytes(32, "big")
    local_key = (2).to_bytes(32, "big")
    sender_pubkey = _public_key_x(sender_key).hex()
    now = int(time.time())
    wrap = create_nip17_private_messages(
        "/uag status", sender_key, _public_key_x(local_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, local_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "status-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "status-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=now)
    assert inbox.enqueue_verified_wrap(
        sender_pubkey,
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=now,
        session_id="active-session",
    )
    event_queue: queue.Queue[dict[str, object]] = queue.Queue()
    foreground_event = {"kind": "user", "text": "foreground turn still running"}
    event_queue.put(foreground_event)
    replied = threading.Event()
    replies: list[tuple[dict[str, object], str]] = []
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=local_key,
        relays=["wss://relay.example"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        status_provider=lambda: "CLI: busy\nWaiting for human input: yes",
        current_session_id_provider=lambda: "active-session",
    )

    def capture_reply(event: dict[str, object], text: str) -> dict[str, object]:
        replies.append((event, text))
        replied.set()
        return {"ok": True}

    runtime.send_reply = capture_reply  # type: ignore[method-assign]
    worker = threading.Thread(target=runtime._status_worker, daemon=True)
    runtime._status_thread = worker
    worker.start()
    try:
        runtime._queue_rumor(rumor)
        assert replied.wait(timeout=2.0)
        assert event_queue.get_nowait() == foreground_event
        assert event_queue.empty()
        assert replies[0][1] == "CLI: busy\nWaiting for human input: yes"
        record = inbox.get(sender_pubkey, rumor["id"])
        assert record is not None
        assert record.status == "completed"
        assert record.wrapped_event is None
    finally:
        runtime._status_stop.set()
        worker.join(timeout=1.0)
        inbox.close()
        pairings.close()


def test_status_summary_fails_closed_to_sanitized_unavailable_state() -> None:
    core = SimpleNamespace(
        status_lock=Lock(),
        status_busy=False,
        status_label="",
        human_ask_lock=Lock(),
        human_ask_active=False,
        _nostr_remote_runtime=SimpleNamespace(
            status=lambda: (_ for _ in ()).throw(RuntimeError("private detail"))
        ),
    )

    status = _nostr_remote_status_text(core)

    assert "CLI: idle" in status
    assert "Activity:" not in status
    assert "Nostr remote listener: status unavailable" in status
    assert "private detail" not in status


def test_status_queue_backpressure_recovers_durable_request_without_cli_fallback(
    tmp_path,
) -> None:
    sender_key = (1).to_bytes(32, "big")
    local_key = (2).to_bytes(32, "big")
    sender_pubkey = _public_key_x(sender_key).hex()
    now = int(time.time())
    wrap = create_nip17_private_messages(
        "/uag status", sender_key, _public_key_x(local_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, local_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "status-pressure-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "status-pressure-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=now)
    assert inbox.enqueue_verified_wrap(
        sender_pubkey,
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=now,
        session_id="active-session",
    )
    event_queue: queue.Queue[dict[str, object]] = queue.Queue()
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=local_key,
        relays=["wss://relay.example"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        status_provider=lambda: "CLI: busy",
        current_session_id_provider=lambda: "active-session",
    )
    worker_release = threading.Event()
    worker = threading.Thread(target=worker_release.wait, daemon=True)
    runtime._status_queue = queue.Queue(maxsize=1)
    runtime._status_queue.put_nowait({"kind": "occupied"})
    runtime._status_thread = worker
    worker.start()
    try:
        runtime._queue_rumor(rumor)
        assert event_queue.empty()
        assert runtime._status_recovery_needed.is_set()

        runtime._status_queue.get_nowait()
        runtime._status_recovery_needed.clear()
        runtime._recover_pending_status_events()
        recovered = runtime._status_queue.get_nowait()
        assert recovered["text"] == "/uag status"
        assert recovered["rumor_id"] == rumor["id"]
        assert event_queue.empty()
    finally:
        worker_release.set()
        worker.join(timeout=1.0)
        inbox.close()
        pairings.close()
