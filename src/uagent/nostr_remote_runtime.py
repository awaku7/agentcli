"""Opt-in CLI bridge for the experimental NIP-17 inbox and direct replies."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from .nostr_nip17 import unwrap_nip17_private_message
from .nostr_remote_dispatch import (
    RemoteCLIRequestError,
    RemoteCLIAction,
    authorize_nostr_remote_request,
    enqueue_nostr_remote_request,
)
from .nostr_remote_inbox import InboxRecord, SQLiteNostrInboxStore
from .nostr_remote_pairing import SQLitePairingStore
from .nostr_remote_transport import listen_nip17_messages


def dispatch_nostr_remote_inbox_event(
    event: dict[str, Any],
    *,
    inbox_store: SQLiteNostrInboxStore,
    pairing_store: SQLitePairingStore,
    private_key: bytes,
    current_session_id: str,
) -> RemoteCLIAction:
    """Claim, authenticate, reauthorize, and terminally record one inbox item."""
    if not isinstance(event, dict) or event.get("session_id") != current_session_id:
        raise RemoteCLIRequestError("remote request belongs to a different CLI session")
    sender = event.get("sender_pubkey")
    rumor_id = event.get("rumor_id")
    try:
        record = inbox_store.claim(sender, rumor_id, session_id=current_session_id)
    except (TypeError, ValueError) as exc:
        raise RemoteCLIRequestError("invalid durable inbox reference") from exc
    if record is None:
        raise RemoteCLIRequestError("remote inbox item is missing or already claimed")

    try:
        if not isinstance(record.wrapped_event, dict):
            raise RemoteCLIRequestError("durable inbox ciphertext is unavailable")
        rumor = unwrap_nip17_private_message(record.wrapped_event, private_key)
        if (
            rumor.get("pubkey") != record.sender_pubkey
            or rumor.get("id") != record.rumor_id
            or rumor.get("created_at") != record.created_at
            or rumor.get("pubkey") != event.get("sender_pubkey")
            or rumor.get("id") != event.get("rumor_id")
            or rumor.get("created_at") != event.get("created_at")
            or rumor.get("content") != event.get("text")
            or record.session_id != event.get("session_id")
        ):
            raise RemoteCLIRequestError("queued request does not match durable inbox")
        action = authorize_nostr_remote_request(
            event,
            current_session_id=current_session_id,
            authorize_sender=pairing_store.is_authorized,
        )
    except RemoteCLIRequestError:
        inbox_store.finish(record.sender_pubkey, record.rumor_id, "rejected")
        raise
    except Exception as exc:
        inbox_store.finish(record.sender_pubkey, record.rumor_id, "failed")
        raise RemoteCLIRequestError("durable inbox verification failed") from exc

    # Leave the row in dispatching until the foreground CLI has actually run
    # the action. A crash or command failure after validation must remain
    # visible for manual reconciliation, not look like a successful delivery.
    return action


class NostrRemoteRuntime:
    """Manage one opt-in listener set for a CLI session."""

    def __init__(
        self,
        *,
        event_queue: Any,
        private_key: bytes,
        relays: list[str],
        session_id: str,
        inbox_store: SQLiteNostrInboxStore,
        pairing_store: SQLitePairingStore,
    ) -> None:
        self.event_queue = event_queue
        self.private_key = private_key
        self.relays = tuple(dict.fromkeys(relays))
        self.session_id = session_id
        self.inbox_store = inbox_store
        self.pairing_store = pairing_store
        self._state_lock = threading.Lock()
        self._state = "stopped"
        self._error = ""
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self._closed = False

    @property
    def authorize_sender(self):
        return self.pairing_store.is_authorized

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            state = self._state
            error = self._error
            closed = self._closed
        pending = (
            0
            if closed
            else len(
                self.inbox_store.list_pending(limit=1000, session_id=self.session_id)
            )
        )
        dispatching = (
            0
            if closed
            else len(
                self.inbox_store.list_dispatching(
                    limit=1000, session_id=self.session_id
                )
            )
        )
        return {
            "state": state,
            "relays": list(self.relays),
            "session_id": self.session_id,
            "error": error,
            "pending": pending,
            "dispatching": dispatching,
        }

    def _queue_rumor(self, rumor: dict[str, Any]) -> None:
        try:
            enqueue_nostr_remote_request(
                self.event_queue, rumor, target_session_id=self.session_id
            )
        except RemoteCLIRequestError:
            # Invalid/oversized requests from an approved sender must not take
            # down the listener. Queue only the durable ID so the foreground
            # dispatcher claims and rejects the ciphertext without echoing it.
            self.event_queue.put(
                {
                    "kind": "nostr_remote_request",
                    "sender_pubkey": rumor.get("pubkey"),
                    "rumor_id": rumor.get("id"),
                    "created_at": rumor.get("created_at"),
                    "session_id": self.session_id,
                    "text": "",
                }
            )

    def _queue_record(self, record: InboxRecord) -> None:
        try:
            if not isinstance(record.wrapped_event, dict):
                raise ValueError("missing ciphertext")
            rumor = unwrap_nip17_private_message(record.wrapped_event, self.private_key)
            enqueue_nostr_remote_request(
                self.event_queue, rumor, target_session_id=record.session_id
            )
        except Exception:
            # Let the foreground claim and terminally reject a damaged pending
            # row instead of silently leaving it stuck forever.
            self.event_queue.put(
                {
                    "kind": "nostr_remote_request",
                    "sender_pubkey": record.sender_pubkey,
                    "rumor_id": record.rumor_id,
                    "created_at": record.created_at,
                    "session_id": record.session_id,
                    "text": "",
                }
            )

    def start(self) -> None:
        if not self.relays:
            raise ValueError("at least one configured Nostr relay is required")
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("an active CLI session is required")
        with self._state_lock:
            if self._state == "running":
                return
            if self._closed:
                raise RuntimeError("Nostr remote runtime is already closed")
            self._state = "running"
            self._error = ""
        for record in self.inbox_store.list_pending(
            limit=1000, session_id=self.session_id
        ):
            self._queue_record(record)
        self._thread = threading.Thread(
            target=self._thread_main, name="uag-nostr-remote", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=2.0)

    async def _listen_relay(self, relay: str, index: int) -> None:
        stop_event = self._stop_event
        if stop_event is None:
            raise RuntimeError("Nostr remote listener is not initialized")
        retry_delay = 1.0
        while not stop_event.is_set():
            try:
                await listen_nip17_messages(
                    relay,
                    self.private_key,
                    self._queue_rumor,
                    authorize_sender=self.authorize_sender,
                    inbox_store=self.inbox_store,
                    target_session_id=self.session_id,
                    stop_event=stop_event,
                )
                if stop_event.is_set():
                    return
                raise RuntimeError("Nostr listener stopped unexpectedly")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._error = f"{relay}: {type(exc).__name__}: {str(exc)[:200]}"
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=retry_delay)
                except asyncio.TimeoutError:
                    pass
                retry_delay = min(retry_delay * 2, 30.0)

    async def _listen(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._ready.set()
        tasks = [
            asyncio.create_task(
                self._listen_relay(relay, index),
                name=f"uag-nostr-remote-{index}",
            )
            for index, relay in enumerate(self.relays)
        ]
        stop_task = asyncio.create_task(self._stop_event.wait())
        try:
            done, pending = await asyncio.wait(
                [*tasks, stop_task], return_when=asyncio.FIRST_COMPLETED
            )
            if stop_task not in done:
                failed = next((task for task in done if task is not stop_task), None)
                if failed is not None:
                    error = failed.exception()
                    if error is not None:
                        raise error
                    raise RuntimeError("Nostr listener stopped unexpectedly")
        finally:
            for task in [*tasks, stop_task]:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, stop_task, return_exceptions=True)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._listen())
        except Exception as exc:
            with self._state_lock:
                self._state = "error"
                self._error = f"{type(exc).__name__}: {str(exc)[:240]}"
        else:
            with self._state_lock:
                self._state = "stopped"
        finally:
            self._loop = None
            self._stop_event = None

    def dispatch_event(
        self, event: dict[str, Any], *, current_session_id: str
    ) -> RemoteCLIAction:
        return dispatch_nostr_remote_inbox_event(
            event,
            inbox_store=self.inbox_store,
            pairing_store=self.pairing_store,
            private_key=self.private_key,
            current_session_id=current_session_id,
        )

    def finish_event(self, event: dict[str, Any], outcome: str) -> bool:
        """Finalize a claimed inbox item after its foreground action completes."""
        if not isinstance(event, dict):
            raise ValueError("remote inbox event reference is invalid")
        sender = event.get("sender_pubkey")
        rumor_id = event.get("rumor_id")
        if not isinstance(sender, str) or not isinstance(rumor_id, str):
            raise ValueError("remote inbox event reference is invalid")
        if outcome not in {"completed", "rejected", "failed"}:
            raise ValueError("invalid remote inbox outcome")
        return self.inbox_store.finish(sender, rumor_id, outcome)

    def send_reply(self, request_event: dict[str, Any], text: str) -> dict[str, Any]:
        """Send a short NIP-17 reply to a still-authorized request sender.

        The recipient relay list is fetched only from the locally configured
        relays, signature-verified, then intersected with the same local egress
        allowlist. This prototype sends synchronously and does not retain an
        outbox for retries.
        """
        from .nostr_nip17 import _public_key_x, create_nip17_private_messages
        from .nostr_remote_transport import (
            fetch_nip17_relay_list,
            publish_nip17_gift_wraps,
        )

        if not isinstance(request_event, dict):
            raise ValueError("remote request metadata is invalid")
        sender = request_event.get("sender_pubkey")
        if not isinstance(sender, str):
            raise ValueError("remote sender key is invalid")
        try:
            sender = bytes.fromhex(sender).hex()
        except ValueError as exc:
            raise ValueError("remote sender key is invalid") from exc
        if len(bytes.fromhex(sender)) != 32 or not self.pairing_store.is_authorized(
            sender
        ):
            raise PermissionError("remote sender is no longer paired")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("reply text must be non-empty text")
        suffix = " [Reply truncated]"
        encoded = text.encode("utf-8")
        if len(encoded) > 16_384:
            encoded = encoded[: 16_384 - len(suffix.encode("utf-8"))]
            text = encoded.decode("utf-8", errors="ignore") + suffix

        remote_relays = asyncio.run(
            fetch_nip17_relay_list(
                sender,
                self.relays,
                allowed_relay_urls=self.relays,
                auth_private_key=self.private_key,
                timeout=3.0,
            )
        )
        allowed = set(self.relays)
        recipient_relays = [url for url in remote_relays if url in allowed]
        if not recipient_relays:
            raise ValueError("no recipient inbox relay is permitted by local policy")

        own_pubkey = _public_key_x(self.private_key).hex()
        events = create_nip17_private_messages(
            text, self.private_key, bytes.fromhex(sender)
        )
        relay_lists = {sender: recipient_relays[:1]}
        if sender != own_pubkey:
            relay_lists[own_pubkey] = [self.relays[0]]
        deliveries = asyncio.run(
            publish_nip17_gift_wraps(
                events,
                relay_lists,
                self.private_key,
                allowed_relay_urls=self.relays,
                timeout=3.0,
            )
        )
        if not deliveries or not all(delivery.accepted for delivery in deliveries):
            raise RuntimeError("one or more NIP-17 reply deliveries were rejected")
        return {
            "ok": True,
            "event_ids": [delivery.event_id for delivery in deliveries],
        }

    def stop(self, *, timeout: float = 5.0) -> dict[str, Any]:
        loop = self._loop
        stop_event = self._stop_event
        thread = self._thread
        if loop is not None and stop_event is not None:
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, timeout))
        stopped = thread is None or not thread.is_alive()
        if stopped:
            with self._state_lock:
                self._state = "stopped"
                self._closed = True
            self.inbox_store.close()
            self.pairing_store.close()
        state = "stopped" if stopped else self.status()["state"]
        return {"state": state, "stopped": stopped}


def create_nostr_remote_runtime(
    *,
    core: Any,
    private_key: bytes,
    relays: list[str],
) -> NostrRemoteRuntime:
    """Create a runtime using UAG's persistent SQLite directories."""
    from .nostr_nip17 import _validate_private_key, _validate_relay_uri
    from .utils.paths import get_dbs_dir

    private_key = _validate_private_key(private_key)
    if not isinstance(relays, list) or not relays or len(relays) > 10:
        raise ValueError("between one and ten configured Nostr relays are required")
    relays = list(dict.fromkeys(_validate_relay_uri(relay) for relay in relays))
    event_queue = getattr(core, "event_queue", None)
    if not callable(getattr(event_queue, "put", None)):
        raise TypeError("CLI event queue is unavailable")
    session_id = getattr(core, "session_id", None)
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("there is no active CLI session")
    db_dir = get_dbs_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    inbox_store = SQLiteNostrInboxStore(db_dir / "nostr_remote_inbox.sqlite3")
    try:
        pairing_store = SQLitePairingStore(db_dir / "nostr_remote_pairings.sqlite3")
    except Exception:
        inbox_store.close()
        raise
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=private_key,
        relays=relays,
        session_id=session_id,
        inbox_store=inbox_store,
        pairing_store=pairing_store,
    )
    return runtime


def stop_nostr_remote_runtime(core: Any) -> dict[str, Any]:
    runtime = getattr(core, "_nostr_remote_runtime", None)
    if not isinstance(runtime, NostrRemoteRuntime):
        return {"state": "stopped", "stopped": True}
    result = runtime.stop()
    if result["stopped"]:
        for name in ("_nostr_remote_runtime", "_nostr_remote_authorize_sender"):
            try:
                delattr(core, name)
            except AttributeError:
                pass
    return result


def start_nostr_remote_runtime(
    core: Any, *, private_key: bytes, relays: list[str]
) -> NostrRemoteRuntime:
    existing = getattr(core, "_nostr_remote_runtime", None)
    if isinstance(existing, NostrRemoteRuntime):
        if existing.status()["state"] == "running":
            return existing
        stop_nostr_remote_runtime(core)
    runtime = create_nostr_remote_runtime(
        core=core, private_key=private_key, relays=relays
    )
    setattr(core, "_nostr_remote_runtime", runtime)
    setattr(core, "_nostr_remote_authorize_sender", runtime.authorize_sender)
    try:
        runtime.start()
    except Exception:
        for name in ("_nostr_remote_runtime", "_nostr_remote_authorize_sender"):
            try:
                delattr(core, name)
            except AttributeError:
                pass
        runtime.inbox_store.close()
        runtime.pairing_store.close()
        raise
    return runtime
