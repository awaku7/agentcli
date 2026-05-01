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

_RUNTIME_LOCK = threading.RLock()
_RUNTIME: Optional["SchedulerService"] = None


class SchedulerService:
    def __init__(
        self,
        event_sink: Any,
        *,
        store: SchedulerStore | None = None,
        poll_interval_s: float = 0.5,
    ) -> None:
        self._sink = event_sink
        self._store = store or SchedulerStore()
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
        due: list[ScheduleItem] = []

        for item in items:
            if not item.enabled:
                kept.append(item)
                continue
            try:
                if item.next_fire_at <= now:
                    due.append(item)
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

        for item in due:
            notice = (item.message or "").strip()
            prompt = item.effective_prompt
            base = {
                "schedule_id": item.id,
                "schedule_type": item.type,
                "schedule_at": item.at,
            }
            if notice:
                self._emit({"kind": "schedule_notice", "text": notice, **base})
            if prompt:
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
