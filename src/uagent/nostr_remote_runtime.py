"""Opt-in CLI bridge for the experimental NIP-17 inbox and direct replies."""

from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from typing import Any, Callable

from .nostr_nip17 import unwrap_nip17_private_message
from .nostr_remote_dispatch import (
    NOT_PAIRED_MESSAGE,
    RemoteCLIRequestError,
    RemoteCLIAction,
    authorize_nostr_remote_request,
    create_nostr_remote_request_event,
    is_nostr_remote_status_request,
)
from .nostr_remote_inbox import (
    InboxRecord,
    IsolatedIngressInboxStore,
    SQLiteNostrInboxStore,
)
from .nostr_remote_outbox import OutboxRecord, SQLiteNostrOutboxStore
from .nostr_remote_pairing import SQLitePairingStore
from .nostr_remote_transport import (
    NostrRecipientRelayListUnavailable,
    listen_nip17_messages,
)

_READBACK_TIMEOUT_SECONDS = 8.0
_READBACK_ATTEMPTS = 2
# Live progress notes for the active remote request (tool activity and
# reasoning) are best-effort side messages, separate from the durable reply
# outbox: they are capped per request and dropped rather than retried.
_PROGRESS_MAX_PER_REQUEST = 30
_PROGRESS_TEXT_LIMIT = 1200
_REASONING_FLUSH_CHARS = 600
# Upper bound for send_reply to wait while the progress sender publishes
# the request's queued notes, so the reply cannot overtake them.
_PROGRESS_DRAIN_TIMEOUT_SECONDS = 10.0


async def _read_back_wraps(
    relays: Any,
    private_key: bytes,
    recipient_event_id: str,
    sender_copy_event_id: str,
) -> list[dict[str, str]]:
    """Read both wraps of one reply back from each relay, with retries.

    A single short attempt reported ``unavailable`` for events that were in
    fact stored whenever a relay dropped the connection mid-readback, which
    AUTH-gated relays do often; a longer window plus one retry separates a
    genuine absence from a flaky readback. The result vocabulary matches
    ``read_back_nip17_gift_wrap``: found / not_returned / unavailable.
    """
    from .nostr_remote_transport import read_back_nip17_gift_wrap

    async def one_event(relay: str, event_id: str) -> str:
        result = "unavailable"
        for _attempt in range(_READBACK_ATTEMPTS):
            result = await read_back_nip17_gift_wrap(
                relay,
                event_id,
                allowed_relay_urls=relays,
                auth_private_key=private_key,
                timeout=_READBACK_TIMEOUT_SECONDS,
            )
            if result != "unavailable":
                break
        return result

    async def one_relay(relay: str) -> dict[str, str]:
        recipient, sender_copy = await asyncio.gather(
            one_event(relay, recipient_event_id),
            one_event(relay, sender_copy_event_id),
        )
        return {"relay": relay, "recipient": recipient, "sender_copy": sender_copy}

    return await asyncio.gather(*(one_relay(relay) for relay in relays))


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
    on_unpaired_sender: Callable[[str], bool] | None = None,
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

        def _authorize() -> RemoteCLIAction:
            return authorize_nostr_remote_request(
                event,
                current_session_id=current_session_id,
                authorize_sender=pairing_store.is_authorized,
            )

        try:
            action = _authorize()
        except RemoteCLIRequestError as exc:
            if on_unpaired_sender is None or str(exc) != NOT_PAIRED_MESSAGE:
                raise
            # The request verified in every other respect; only the
            # sender has no pairing. Give the local operator one
            # chance to register the device on the spot: approval
            # pairs it, so authorizing again lets this very request
            # proceed instead of being recorded as rejected.
            if not on_unpaired_sender(record.sender_pubkey):
                raise
            action = _authorize()
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
        incoming_message_display: Callable[[dict[str, Any]], None] | None = None,
        ask_state_provider: Callable[[], dict[str, Any] | None] | None = None,
        ask_answer_deliverer: Callable[[Any, str], bool] | None = None,
        pairing_asker: Callable[[str], str | None] | None = None,
    ) -> None:
        self.event_queue = event_queue
        self.private_key = private_key
        self.relays = tuple(dict.fromkeys(relays))
        self.session_id = session_id
        self.inbox_store = inbox_store
        self.pairing_store = pairing_store
        self.outbox_store = outbox_store
        self._status_provider = status_provider
        self._incoming_message_display = incoming_message_display
        self._current_session_id_provider = current_session_id_provider or (
            lambda: self.session_id
        )
        self._ask_state_provider = ask_state_provider
        self._ask_answer_deliverer = ask_answer_deliverer
        self._pairing_asker = pairing_asker
        self._pairing_declined: set[str] = set()
        self._pairing_prompt_open = False
        self._progress_lock = threading.Lock()
        self._active_request: dict[str, Any] | None = None
        self._progress_queue: queue.Queue[tuple[dict[str, Any], str]] = queue.Queue()
        self._progress_pending: dict[tuple[str, str], int] = {}
        self._question_queue: queue.Queue[tuple[dict[str, Any], str]] = queue.Queue()
        self._progress_sent = 0
        self._progress_routes: dict[str, list[str]] | None = None
        self._progress_routes_sender = ""
        self._last_tool_note = ""
        self._reasoning_parts: list[str] = []
        self._ask_forwarded_queue: Any = None
        self._ask_queued_queue: Any = None
        self._status_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=32)
        self._status_recovery_needed = threading.Event()
        self._status_stop = threading.Event()
        self._status_thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._connected_relays: set[str] = set()
        self._receive_counts = {
            "gift_wraps": 0,
            "invalid": 0,
            "decrypt_failed": 0,
            "unauthorized": 0,
            "stale": 0,
            "duplicate": 0,
            "inbox_rejected": 0,
            "queued": 0,
        }
        self._delivery_rejections: list[dict[str, str]] = []
        self._last_delivery_readback: list[dict[str, str]] = []
        self._last_unwrap_error = ""
        self._readback_threads: set[threading.Thread] = set()
        self._own_relay_list_accepted = 0
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

    def authorize_ingress_sender(self, sender_pubkey: str) -> bool:
        """Ingress gate for the relay listener: admit any verified sender.

        The NIP-17 unwrap has already authenticated the sender, so a
        first-contact request may persist in the durable inbox.
        Pairing is decided at dispatch time, not here: paired senders
        execute, and an unpaired sender is offered to the operator
        for pairing on the foreground path (and rejected on every
        other path). Dropping unknown senders at ingress would make
        that pairing prompt unreachable.
        """
        return True

    # -- Live progress and human_ask bridging for the active request --

    def _set_active_request(self, event: dict[str, Any] | None) -> None:
        with self._progress_lock:
            # Flush remaining reasoning under the outgoing request before
            # switching; queued items carry their request, so they still
            # send after the active request changes.
            self._flush_reasoning_locked()
            self._active_request = event
            self._progress_sent = 0
            self._progress_routes = None
            self._progress_routes_sender = ""
            self._last_tool_note = ""
            self._ask_forwarded_queue = None
            self._ask_queued_queue = None
            self._reasoning_parts = []

    @staticmethod
    def _progress_key(request: dict[str, Any]) -> tuple[str, str]:
        return (
            str(request.get("sender_pubkey") or ""),
            str(request.get("rumor_id") or ""),
        )

    def _enqueue_progress_locked(self, text: str) -> None:
        if self._active_request is None:
            return
        if self._progress_sent >= _PROGRESS_MAX_PER_REQUEST:
            return
        self._progress_sent += 1
        self._progress_queue.put((self._active_request, text[:_PROGRESS_TEXT_LIMIT]))
        key = self._progress_key(self._active_request)
        self._progress_pending[key] = self._progress_pending.get(key, 0) + 1

    def _note_progress_published(self, request: dict[str, Any]) -> None:
        key = self._progress_key(request)
        with self._progress_lock:
            remaining = self._progress_pending.get(key, 0) - 1
            if remaining > 0:
                self._progress_pending[key] = remaining
            else:
                self._progress_pending.pop(key, None)

    def _wait_for_progress_drain(
        self,
        request: dict[str, Any],
        *,
        timeout: float = _PROGRESS_DRAIN_TIMEOUT_SECONDS,
    ) -> None:
        """Wait briefly until the request's queued progress notes are sent.

        Progress notes travel on a side queue drained one by one by a
        background task, while the reply is delivered separately; without
        this wait the reply can overtake the final reasoning note and
        reach the requester first. Best-effort: the wait is bounded by
        ``timeout`` and skipped when the progress sender is not running,
        so the reply is never blocked indefinitely.
        """
        key = self._progress_key(request)
        with self._progress_lock:
            active = self._active_request
            if active is not None and self._progress_key(active) == key:
                self._flush_reasoning_locked()
        stop_event = self._stop_event
        if stop_event is None:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if stop_event.is_set():
                return
            with self._progress_lock:
                if self._progress_pending.get(key, 0) <= 0:
                    return
            time.sleep(0.05)

    def _flush_reasoning_locked(self) -> None:
        if not self._reasoning_parts:
            return
        text = "".join(self._reasoning_parts).strip()
        self._reasoning_parts = []
        if text:
            self._enqueue_progress_locked("💭 " + text)

    def note_tool_action(self, name: str, text: str) -> None:
        """Forward one tool-start sentence to the active remote requester.

        ``text`` is the tool's localized action sentence (the same text
        the local [TOOL] trace shows), produced by the shared describer
        machinery in tools/__init__.
        """
        if not name or not text:
            return
        with self._progress_lock:
            if self._active_request is None or name == self._last_tool_note:
                return
            self._last_tool_note = name
            self._flush_reasoning_locked()
            self._enqueue_progress_locked("🔧 " + text)

    def note_reasoning(self, text: str) -> None:
        """Buffer streamed reasoning for the active remote requester."""
        if not isinstance(text, str) or not text:
            return
        # Background sub-agent jobs share the providers; their reasoning is
        # not part of the foreground remote turn (same rule as set_status).
        try:
            from .runtime.sub_agent_jobs import current_sub_agent_job_mode

            if current_sub_agent_job_mode() == "background":
                return
        except Exception:
            pass
        with self._progress_lock:
            if self._active_request is None:
                return
            self._reasoning_parts.append(text)
            if (
                sum(len(part) for part in self._reasoning_parts)
                >= _REASONING_FLUSH_CHARS
            ):
                self._flush_reasoning_locked()

    def _ask_snapshot(self) -> dict[str, Any] | None:
        if self._ask_state_provider is None:
            return None
        try:
            snapshot = self._ask_state_provider()
        except Exception:
            return None
        return snapshot if isinstance(snapshot, dict) else None

    def _progress_authorized(self, sender: str) -> bool:
        """Re-check pairing at send time, like send_reply and outbox delivery.

        A requester unpaired mid-turn must stop receiving progress,
        reasoning, and forwarded questions immediately.
        """
        try:
            return self.pairing_store.is_authorized(sender) is True
        except Exception:
            return False

    async def _progress_routes_for(self, sender: str) -> dict[str, list[str]] | None:
        """Recipient routes for progress DMs, cached per sender."""
        from .nostr_nip17 import _public_key_x
        from .nostr_remote_transport import fetch_nip17_relay_list

        with self._progress_lock:
            if self._progress_routes_sender == sender:
                return self._progress_routes
        try:
            remote_relays = await fetch_nip17_relay_list(
                sender,
                self.relays,
                allowed_relay_urls=self.relays,
                auth_private_key=self.private_key,
                timeout=3.0,
            )
        except Exception:
            return None
        allowed = set(self.relays)
        recipient_relays = [relay for relay in remote_relays if relay in allowed]
        if not recipient_relays:
            return None
        routes = {
            sender: recipient_relays,
            _public_key_x(self.private_key).hex(): [self.relays[0]],
        }
        with self._progress_lock:
            self._progress_routes = routes
            self._progress_routes_sender = sender
        return routes

    @staticmethod
    def _recipient_accepted(deliveries: Any, event: Any) -> bool:
        """True when a relay accepted the given (recipient) gift wrap."""
        try:
            event_id = event.get("id")
            return any(
                getattr(delivery, "accepted", False)
                and getattr(delivery, "event_id", None) == event_id
                for delivery in deliveries or []
            )
        except Exception:
            return False

    async def _publish_progress_text(self, request: dict[str, Any], text: str) -> bool:
        """Best-effort publish of one progress DM; never raises.

        Returns True only when a recipient relay accepted the wrap:
        publish_nip17_gift_wraps reports rejections in its results
        instead of raising, so a non-throwing call is not delivery.
        """
        from .nostr_nip17 import create_nip17_private_messages
        from .nostr_remote_transport import publish_nip17_gift_wraps

        sender = request.get("sender_pubkey")
        if not isinstance(sender, str) or not self._progress_authorized(sender):
            return False
        routes = await self._progress_routes_for(sender)
        if routes is None:
            return False
        try:
            events = create_nip17_private_messages(
                text, self.private_key, bytes.fromhex(sender)
            )
            deliveries = await publish_nip17_gift_wraps(
                events,
                routes,
                self.private_key,
                allowed_relay_urls=self.relays,
                timeout=3.0,
            )
        except Exception:
            return False
        return self._recipient_accepted(deliveries, events[0])

    async def _publish_question_text(
        self,
        request: dict[str, Any],
        text: str,
        ask_queue: Any,
    ) -> None:
        """Publish a forwarded human_ask question; never raises.

        The recipient wrap goes first and answer routing arms as soon as
        a recipient relay accepts it; the sender copy (the publisher's
        sequential second half) must not widen the window in which a
        fast answer would be mistaken for a new request.
        """
        from .nostr_nip17 import _public_key_x, create_nip17_private_messages
        from .nostr_remote_transport import publish_nip17_gift_wraps

        # Revalidate before publishing: the ask may have been answered
        # locally, timed out, or its turn may have ended while this
        # question waited behind another note in the sender.
        with self._progress_lock:
            still_active = self._active_request is request
        snapshot = self._ask_snapshot()
        if (
            not still_active
            or not snapshot
            or not snapshot.get("active")
            or snapshot.get("queue") is not ask_queue
        ):
            self._note_question_result(ask_queue, False)
            return

        sender = request.get("sender_pubkey")
        delivered = False
        events: list[dict[str, Any]] = []
        routes: dict[str, list[str]] | None = None
        if isinstance(sender, str) and self._progress_authorized(sender):
            routes = await self._progress_routes_for(sender)
        if routes is not None and isinstance(sender, str):
            try:
                events = create_nip17_private_messages(
                    text, self.private_key, bytes.fromhex(sender)
                )
                deliveries = await publish_nip17_gift_wraps(
                    [events[0]],
                    {sender: routes[sender]},
                    self.private_key,
                    allowed_relay_urls=self.relays,
                    timeout=3.0,
                )
                delivered = self._recipient_accepted(deliveries, events[0])
            except Exception:
                delivered = False
        self._note_question_result(ask_queue, delivered)
        if delivered and routes is not None and len(events) > 1:
            own = _public_key_x(self.private_key).hex()
            try:
                await publish_nip17_gift_wraps(
                    [events[1]],
                    {own: routes[own]},
                    self.private_key,
                    allowed_relay_urls=self.relays,
                    timeout=3.0,
                )
            except Exception:
                pass

    def _note_question_result(self, ask_queue: Any, delivered: bool) -> None:
        """Record whether a forwarded human_ask question actually went out.

        Answer routing arms only on delivery; on failure the queued mark is
        cleared so the watcher offers the question again instead of leaving
        the ask silently unanswered.
        """
        with self._progress_lock:
            if self._ask_queued_queue is ask_queue:
                self._ask_queued_queue = None
            if delivered:
                self._ask_forwarded_queue = ask_queue

    async def _progress_sender(self) -> None:
        """Drain queued progress notes and forwarded questions until stop."""
        stop_event = self._stop_event
        if stop_event is None:
            return
        while not stop_event.is_set():
            question: tuple[dict[str, Any], str, Any] | None = None
            item: tuple[dict[str, Any], str] | None = None
            try:
                question = self._question_queue.get_nowait()
            except queue.Empty:
                try:
                    item = self._progress_queue.get_nowait()
                except queue.Empty:
                    item = None
            if question is None and item is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
                continue
            if question is not None:
                await self._publish_question_text(question[0], question[1], question[2])
            else:
                assert item is not None
                try:
                    await self._publish_progress_text(item[0], item[1])
                except Exception:
                    pass
                finally:
                    self._note_progress_published(item[0])

    def _forward_pending_ask_once(self) -> None:
        """Queue one pending human_ask question for the active requester."""
        with self._progress_lock:
            if self._pairing_prompt_open:
                # The open question is the local pairing prompt; it
                # must never be forwarded to a remote requester.
                return
            active = self._active_request
            forwarded = self._ask_forwarded_queue
            queued = self._ask_queued_queue
        if active is None:
            return
        snapshot = self._ask_snapshot()
        if not snapshot or not snapshot.get("active"):
            return
        if snapshot.get("is_password"):
            return
        message = str(snapshot.get("message") or "").strip()
        ask_queue = snapshot.get("queue")
        if not message or ask_queue is None:
            return
        if ask_queue is forwarded or ask_queue is queued:
            return
        with self._progress_lock:
            self._flush_reasoning_locked()
            self._ask_queued_queue = ask_queue
        self._question_queue.put(
            (active, "❓ " + message[:_PROGRESS_TEXT_LIMIT], ask_queue)
        )

    async def _ask_watcher(self) -> None:
        """Forward a pending human_ask question to the active requester."""
        stop_event = self._stop_event
        if stop_event is None:
            return
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.4)
            except asyncio.TimeoutError:
                pass
            if stop_event.is_set():
                return
            self._forward_pending_ask_once()

    def _try_deliver_ask_answer(self, rumor: dict[str, Any]) -> bool:
        """Route a DM from the active requester into a forwarded human_ask.

        Returns True when the rumor was consumed as the ask's answer: its
        durable inbox row is claimed and finished without a foreground turn.
        """
        with self._progress_lock:
            active = self._active_request
            forwarded = self._ask_forwarded_queue
        if active is None or forwarded is None:
            return False
        if rumor.get("pubkey") != active.get("sender_pubkey"):
            return False
        snapshot = self._ask_snapshot()
        if not snapshot or not snapshot.get("active"):
            return False
        if snapshot.get("is_password"):
            return False
        if snapshot.get("queue") is not forwarded:
            return False
        text = rumor.get("content")
        if not isinstance(text, str):
            return False
        # Control texts (/uag status, /uag cmd ...) are never answers:
        # they keep their normal routing even while an ask is pending.
        lowered = text.strip().lower()
        if lowered == "/uag" or lowered.startswith(("/uag ", "/uag\t", "/uag\n")):
            return False
        sender = rumor.get("pubkey")
        rumor_id = rumor.get("id")
        if not isinstance(sender, str) or not isinstance(rumor_id, str):
            return False
        # A device revoked after the question was forwarded must not
        # resume the turn by answering it. Ingress is permissive for
        # first contact, so recheck pairing before consuming a DM as
        # an ask answer; an unauthorized DM keeps its normal routing
        # (and is rejected, or offered for pairing, at dispatch).
        try:
            if not self.pairing_store.is_authorized(sender):
                return False
        except Exception:
            return False
        try:
            record = self.inbox_store.claim(
                sender, rumor_id, session_id=self.session_id
            )
            if record is None:
                return False
            if not self.inbox_store.finish(sender, rumor_id, "completed"):
                return False
        except Exception:
            return False
        # Deliver last, atomically against the host's ask state: if the ask
        # was already answered locally, the deliverer reports False and this
        # DM is dropped as a late duplicate answer rather than being put
        # into a queue nobody reads anymore.
        if self._ask_answer_deliverer is not None:
            try:
                self._ask_answer_deliverer(forwarded, text)
            except Exception:
                pass
        else:
            snapshot = self._ask_snapshot()
            if (
                snapshot
                and snapshot.get("active")
                and snapshot.get("queue") is forwarded
            ):
                forwarded.put(text)
        with self._progress_lock:
            self._ask_forwarded_queue = None
        return True

    def _record_receive_diagnostic(self, relay: str, event: str) -> None:
        """Count receive outcomes without retaining message data or identities."""
        with self._state_lock:
            if event.startswith("unwrap_error:"):
                self._last_unwrap_error = event[len("unwrap_error:") :][:120]
            elif event == "connected":
                self._connected_relays.add(relay)
            elif event == "disconnected":
                self._connected_relays.discard(relay)
            elif event in self._receive_counts:
                self._receive_counts[event] += 1

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            state = self._state
            error = self._error
            closed = self._closed
            diagnostics = {
                "connected_relays": len(self._connected_relays),
                **self._receive_counts,
                "delivery_rejections": [
                    dict(item) for item in self._delivery_rejections
                ],
                "delivery_readback": [
                    dict(item) for item in self._last_delivery_readback
                ],
                "last_unwrap_error": self._last_unwrap_error,
                "own_relay_list_accepted": self._own_relay_list_accepted,
            }
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
        outbox_summary = (
            None
            if closed or self.outbox_store is None
            else self.outbox_store.status_summary()
        )
        outbox_pending = (
            0
            if outbox_summary is None
            else outbox_summary["pending"] + outbox_summary["sending"]
        )
        return {
            "state": state,
            "relays": list(self.relays),
            "session_id": self.session_id,
            "error": error,
            "diagnostics": diagnostics,
            "pending": pending,
            "dispatching": dispatching,
            "outbox_pending": outbox_pending,
            "outbox_summary": outbox_summary,
        }

    def _queue_rumor(self, rumor: dict[str, Any]) -> None:
        if self._try_deliver_ask_answer(rumor):
            return
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
            # Only well-formed, authenticated requests are echoed. Reject
            # malformed commands without printing attacker-controlled content.
            if self._incoming_message_display is not None:
                try:
                    self._incoming_message_display(rumor)
                except Exception:
                    pass

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
                    authorize_sender=self.authorize_ingress_sender,
                    inbox_store=self.inbox_store,
                    target_session_id=self.session_id,
                    stop_event=stop_event,
                    diagnostic_callback=lambda event: self._record_receive_diagnostic(
                        relay, event
                    ),
                )
                if stop_event.is_set():
                    return
                raise RuntimeError("Nostr listener stopped unexpectedly")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._state_lock:
                    self._connected_relays.discard(relay)
                    self._error = f"{relay}: {type(exc).__name__}: {str(exc)[:200]}"
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=retry_delay)
                except asyncio.TimeoutError:
                    pass
                retry_delay = min(retry_delay * 2, 30.0)

    async def _publish_own_relay_list(self) -> None:
        """Publish this node's signed kind-10050 list to its configured relays.

        Strict NIP-17 clients refuse to compose a DM to an identity with no
        published inbox relay list, so the list is announced on listener
        start. Publication is best-effort: a relay that refuses or times out
        must not stop the listener, so failures only lower the accepted
        count kept in the status diagnostics.
        """
        from .nostr_nip17 import create_nip17_relay_list_event
        from .nostr_remote_transport import publish_relay_list_event

        try:
            event = create_nip17_relay_list_event(list(self.relays), self.private_key)
        except Exception:
            return
        accepted = 0
        for relay in self.relays:
            try:
                delivery = await publish_relay_list_event(
                    relay,
                    event,
                    self.private_key,
                    allowed_relay_urls=[relay],
                )
            except Exception:
                continue
            if getattr(delivery, "accepted", False):
                accepted += 1
        with self._state_lock:
            self._own_relay_list_accepted = accepted
        try:
            from .runtime.logging_setup import log_event

            log_event(
                "nostr.remote_relay_list_published",
                accepted=accepted,
                relays=len(self.relays),
            )
        except Exception:
            pass

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
        tasks.append(
            asyncio.create_task(self._progress_sender(), name="uag-nostr-progress")
        )
        tasks.append(asyncio.create_task(self._ask_watcher(), name="uag-nostr-ask"))
        # Not part of the FIRST_COMPLETED wait set: this one-shot task is
        # expected to finish while the listeners keep running.
        publish_task = asyncio.create_task(
            self._publish_own_relay_list(), name="uag-nostr-relay-list"
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
            for task in [*tasks, stop_task, publish_task]:
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                *tasks, stop_task, publish_task, return_exceptions=True
            )

    def _note_delivery_rejections(self, deliveries: list[Any]) -> None:
        """Remember which relays refused the latest reply, with their reasons.

        Relay messages are remote-controlled text, so they are stored with
        non-printable characters replaced, whitespace-normalized and
        bounded, for status display and the structured log only.
        """
        noted: list[dict[str, str]] = []
        for delivery in deliveries:
            if getattr(delivery, "accepted", False):
                continue
            relay = " ".join(
                "".join(
                    char if char.isprintable() else " "
                    for char in str(getattr(delivery, "relay_url", "") or "")
                ).split()
            )[:128]
            message = " ".join(
                "".join(
                    char if char.isprintable() else " "
                    for char in str(getattr(delivery, "message", "") or "")
                ).split()
            )[:200]
            noted.append({"relay": relay, "message": message})
            if len(noted) >= 4:
                break
        with self._state_lock:
            self._delivery_rejections = noted
        if noted:
            try:
                from .runtime.logging_setup import log_event

                for item in noted:
                    log_event(
                        "nostr.remote_reply_relay_rejected",
                        relay=item["relay"],
                        message=item["message"],
                    )
            except Exception:
                pass

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
                    raise ValueError("NoPermittedRecipientRelay")
                # The recipient may read from any published DM inbox relay.
                # Send the same signed gift wrap to every locally permitted
                # kind-10050 relay instead of relying on the first one.
                relay_lists[record.sender_pubkey] = recipient_relays
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
            # Stable public-safe error types allow troubleshooting without
            # exposing relay notices, message bodies or participant identities.
            error_type = (
                "RecipientRelayListUnavailable"
                if isinstance(exc, NostrRecipientRelayListUnavailable)
                else (
                    "NoPermittedRecipientRelay"
                    if isinstance(exc, ValueError)
                    and str(exc) == "NoPermittedRecipientRelay"
                    else type(exc).__name__
                )
            )
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

        self._note_delivery_rejections(deliveries)
        accepted_event_ids = {
            delivery.event_id for delivery in deliveries if delivery.accepted
        }
        recipient_event_ids = {
            str(event.get("id"))
            for event in record.events
            if isinstance(event, dict)
            and any(
                isinstance(tag, list)
                and len(tag) >= 2
                and tag[0] == "p"
                and tag[1] == record.sender_pubkey
                for tag in event.get("tags") or []
            )
        }
        # Delivered means the addressee's gift wrap was accepted by at least
        # one of their inbox relays. One refusing relay in the recipient's
        # signed list must not block the reply when another accepted it; the
        # sender-copy wrap is attempted but does not gate delivery.
        if (
            deliveries
            and recipient_event_ids
            and recipient_event_ids <= accepted_event_ids
        ):
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
                self._schedule_delivery_readback(
                    deliveries, record, recipient_event_ids
                )
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

    async def _record_delivery_readback(
        self,
        deliveries: list[Any],
        record: OutboxRecord,
        recipient_event_ids: set[str],
    ) -> None:
        """Read the just-delivered wraps back from the accepting relays.

        A relay OK does not prove the event was retained or can be served
        again, which is how a reply can be "delivered" yet never appear in
        the recipient's client. Probing automatically keeps the evidence in
        the status diagnostics without a manual verify run; the probe never
        fails the delivery. Only relays that accepted a wrap are probed.
        """
        event_ids = [str(event_id) for event_id in record.event_ids]
        if len(event_ids) != 2 or len(recipient_event_ids) != 1:
            return
        recipient_event_id = next(iter(recipient_event_ids))
        sender_copy_event_id = next(
            event_id for event_id in event_ids if event_id != recipient_event_id
        )
        accepting_relays = [
            relay
            for relay in dict.fromkeys(
                str(getattr(delivery, "relay_url", "") or "")
                for delivery in deliveries
                if getattr(delivery, "accepted", False)
            )
            if relay
        ]
        if not accepting_relays:
            return
        try:
            readback = await _read_back_wraps(
                accepting_relays,
                self.private_key,
                recipient_event_id,
                sender_copy_event_id,
            )
        except Exception:
            return
        with self._state_lock:
            self._last_delivery_readback = readback
        try:
            from .runtime.logging_setup import log_event

            log_event(
                "nostr.remote_reply_readback",
                recipient_found=sum(
                    1 for item in readback if item["recipient"] == "found"
                ),
                sender_copy_found=sum(
                    1 for item in readback if item["sender_copy"] == "found"
                ),
                relays=len(readback),
            )
        except Exception:
            pass

    def _schedule_delivery_readback(
        self,
        deliveries: list[Any],
        record: OutboxRecord,
        recipient_event_ids: set[str],
    ) -> None:
        # The probe is diagnostics only: run it on its own thread so a slow
        # or timing-out relay never stalls the reply path (send_reply runs
        # delivery synchronously on the foreground loop) or outbox retries.
        thread = threading.Thread(
            target=self._run_delivery_readback,
            args=(deliveries, record, recipient_event_ids),
            name="nostr-delivery-readback",
            daemon=True,
        )
        with self._state_lock:
            self._readback_threads.add(thread)
        thread.start()

    def _run_delivery_readback(
        self,
        deliveries: list[Any],
        record: OutboxRecord,
        recipient_event_ids: set[str],
    ) -> None:
        try:
            asyncio.run(
                self._record_delivery_readback(deliveries, record, recipient_event_ids)
            )
        except Exception:
            pass
        finally:
            with self._state_lock:
                self._readback_threads.discard(threading.current_thread())

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

    def _offer_pairing(self, sender_pubkey: str) -> bool:
        """Ask the local operator whether to pair an unknown sender.

        Runs on the foreground dispatch thread while the request is
        claimed. Approval pairs the device, so the caller can
        authorize the same request again and let it proceed. An
        explicit refusal is remembered for the rest of the session so
        a sender cannot keep re-triggering the prompt; no answer at
        all (cancel, timeout, prompt unavailable) is not a refusal
        and may be asked again on a later message.
        """
        if self._pairing_asker is None:
            return False
        with self._progress_lock:
            if sender_pubkey in self._pairing_declined:
                return False
            if self._pairing_prompt_open:
                return False
            self._pairing_prompt_open = True
        try:
            try:
                from .tools.nostr_transport import encode_npub

                npub = encode_npub(sender_pubkey)
            except Exception:
                npub = sender_pubkey
            try:
                answer = self._pairing_asker(npub)
            except Exception:
                return False
        finally:
            with self._progress_lock:
                self._pairing_prompt_open = False
        if answer is None:
            return False
        # Ctrl+C at the prompt reaches the asker as the ask channel's
        # "cancel" sentinel; that is no answer, not a refusal, so the
        # sender may be asked about again on a later message.
        if answer.strip().lower() == "cancel":
            return False
        if answer.strip().lower() in {"yes", "y", "はい"}:
            try:
                self.pairing_store.pair(sender_pubkey, "", approved=True)
            except Exception:
                return False
            return True
        with self._progress_lock:
            self._pairing_declined.add(sender_pubkey)
        return False

    def dispatch_event(
        self,
        event: dict[str, Any],
        *,
        current_session_id: str,
        allow_pairing_prompt: bool = False,
    ) -> RemoteCLIAction:
        action = dispatch_nostr_remote_inbox_event(
            event,
            inbox_store=self.inbox_store,
            pairing_store=self.pairing_store,
            private_key=self.private_key,
            current_session_id=current_session_id,
            on_unpaired_sender=(self._offer_pairing if allow_pairing_prompt else None),
        )
        # Status queries are also dispatched (by the side worker, possibly
        # while a turn is running); they must never take over the active
        # request that progress notes and human_ask forwarding belong to.
        if action.kind != "status":
            self._set_active_request(event)
        return action

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
        finished = self.inbox_store.finish(sender, rumor_id, outcome)
        with self._progress_lock:
            active = self._active_request
        if (
            active is not None
            and active.get("sender_pubkey") == sender
            and active.get("rumor_id") == rumor_id
        ):
            self._set_active_request(None)
        return finished

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

        # Queued progress notes for this request (tool activity and the
        # final reasoning flush) must reach the requester before the
        # reply; give the progress sender a bounded chance to drain them.
        self._wait_for_progress_drain(request_event)

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

    def verify_latest_reply(self) -> dict[str, Any]:
        """Read back both wraps of the latest delivered reply without plaintext."""
        if self._closed or self.outbox_store is None:
            return {"state": "unavailable"}
        record = self.outbox_store.latest_delivered()
        if record is None:
            return {"state": "no_delivered_reply"}
        if len(record.event_ids) != 2:
            return {"state": "invalid_event_ids"}

        return {
            "state": "complete",
            "event_ids": list(record.event_ids),
            "relays": asyncio.run(
                _read_back_wraps(
                    self.relays,
                    self.private_key,
                    record.event_ids[0],
                    record.event_ids[1],
                )
            ),
        }

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


def _display_nostr_incoming(core: Any, rumor: dict[str, Any]) -> None:
    """Render a bounded one-line preview via the shared display channel.

    Rendered synchronously with the caller's core object (the runtime's
    contract); the insertion logic itself lives in
    runtime/display_channel.py alongside the other notice surfaces.
    """
    sender = rumor.get("pubkey")
    content = rumor.get("content")
    if not isinstance(sender, str) or not isinstance(content, str):
        return
    preview = " ".join(
        "".join(char if char.isprintable() else " " for char in content).split()
    )
    if len(preview) > 2_000:
        preview = preview[:2_000] + "…"
    text = f"[NOSTR] Received from {sender[:12]}: {preview}"
    try:
        from .runtime.display_channel import Notice, render_notice

        render_notice(core, Notice(text=text, source="nostr"))
    except Exception:
        pass


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
    first_contact_store = SQLiteNostrInboxStore(
        db_dir / "nostr_remote_first_contact.sqlite3",
        max_pending=100,
        max_records=1_000,
        max_total_payload_bytes=8 * 1024 * 1024,
    )
    outbox_store = None
    pairing_store = None
    try:
        outbox_store = SQLiteNostrOutboxStore(db_dir / "nostr_remote_outbox.sqlite3")
        pairing_store = SQLitePairingStore(db_dir / "nostr_remote_pairings.sqlite3")
    except Exception:
        inbox_store.close()
        first_contact_store.close()
        if outbox_store is not None:
            outbox_store.close()
        if pairing_store is not None:
            pairing_store.close()
        raise
    # First-contact requests persist in their own small store so
    # unauthorized traffic cannot exhaust the paired inbox budget.
    inbox_store = IsolatedIngressInboxStore(
        inbox_store, first_contact_store, pairing_store.is_authorized
    )

    def _ask_state_snapshot() -> dict[str, Any] | None:
        lock = getattr(core, "human_ask_lock", None)
        if lock is None:
            return None
        try:
            with lock:
                return {
                    "active": bool(getattr(core, "human_ask_active", False)),
                    "is_password": bool(getattr(core, "human_ask_is_password", False)),
                    "message": str(getattr(core, "human_ask_message", "") or ""),
                    "queue": getattr(core, "human_ask_queue", None),
                }
        except Exception:
            return None

    def _deliver_ask_answer(expected_queue: Any, text: str) -> bool:
        lock = getattr(core, "human_ask_lock", None)
        if lock is None:
            return False
        try:
            with lock:
                if not bool(getattr(core, "human_ask_active", False)):
                    return False
                if bool(getattr(core, "human_ask_is_password", False)):
                    return False
                if getattr(core, "human_ask_queue", None) is not expected_queue:
                    return False
                expected_queue.put(text)
                return True
        except Exception:
            return False

    def _ask_pairing(npub: str) -> str | None:
        """Ask the local operator about pairing, via the CLI ask channel.

        Uses a private reply queue (like the session passphrase
        prompt), so no Nostr DM can be routed in as the answer: the
        remote answer path only delivers to the queue it forwarded,
        which is never this one. Returns the typed answer, or None
        when the prompt was cancelled, timed out, or unavailable.
        """
        lock = getattr(core, "human_ask_lock", None)
        if lock is None:
            return None
        from .i18n import _

        question = _(
            "A Nostr DM arrived from an unregistered device (%(npub)s). "
            "Register this device and process the message? "
            "Answer yes or no.",
            npub=npub,
        )
        reply_queue: queue.Queue = queue.Queue(maxsize=1)
        with lock:
            if getattr(core, "human_ask_active", False):
                return None
            core.human_ask_queue = reply_queue
            core.human_ask_active = True
            core.human_ask_is_password = False
            core.human_ask_multiline_active = False
            core.human_ask_message = question
            core.human_ask_prompt = "[PAIRING] > "
            lines = getattr(core, "human_ask_lines", None)
            if lines is not None:
                lines.clear()
        try:
            print(question, flush=True)
            try:
                timeout = float(os.environ.get("UAGENT_HUMAN_ASK_TIMEOUT_SEC", "300"))
            except (TypeError, ValueError):
                timeout = 300.0
            if timeout <= 0:
                timeout = 300.0
            try:
                value = reply_queue.get(timeout=timeout)
            except queue.Empty:
                return None
            return None if value is None else str(value)
        finally:
            cleaned_up = False
            with lock:
                if getattr(core, "human_ask_queue", None) is reply_queue:
                    core.human_ask_active = False
                    core.human_ask_is_password = False
                    core.human_ask_multiline_active = False
                    core.human_ask_message = ""
                    core.human_ask_prompt = ""
                    core.human_ask_queue = None
                    cleaned_up = True
            if cleaned_up:
                # The reply path marks the CLI busy ("replying")
                # before delivering the answer, and a following turn
                # normally clears it. A pairing answer often leads
                # to no turn (refusal or another rejection), so
                # restore the idle status here; otherwise stdin
                # stays blocked on the busy flag.
                try:
                    if getattr(core, "status_busy", False) and str(
                        getattr(core, "status_label", "")
                    ).startswith("replying"):
                        core.set_status(False)
                except Exception:
                    pass

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
        incoming_message_display=lambda rumor: _display_nostr_incoming(core, rumor),
        ask_state_provider=_ask_state_snapshot,
        ask_answer_deliverer=_deliver_ask_answer,
        pairing_asker=_ask_pairing,
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
