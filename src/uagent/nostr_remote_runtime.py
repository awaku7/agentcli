"""Opt-in CLI bridge for the experimental NIP-17 inbox and direct replies."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from typing import Any, Callable

from .nostr_nip17 import unwrap_nip17_private_message
from .nostr_remote_dispatch import (
    RemoteCLIRequestError,
    RemoteCLIAction,
    authorize_nostr_remote_request,
    create_nostr_remote_request_event,
    is_nostr_remote_status_request,
)
from .nostr_remote_inbox import InboxRecord, SQLiteNostrInboxStore
from .nostr_remote_outbox import OutboxRecord, SQLiteNostrOutboxStore
from .nostr_remote_pairing import SQLitePairingStore
from .nostr_remote_transport import listen_nip17_messages


def format_nostr_remote_status(core: Any) -> str:
    """Format a bounded, sanitized CLI status summary for a paired device."""
    busy = False
    label = ""
    try:
        with core.status_lock:
            busy = bool(core.status_busy)
            raw_label = core.status_label
        if isinstance(raw_label, str):
            safe_label = "".join(ch if ch.isprintable() else " " for ch in raw_label)
            label = " ".join(safe_label.split())[:80]
    except Exception:
        pass

    lines = [f"CLI: {'busy' if busy else 'idle'}"]
    if busy and label:
        lines.append(f"Activity: {label}")

    session_id = getattr(core, "session_id", None)
    if isinstance(session_id, str) and session_id:
        safe_session = "".join(ch if ch.isprintable() else " " for ch in session_id)
        lines.append(f"Session: {' '.join(safe_session.split())[:128]}")

    waiting_for_human = False
    try:
        with core.human_ask_lock:
            waiting_for_human = bool(core.human_ask_active)
    except Exception:
        pass
    if waiting_for_human:
        lines.append("Waiting for human input: yes")

    job_manager = getattr(core, "_sub_agent_job_manager", None)
    job_owner = getattr(core, "_sub_agent_job_owner", None)
    if job_manager is not None and job_owner is not None:
        try:
            running_jobs = job_manager.running_count(owner=job_owner)
        except Exception:
            running_jobs = None
        if isinstance(running_jobs, int) and not isinstance(running_jobs, bool):
            lines.append(f"Background jobs: {max(0, running_jobs)}")

    runtime = getattr(core, "_nostr_remote_runtime", None)
    if runtime is None:
        lines.append("Nostr remote listener: stopped")
    else:
        try:
            runtime_status = runtime.status()
        except Exception:
            runtime_status = None
        if isinstance(runtime_status, dict):
            state = runtime_status.get("state")
            if not isinstance(state, str) or not state:
                state = "unknown"
            safe_state = "".join(ch if ch.isprintable() else " " for ch in state)
            lines.append(f"Nostr remote listener: {' '.join(safe_state.split())[:32]}")
            for key, heading in (
                ("pending", "Pending remote requests"),
                ("dispatching", "Requests needing reconciliation"),
                ("outbox_pending", "Pending encrypted replies"),
            ):
                count = runtime_status.get(key)
                if isinstance(count, int) and not isinstance(count, bool):
                    lines.append(f"{heading}: {max(0, count)}")
        else:
            lines.append("Nostr remote listener: status unavailable")

    return "\n".join(lines)


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
        outbox_store: SQLiteNostrOutboxStore | None = None,
        status_provider: Callable[[], str] | None = None,
        current_session_id_provider: Callable[[], str] | None = None,
    ) -> None:
        self.event_queue = event_queue
        self.private_key = private_key
        self.relays = tuple(dict.fromkeys(relays))
        self.session_id = session_id
        self.inbox_store = inbox_store
        self.pairing_store = pairing_store
        self.outbox_store = outbox_store
        self._status_provider = status_provider
        self._current_session_id_provider = current_session_id_provider or (
            lambda: self.session_id
        )
        self._status_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=32)
        self._status_recovery_needed = threading.Event()
        self._status_stop = threading.Event()
        self._status_thread: threading.Thread | None = None
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
        outbox_pending = (
            0
            if closed or self.outbox_store is None
            else self.outbox_store.pending_count()
        )
        return {
            "state": state,
            "relays": list(self.relays),
            "session_id": self.session_id,
            "error": error,
            "pending": pending,
            "dispatching": dispatching,
            "outbox_pending": outbox_pending,
        }

    def _queue_rumor(self, rumor: dict[str, Any]) -> None:
        try:
            event = create_nostr_remote_request_event(
                rumor, target_session_id=self.session_id
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
        else:
            self._queue_event(event)

    def _queue_event(self, event: dict[str, Any]) -> None:
        """Route status queries to the bounded side worker; queue other input."""
        worker = self._status_thread
        if (
            self._status_provider is not None
            and worker is not None
            and worker.is_alive()
            and is_nostr_remote_status_request(str(event.get("text") or ""))
        ):
            try:
                self._status_queue.put_nowait(event)
                return
            except queue.Full:
                # Keep the durable request out of the foreground queue: status
                # must never become ordinary chat when the side queue is busy.
                self._status_recovery_needed.set()
                return
        self.event_queue.put(event)

    def _recover_pending_status_events(self) -> None:
        """Requeue durable status requests deferred by bounded-queue pressure."""
        try:
            records = self.inbox_store.list_pending(
                limit=1000, session_id=self.session_id
            )
        except Exception:
            self._status_recovery_needed.set()
            return

        for record in records:
            if not isinstance(record.wrapped_event, dict):
                continue
            try:
                rumor = unwrap_nip17_private_message(
                    record.wrapped_event, self.private_key
                )
                event = create_nostr_remote_request_event(
                    rumor, target_session_id=record.session_id
                )
            except Exception:
                continue
            if not is_nostr_remote_status_request(event["text"]):
                continue
            try:
                self._status_queue.put_nowait(event)
            except queue.Full:
                self._status_recovery_needed.set()
                return

    def _process_status_event(self, event: dict[str, Any]) -> None:
        """Authorize, answer, and finalize a status query off the CLI turn thread."""
        try:
            current_session_id = self._current_session_id_provider()
            if not isinstance(current_session_id, str):
                current_session_id = ""
            action = self.dispatch_event(
                event,
                current_session_id=current_session_id,
            )
        except RemoteCLIRequestError as exc:
            try:
                from .runtime.logging_setup import log_event

                log_event("nostr.remote_status_rejected", reason=str(exc)[:160])
            except Exception:
                pass
            return
        except Exception as exc:
            try:
                from .runtime.logging_setup import log_event

                log_event("nostr.remote_status_failed", error_type=type(exc).__name__)
            except Exception:
                pass
            return

        if action.kind != "status":
            self.finish_event(event, "rejected")
            return
        try:
            response = self._status_provider() if self._status_provider else ""
        except Exception:
            response = "CLI status is temporarily unavailable."
        if not isinstance(response, str) or not response.strip():
            response = "CLI status is temporarily unavailable."
        try:
            finalized = self.finish_event(event, "completed")
        except Exception as exc:
            finalized = False
            finalize_error = type(exc).__name__
        else:
            finalize_error = "inbox_row_not_dispatching"
        if not finalized:
            try:
                from .runtime.logging_setup import log_event

                log_event(
                    "nostr.remote_status_finalize_failed",
                    error_type=finalize_error,
                )
            except Exception:
                pass
            return
        try:
            self.send_reply(event, response)
        except Exception as exc:
            try:
                from .runtime.logging_setup import log_event

                log_event(
                    "nostr.remote_status_reply_failed",
                    error_type=type(exc).__name__,
                )
            except Exception:
                pass

    def _status_worker(self) -> None:
        while not self._status_stop.is_set():
            try:
                event = self._status_queue.get(timeout=0.2)
            except queue.Empty:
                if self._status_recovery_needed.is_set():
                    self._status_recovery_needed.clear()
                    self._recover_pending_status_events()
                continue
            try:
                self._process_status_event(event)
            except Exception as exc:
                try:
                    from .runtime.logging_setup import log_event

                    log_event(
                        "nostr.remote_status_worker_failed",
                        error_type=type(exc).__name__,
                    )
                except Exception:
                    pass
            finally:
                self._status_queue.task_done()

    def _queue_record(self, record: InboxRecord) -> None:
        try:
            if not isinstance(record.wrapped_event, dict):
                raise ValueError("missing ciphertext")
            rumor = unwrap_nip17_private_message(record.wrapped_event, self.private_key)
            event = create_nostr_remote_request_event(
                rumor, target_session_id=record.session_id
            )
            self._queue_event(event)
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
        self._status_stop.clear()
        if self._status_provider is not None:
            self._status_thread = threading.Thread(
                target=self._status_worker,
                name="uag-nostr-status",
                daemon=True,
            )
            self._status_thread.start()
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
        if self.outbox_store is not None:
            tasks.append(
                asyncio.create_task(self._retry_outbox(), name="uag-nostr-outbox")
            )
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

    async def _deliver_outbox_record(self, record: OutboxRecord) -> dict[str, Any]:
        """Publish one claimed reply bundle and persist its delivery outcome."""
        store = self.outbox_store
        if store is None:
            return {"state": "unavailable"}
        if record.events is None or record.relay_lists_by_pubkey is None:
            store.fail(record.sender_pubkey, record.request_rumor_id, "InvalidPayload")
            return {"state": "failed", "error_type": "InvalidPayload"}
        try:
            authorized = self.pairing_store.is_authorized(record.sender_pubkey)
        except Exception:
            authorized = False
        if authorized is not True:
            store.fail(
                record.sender_pubkey, record.request_rumor_id, "AuthorizationRevoked"
            )
            return {"state": "failed", "error_type": "AuthorizationRevoked"}

        try:
            from .nostr_remote_transport import (
                fetch_nip17_relay_list,
                publish_nip17_gift_wraps,
            )

            relay_lists = dict(record.relay_lists_by_pubkey)
            recipients = {
                tag[1]
                for event in record.events
                for tag in event.get("tags", [])
                if isinstance(tag, list)
                and len(tag) >= 2
                and tag[0] == "p"
                and isinstance(tag[1], str)
            }
            missing_routes = recipients - relay_lists.keys()
            if missing_routes:
                if missing_routes != {record.sender_pubkey}:
                    store.fail(
                        record.sender_pubkey,
                        record.request_rumor_id,
                        "InvalidRelayRoutes",
                    )
                    return {"state": "failed", "error_type": "InvalidRelayRoutes"}
                remote_relays = await fetch_nip17_relay_list(
                    record.sender_pubkey,
                    self.relays,
                    allowed_relay_urls=self.relays,
                    auth_private_key=self.private_key,
                    timeout=3.0,
                )
                allowed = set(self.relays)
                recipient_relays = [
                    relay for relay in remote_relays if relay in allowed
                ]
                if not recipient_relays:
                    raise RuntimeError("NoPermittedRecipientRelay")
                relay_lists[record.sender_pubkey] = recipient_relays[:1]
                if not store.update_routes(
                    record.sender_pubkey,
                    record.request_rumor_id,
                    relay_lists,
                ):
                    return {"state": "unknown", "event_ids": list(record.event_ids)}

            deliveries = await publish_nip17_gift_wraps(
                record.events,
                relay_lists,
                self.private_key,
                allowed_relay_urls=self.relays,
                timeout=3.0,
            )
        except asyncio.CancelledError:
            # The sending lease expires after a crash or shutdown, allowing the
            # exact same signed event IDs to be retried safely on next startup.
            raise
        except Exception as exc:
            error_type = type(exc).__name__
            updated = store.retry_or_fail(
                record.sender_pubkey, record.request_rumor_id, error_type
            )
            return {
                "state": updated.status if updated is not None else "unknown",
                "error_type": error_type,
                "attempts": (
                    updated.attempts if updated is not None else record.attempts
                ),
            }

        if deliveries and all(delivery.accepted for delivery in deliveries):
            if store.mark_delivered(
                record.sender_pubkey,
                record.request_rumor_id,
                event_ids=record.event_ids,
            ):
                try:
                    from .runtime.logging_setup import log_event

                    log_event(
                        "nostr.remote_reply_delivered",
                        sender=record.sender_pubkey[:12],
                        attempts=record.attempts,
                    )
                except Exception:
                    pass
                return {
                    "state": "delivered",
                    "event_ids": list(record.event_ids),
                    "delivery_count": len(deliveries),
                }
            return {"state": "unknown", "event_ids": list(record.event_ids)}

        updated = store.retry_or_fail(
            record.sender_pubkey, record.request_rumor_id, "RelayRejected"
        )
        return {
            "state": updated.status if updated is not None else "unknown",
            "error_type": "RelayRejected",
            "attempts": updated.attempts if updated is not None else record.attempts,
        }

    async def _retry_outbox(self) -> None:
        """Retry due ciphertext-only replies until the listener is stopped."""
        stop_event = self._stop_event
        store = self.outbox_store
        if stop_event is None or store is None:
            return
        while not stop_event.is_set():
            try:
                record = store.claim_next_due()
                if record is not None:
                    await self._deliver_outbox_record(record)
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._error = f"reply outbox: {type(exc).__name__}"
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

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
            self._status_stop.set()
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
        """Durably enqueue and send a short reply to an authorized sender."""
        from .nostr_nip17 import _public_key_x, create_nip17_private_messages

        if not isinstance(request_event, dict):
            raise ValueError("remote request metadata is invalid")
        sender_value = request_event.get("sender_pubkey")
        request_id_value = request_event.get("rumor_id")
        try:
            sender = bytes.fromhex(sender_value).hex()
        except (TypeError, ValueError) as exc:
            raise ValueError("remote sender key is invalid") from exc
        try:
            request_id = bytes.fromhex(request_id_value).hex()
        except (TypeError, ValueError) as exc:
            raise ValueError("remote request rumor id is invalid") from exc
        if len(bytes.fromhex(sender)) != 32 or len(bytes.fromhex(request_id)) != 32:
            raise ValueError("remote request key or rumor id is invalid")
        if not self.pairing_store.is_authorized(sender):
            raise PermissionError("remote sender is no longer paired")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("reply text must be non-empty text")
        suffix = " [Reply truncated]"
        encoded = text.encode("utf-8")
        if len(encoded) > 16_384:
            encoded = encoded[: 16_384 - len(suffix.encode("utf-8"))]
            text = encoded.decode("utf-8", errors="ignore") + suffix

        store = self.outbox_store
        if store is None:
            raise RuntimeError("Nostr reply outbox is unavailable")
        record = store.get(sender, request_id)
        if record is None:
            if not self.relays:
                raise ValueError("no configured relay is available for the outbox")
            own_pubkey = _public_key_x(self.private_key).hex()
            events = create_nip17_private_messages(
                text, self.private_key, bytes.fromhex(sender)
            )
            relay_lists = {own_pubkey: [self.relays[0]]}
            record = store.enqueue(
                sender,
                request_id,
                events,
                relay_lists,
                allow_missing_routes=True,
            )

        if record.status == "delivered":
            return {
                "ok": True,
                "event_ids": list(record.event_ids),
                "already_delivered": True,
            }
        if record.status == "failed":
            raise RuntimeError("Nostr reply delivery previously failed")
        if record.status == "sending":
            return {"ok": True, "queued": True, "event_ids": list(record.event_ids)}

        claimed = store.claim(sender, request_id)
        if claimed is None:
            record = store.get(sender, request_id)
            if record is not None and record.status == "delivered":
                return {"ok": True, "event_ids": list(record.event_ids)}
            if record is not None and record.status in {"pending", "sending"}:
                return {
                    "ok": True,
                    "queued": True,
                    "event_ids": list(record.event_ids),
                }
            raise RuntimeError("Nostr reply could not be claimed from the outbox")

        result = asyncio.run(self._deliver_outbox_record(claimed))
        if result.get("state") == "delivered":
            return {"ok": True, "event_ids": list(result.get("event_ids") or [])}
        if result.get("state") == "pending":
            return {"ok": True, "queued": True, "event_ids": list(record.event_ids)}
        raise RuntimeError("Nostr reply could not be delivered")

    def stop(self, *, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, timeout)
        self._status_stop.set()
        loop = self._loop
        stop_event = self._stop_event
        thread = self._thread
        status_thread = self._status_thread
        if loop is not None and stop_event is not None:
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        if status_thread is not None and status_thread.is_alive():
            status_thread.join(timeout=max(0.0, deadline - time.monotonic()))
        stopped = (thread is None or not thread.is_alive()) and (
            status_thread is None or not status_thread.is_alive()
        )
        if stopped:
            with self._state_lock:
                self._state = "stopped"
                self._closed = True
            self.inbox_store.close()
            self.pairing_store.close()
            if self.outbox_store is not None:
                self.outbox_store.close()
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
    outbox_store = None
    pairing_store = None
    try:
        outbox_store = SQLiteNostrOutboxStore(db_dir / "nostr_remote_outbox.sqlite3")
        pairing_store = SQLitePairingStore(db_dir / "nostr_remote_pairings.sqlite3")
    except Exception:
        inbox_store.close()
        if outbox_store is not None:
            outbox_store.close()
        if pairing_store is not None:
            pairing_store.close()
        raise
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=private_key,
        relays=relays,
        session_id=session_id,
        inbox_store=inbox_store,
        pairing_store=pairing_store,
        outbox_store=outbox_store,
        status_provider=lambda: format_nostr_remote_status(core),
        current_session_id_provider=lambda: str(getattr(core, "session_id", "") or ""),
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
        try:
            runtime.stop(timeout=2.0)
        except Exception:
            runtime._status_stop.set()
        for name in ("_nostr_remote_runtime", "_nostr_remote_authorize_sender"):
            try:
                delattr(core, name)
            except AttributeError:
                pass
        raise
    return runtime
