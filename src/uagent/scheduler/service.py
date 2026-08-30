from __future__ import annotations

import threading
from typing import Any, Optional

from .models import (
    SCHEDULE_TYPE_PERIODIC,
    SCHEDULE_TYPE_ONCE,
    ScheduleItem,
    advance_periodic_at,
    utc_now,
)
from .store import SchedulerStore
from .run_store import SchedulerRunStore

_RUNTIME_LOCK = threading.RLock()
_RUNTIME: Optional["SchedulerService"] = None


class SchedulerService:
    def __init__(
        self,
        event_sink: Any,
        *,
        store: SchedulerStore | None = None,
        run_store: SchedulerRunStore | None = None,
        poll_interval_s: float = 0.5,
    ) -> None:
        self._sink = event_sink
        self._store = store or SchedulerStore()
        self._run_store = run_store or SchedulerRunStore()
        self._poll_interval_s = max(0.1, float(poll_interval_s or 0.5))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

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

    def snapshot(self) -> list[ScheduleItem]:
        return self._store.list_items()

    def add_item(self, item: ScheduleItem) -> ScheduleItem:
        return self._store.add_item(item)

    def delete_item(self, schedule_id: str) -> bool:
        return self._store.delete_item(schedule_id)

    def _emit(self, payload: dict[str, Any]) -> None:
        try:
            self._sink.put(payload)
        except Exception:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._fire_due_items()
            except Exception:
                pass
            self._stop.wait(self._poll_interval_s)

    def _fire_due_items(self) -> None:
        now = utc_now()
        items = self._store.list_items()
        kept: list[ScheduleItem] = []
        changed = False
        due: list[tuple[ScheduleItem, str]] = []

        for item in items:
            if not item.enabled:
                kept.append(item)
                continue
            try:
                if item.next_fire_at <= now:
                    due.append((item, item.at))
                    if item.type == SCHEDULE_TYPE_PERIODIC and item.interval_sec > 0:
                        item.at = advance_periodic_at(
                            item.at, item.interval_sec, now=now
                        )
                        item.touch()
                        kept.append(item)
                        changed = True
                    elif item.type == SCHEDULE_TYPE_ONCE:
                        changed = True
                    else:
                        changed = True
                else:
                    kept.append(item)
            except Exception:
                changed = True

        if changed:
            try:
                self._store.save_items(kept)
            except Exception:
                pass

        for item, due_at in due:
            notice = (item.message or "").strip()
            prompt = item.effective_prompt
            try:
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
                    },
                )
                run_id = run.run_id
            except Exception:
                run_id = ""
                # The due item was already removed/advanced above. Restore its
                # due timestamp so a transient run-store failure does not drop
                # the scheduled execution permanently.
                try:
                    item.at = due_at
                    item.touch()
                    self._store.add_item(item)
                except Exception:
                    pass
                continue
            base = {
                "schedule_id": item.id,
                "schedule_type": item.type,
                "schedule_at": due_at,
                "run_id": run_id,
            }
            if notice:
                self._emit({"kind": "schedule_notice", "text": notice, **base})
            if item.execution_mode == "direct":
                self._emit({"kind": "scheduled_direct", **base})
            elif prompt:
                self._emit({"kind": "user", "text": prompt, **base})


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
