from __future__ import annotations

import threading
from typing import Any, Optional

from .models import (
    SCHEDULE_TYPE_PERIODIC,
    ScheduleItem,
    advance_periodic_at,
    format_iso_datetime,
    utc_now,
)
from .store import SchedulerStore
from .run_store import SchedulerRunStore
from .identity import scheduler_instance_id

_RUNTIME_LOCK = threading.RLock()
_RUNTIME: Optional["SchedulerService"] = None
_DISPATCH_EVENT_ID = "_uag_scheduler_event_id"
_DISPATCH_EVENT_OWNER = "_uag_scheduler_event_owner"
_DISPATCH_LEASE_SECONDS = 300.0


class SchedulerService:
    def __init__(
        self,
        event_sink: Any,
        *,
        store: SchedulerStore | None = None,
        run_store: SchedulerRunStore | None = None,
        poll_interval_s: float = 0.5,
        instance_id: str | None = None,
    ) -> None:
        self._sink = event_sink
        self._instance_id = str(instance_id or scheduler_instance_id()).strip()
        self._store = store or SchedulerStore()
        self._run_store = run_store or SchedulerRunStore()
        self._poll_interval_s = max(0.1, float(poll_interval_s or 0.5))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sink_get_original = None
        self._sink_get_wrapper = None
        self._ack_on_dequeue = False
        self._queued_event_ids: set[int] = set()
        self._queued_event_lock = threading.Lock()
        self._install_sink_ack_hook()

    def _install_sink_ack_hook(self) -> None:
        getter = getattr(self._sink, "get", None)
        if not callable(getter):
            return

        def _get_with_scheduler_ack(*args, **kwargs):
            event = getter(*args, **kwargs)
            self._ack_dequeued_event(event)
            return event

        try:
            setattr(self._sink, "get", _get_with_scheduler_ack)
        except Exception:
            return
        self._sink_get_original = getter
        self._sink_get_wrapper = _get_with_scheduler_ack
        self._ack_on_dequeue = True

    def _restore_sink_ack_hook(self) -> None:
        wrapper = self._sink_get_wrapper
        original = self._sink_get_original
        if wrapper is None or original is None:
            return
        try:
            if getattr(self._sink, "get", None) is wrapper:
                setattr(self._sink, "get", original)
        except Exception:
            pass
        self._sink_get_original = None
        self._sink_get_wrapper = None
        self._ack_on_dequeue = False

    def _ack_dequeued_event(self, event: Any) -> None:
        if not isinstance(event, dict):
            return
        event_id = event.pop(_DISPATCH_EVENT_ID, None)
        owner = str(event.pop(_DISPATCH_EVENT_OWNER, "") or "").strip()
        if event_id is None or not owner:
            return
        with self._queued_event_lock:
            try:
                self._store.mark_event_delivered(int(event_id), owner)
            except Exception:
                pass
            self._queued_event_ids.discard(int(event_id))

    def is_running(self) -> bool:
        return bool(
            self._thread and self._thread.is_alive() and not self._stop.is_set()
        )

    def start(self) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._restore_sink_ack_hook()

    def snapshot(self) -> list[ScheduleItem]:
        return self._store.list_items()

    def add_item(self, item: ScheduleItem) -> ScheduleItem:
        return self._store.add_item(item)

    def delete_item(self, schedule_id: str) -> bool:
        return self._store.delete_item(schedule_id)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._fire_due_items()
            except Exception:
                pass
            self._stop.wait(self._poll_interval_s)

    def _dispatch_pending_events(self) -> None:
        # A live queue may hold events beyond the normal claim lease. Renew
        # those claims before looking for events eligible for dispatch again.
        with self._queued_event_lock:
            for event_id in tuple(self._queued_event_ids):
                if not self._store.renew_event_lease(
                    event_id,
                    self._instance_id,
                    utc_now(),
                    lease_seconds=_DISPATCH_LEASE_SECONDS,
                ):
                    self._queued_event_ids.discard(event_id)

        # Claim and deliver one event at a time so a failure on an earlier
        # notice cannot let a later execution event overtake it.
        for _ in range(100):
            claimed = self._store.claim_pending_events(
                self._instance_id,
                utc_now(),
                lease_seconds=_DISPATCH_LEASE_SECONDS,
                limit=1,
            )
            if not claimed:
                return
            event_id, payload = claimed[0]
            delivery = dict(payload)
            if self._ack_on_dequeue:
                delivery[_DISPATCH_EVENT_ID] = event_id
                delivery[_DISPATCH_EVENT_OWNER] = self._instance_id
            try:
                if self._ack_on_dequeue:
                    with self._queued_event_lock:
                        self._queued_event_ids.add(event_id)
                        self._sink.put(delivery)
                else:
                    self._sink.put(delivery)
            except Exception as exc:
                with self._queued_event_lock:
                    self._queued_event_ids.discard(event_id)
                try:
                    self._store.release_event(
                        event_id,
                        self._instance_id,
                        error=str(exc),
                        retry_delay=self._poll_interval_s,
                    )
                except Exception:
                    pass
                return

            if self._ack_on_dequeue:
                # The event remains leased until queue.get() acknowledges it.
                # A process crash before dequeue therefore leaves durable state
                # that can be explicitly reclaimed and re-dispatched.
                continue

            # Generic sinks that expose put() but not get() cannot provide a
            # dequeue acknowledgement. Preserve compatibility by treating
            # successful sink acceptance as the delivery boundary.
            try:
                if not self._store.mark_event_delivered(event_id, self._instance_id):
                    return
            except Exception:
                return

    def _fire_due_items(self) -> None:
        # Retry previously persisted events before creating new work. This
        # recovers transient sink failures and scheduler-thread restarts within
        # the same process owner.
        self._dispatch_pending_events()

        now = utc_now()
        self._store.reclaim_expired_claims(now)
        due = self._store.claim_due_items(self._instance_id, now)
        for item, due_at in due:
            next_at: str | None = None
            if item.type == SCHEDULE_TYPE_PERIODIC and item.interval_sec > 0:
                next_at = format_iso_datetime(
                    advance_periodic_at(item.at, item.interval_sec, now=now)
                )
            try:
                event_owner = item.owner_instance_id or self._instance_id
                run = self._run_store.create(
                    item.id,
                    idempotency_key=f"{item.id}:{due_at}",
                    metadata={
                        "schedule_type": item.type,
                        "message": item.message,
                        "llm_prompt": item.llm_prompt,
                        "retry_limit": item.retry_limit,
                        "retry_backoff_sec": item.retry_backoff_sec,
                        "timeout_sec": item.timeout_sec,
                        "required_tools": list(item.required_tools),
                        "execution_mode": item.execution_mode,
                        "target_tool": item.target_tool,
                        "target_args": dict(item.target_args),
                        "owner_instance_id": event_owner,
                        "session_id": item.session_id,
                    },
                )

                base = {
                    "schedule_id": item.id,
                    "schedule_type": item.type,
                    "schedule_at": due_at,
                    "run_id": run.run_id,
                    "owner_instance_id": event_owner,
                    "session_id": item.session_id,
                }
                events: list[dict[str, Any]] = []
                notice = (item.message or "").strip()
                prompt = item.effective_prompt
                if notice:
                    events.append({"kind": "schedule_notice", "text": notice, **base})
                if item.execution_mode == "direct":
                    events.append({"kind": "scheduled_direct", **base})
                elif prompt:
                    events.append({"kind": "user", "text": prompt, **base})

                finalized = self._store.finalize_claim_with_events(
                    item.id,
                    self._instance_id,
                    next_at,
                    events,
                )
                if not finalized:
                    raise RuntimeError("scheduler claim was lost before finalization")
            except Exception:
                self._store.release_claim(item.id, self._instance_id, restore_at=due_at)
                continue

        # New outbox rows are dispatched only after their schedule transition
        # committed successfully.
        self._dispatch_pending_events()


def start_background_scheduler(
    event_sink: Any,
    *,
    store: SchedulerStore | None = None,
    poll_interval_s: float = 0.5,
) -> SchedulerService:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is not None and _RUNTIME.is_running():
            return _RUNTIME
        _RUNTIME = SchedulerService(
            event_sink,
            store=store,
            poll_interval_s=poll_interval_s,
        )
        _RUNTIME.start()
        return _RUNTIME


def stop_background_scheduler() -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        runtime = _RUNTIME
        _RUNTIME = None
    if runtime is not None:
        try:
            runtime.stop()
        except Exception:
            pass


def is_background_scheduler_running() -> bool:
    with _RUNTIME_LOCK:
        return bool(_RUNTIME is not None and _RUNTIME.is_running())
