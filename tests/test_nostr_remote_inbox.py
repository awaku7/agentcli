from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_inbox import InboxFullError, SQLiteNostrInboxStore


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


RECIPIENT_PUBLIC = bytes.fromhex(
    "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
)


def _authenticated_wrap(text: str = "private inbox payload"):
    wrap = create_nip17_private_messages(
        text, _secret(1), RECIPIENT_PUBLIC, now=1_700_000_000
    )[0]
    rumor = unwrap_nip17_private_message(wrap, _secret(2))
    return wrap, rumor


def _enqueue(store, wrap, rumor, session_id="active-session"):
    return store.enqueue_verified_wrap(
        rumor["pubkey"],
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=1_700_000_010,
        session_id=session_id,
    )


def test_verified_wrap_is_persisted_encrypted_and_deduplicated(tmp_path) -> None:
    path = tmp_path / "remote-inbox.sqlite3"
    cleartext = "private inbox payload must not be stored"
    wrap, rumor = _authenticated_wrap(cleartext)

    with SQLiteNostrInboxStore(path) as store:
        assert _enqueue(store, wrap, rumor)
        assert not _enqueue(store, wrap, rumor)
        rows = store.list_pending()
        assert len(rows) == 1
        assert rows[0].sender_pubkey == rumor["pubkey"]
        assert rows[0].rumor_id == rumor["id"]
        assert rows[0].session_id == "active-session"
        assert rows[0].status == "pending"
        assert rows[0].wrapped_event == wrap
        assert cleartext not in json.dumps(rows[0].wrapped_event)

    # The SQLite database itself contains encrypted gift-wrap content, not the
    # decrypted DM body.
    for suffix in ("", "-wal"):
        db_file = tmp_path / f"remote-inbox.sqlite3{suffix}"
        if db_file.exists():
            assert cleartext.encode("utf-8") not in db_file.read_bytes()

    with SQLiteNostrInboxStore(path) as reopened:
        assert reopened.list_pending()[0].wrapped_event == wrap
        assert not _enqueue(reopened, wrap, rumor)


def test_claim_transition_is_atomic_and_terminal_finish_erases_ciphertext(
    tmp_path,
) -> None:
    path = tmp_path / "remote-inbox-state.sqlite3"
    wrap, rumor = _authenticated_wrap()
    with SQLiteNostrInboxStore(path) as store:
        assert _enqueue(store, wrap, rumor)
        claimed = store.claim(rumor["pubkey"], rumor["id"], claimed_at=1_700_000_020)
        assert claimed is not None
        assert claimed.status == "dispatching"
        assert claimed.claimed_at == 1_700_000_020
        assert claimed.wrapped_event == wrap
        assert store.claim(rumor["pubkey"], rumor["id"]) is None
        assert store.finish(
            rumor["pubkey"], rumor["id"], "completed", finished_at=1_700_000_030
        )
        assert not store.finish(rumor["pubkey"], rumor["id"], "failed")
        finished = store.get(rumor["pubkey"], rumor["id"])
        assert finished is not None
        assert finished.status == "completed"
        assert finished.finished_at == 1_700_000_030
        assert finished.wrapped_event is None
        assert store.list_pending() == []
        assert not _enqueue(store, wrap, rumor)

    with SQLiteNostrInboxStore(path) as reopened:
        finished = reopened.get(rumor["pubkey"], rumor["id"])
        assert finished is not None and finished.status == "completed"
        assert finished.wrapped_event is None


def test_dispatching_record_survives_restart_without_automatic_retry(tmp_path) -> None:
    path = tmp_path / "remote-inbox-crash.sqlite3"
    wrap, rumor = _authenticated_wrap()
    with SQLiteNostrInboxStore(path) as store:
        assert _enqueue(store, wrap, rumor)
        assert store.claim(rumor["pubkey"], rumor["id"], claimed_at=1_700_000_020)

    with SQLiteNostrInboxStore(path) as reopened:
        assert reopened.list_pending() == []
        uncertain = reopened.list_dispatching()
        assert len(uncertain) == 1
        assert uncertain[0].wrapped_event == wrap
        assert reopened.claim(rumor["pubkey"], rumor["id"]) is None


def test_pending_capacity_fails_closed_but_duplicate_is_still_idempotent(
    tmp_path,
) -> None:
    wrap_a, rumor_a = _authenticated_wrap("first")
    wrap_b, rumor_b = _authenticated_wrap("second")
    # Use distinct rumor IDs while keeping a valid NIP-17 wrap for each request.
    with SQLiteNostrInboxStore(
        tmp_path / "remote-inbox-capacity.sqlite3", max_pending=1
    ) as store:
        assert _enqueue(store, wrap_a, rumor_a)
        assert not _enqueue(store, wrap_a, rumor_a)
        with pytest.raises(InboxFullError):
            _enqueue(store, wrap_b, rumor_b)
        assert len(store.list_pending()) == 1


def test_inbox_claim_has_one_winner_across_store_connections(tmp_path) -> None:
    path = tmp_path / "remote-inbox-concurrent.sqlite3"
    wrap, rumor = _authenticated_wrap()
    store_a = SQLiteNostrInboxStore(path)
    store_b = SQLiteNostrInboxStore(path)
    try:
        assert _enqueue(store_a, wrap, rumor)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda store: store.claim(rumor["pubkey"], rumor["id"]),
                    (store_a, store_b),
                )
            )
        assert sum(result is not None for result in results) == 1
        assert len(store_a.list_dispatching()) == 1
    finally:
        store_a.close()
        store_b.close()


def test_inbox_rejects_invalid_metadata_and_wraps(tmp_path) -> None:
    wrap, rumor = _authenticated_wrap()
    with SQLiteNostrInboxStore(
        tmp_path / "remote-inbox-validation.sqlite3", max_wrap_bytes=128
    ) as store:
        with pytest.raises(ValueError, match="size limit"):
            _enqueue(store, wrap, rumor)
        with pytest.raises(ValueError, match="kind-1059"):
            store.enqueue_verified_wrap(
                rumor["pubkey"],
                rumor["id"],
                {"kind": 14, "content": "not a wrap"},
                created_at=rumor["created_at"],
                session_id="active-session",
            )
        with pytest.raises(ValueError):
            store.enqueue_verified_wrap(
                "not-a-key",
                rumor["id"],
                wrap,
                created_at=rumor["created_at"],
                session_id="active-session",
            )
        with pytest.raises(ValueError, match="canonical NIP-01"):
            store.enqueue_verified_wrap(
                rumor["pubkey"],
                rumor["id"],
                {**wrap, "plaintext": "must never reach the inbox"},
                created_at=rumor["created_at"],
                session_id="active-session",
            )
        with pytest.raises(ValueError):
            store.enqueue_verified_wrap(
                rumor["pubkey"],
                rumor["id"],
                wrap,
                created_at=True,
                session_id="active-session",
            )
        with pytest.raises(ValueError):
            store.enqueue_verified_wrap(
                rumor["pubkey"],
                rumor["id"],
                wrap,
                created_at=rumor["created_at"],
                session_id="",
            )


def test_legacy_inbox_schema_migrates_and_enforces_payload_budget(tmp_path) -> None:
    path = tmp_path / "remote-inbox-legacy.sqlite3"
    wrap_a, rumor_a = _authenticated_wrap("one")
    wrap_b, rumor_b = _authenticated_wrap("two")
    _, terminal_rumor = _authenticated_wrap("already terminal")
    serialized = json.dumps(wrap_a, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )

    # This is the first inbox schema, before wrapped_event_bytes and the
    # cumulative-budget metadata table were added.
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE nostr_remote_inbox (
            sender_pubkey TEXT NOT NULL,
            rumor_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            received_at INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL,
            wrapped_event_json TEXT,
            claimed_at INTEGER,
            finished_at INTEGER,
            PRIMARY KEY (sender_pubkey, rumor_id)
        )
        """)
    connection.execute(
        "INSERT INTO nostr_remote_inbox VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            rumor_a["pubkey"],
            rumor_a["id"],
            rumor_a["created_at"],
            1_700_000_010,
            "active-session",
            "pending",
            serialized.decode("utf-8"),
            None,
            None,
        ),
    )
    connection.execute(
        "INSERT INTO nostr_remote_inbox VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            terminal_rumor["pubkey"],
            terminal_rumor["id"],
            terminal_rumor["created_at"],
            1_700_000_011,
            "active-session",
            "completed",
            None,
            1_700_000_010,
            1_700_000_011,
        ),
    )
    connection.commit()
    connection.close()

    with SQLiteNostrInboxStore(
        path, max_total_payload_bytes=len(serialized)
    ) as migrated:
        record = migrated.get(rumor_a["pubkey"], rumor_a["id"])
        assert record is not None
        assert record.wrapped_event == wrap_a
        terminal = migrated.get(terminal_rumor["pubkey"], terminal_rumor["id"])
        assert terminal is not None
        assert terminal.status == "completed"
        assert terminal.wrapped_event is None
        payload_budget = migrated._connection.execute(
            "SELECT value FROM nostr_remote_inbox_meta WHERE key = 'total_payload_bytes'"
        ).fetchone()[0]
        assert payload_budget == len(serialized)
        assert not _enqueue(migrated, wrap_a, rumor_a)
        with pytest.raises(InboxFullError, match="cumulative encrypted-byte capacity"):
            _enqueue(migrated, wrap_b, rumor_b)


def test_finish_only_accepts_terminal_outcomes(tmp_path) -> None:
    wrap, rumor = _authenticated_wrap()
    with SQLiteNostrInboxStore(tmp_path / "remote-inbox-finish.sqlite3") as store:
        assert _enqueue(store, wrap, rumor)
        assert not store.finish(rumor["pubkey"], rumor["id"], "completed")
        with pytest.raises(ValueError):
            store.finish(rumor["pubkey"], rumor["id"], "pending")
        assert store.claim(rumor["pubkey"], rumor["id"])
        assert store.finish(rumor["pubkey"], rumor["id"], "rejected")


def test_inbox_caps_total_records_and_encrypted_storage(tmp_path) -> None:
    wrap_a, rumor_a = _authenticated_wrap("one")
    wrap_b, rumor_b = _authenticated_wrap("two")
    serialized_size = len(
        json.dumps(wrap_a, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )

    with SQLiteNostrInboxStore(
        tmp_path / "remote-inbox-byte-cap.sqlite3",
        max_total_payload_bytes=serialized_size - 1,
    ) as store:
        with pytest.raises(InboxFullError, match="cumulative encrypted-byte capacity"):
            _enqueue(store, wrap_a, rumor_a)

    # Completing a request erases its ciphertext, but does not refund the
    # lifetime storage budget: SQLite may retain freed pages in the database.
    with SQLiteNostrInboxStore(
        tmp_path / "remote-inbox-cumulative-cap.sqlite3",
        max_total_payload_bytes=serialized_size,
    ) as store:
        assert _enqueue(store, wrap_a, rumor_a)
        assert store.claim(rumor_a["pubkey"], rumor_a["id"])
        assert store.finish(rumor_a["pubkey"], rumor_a["id"], "completed")

    with SQLiteNostrInboxStore(
        tmp_path / "remote-inbox-cumulative-cap.sqlite3",
        max_total_payload_bytes=serialized_size,
    ) as reopened:
        with pytest.raises(InboxFullError, match="cumulative encrypted-byte capacity"):
            _enqueue(reopened, wrap_b, rumor_b)

    with SQLiteNostrInboxStore(
        tmp_path / "remote-inbox-record-cap.sqlite3", max_records=1
    ) as store:
        assert _enqueue(store, wrap_a, rumor_a)
        assert store.claim(rumor_a["pubkey"], rumor_a["id"])
        assert store.finish(rumor_a["pubkey"], rumor_a["id"], "completed")
        with pytest.raises(InboxFullError, match="deduplication capacity"):
            _enqueue(store, wrap_b, rumor_b)
