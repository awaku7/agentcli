from __future__ import annotations

import json
import os
import threading
import tempfile
from pathlib import Path
from typing import Any, Optional

from ..utils.paths import get_schedules_json_path
from .models import ScheduleItem

_LOCK = threading.RLock()


class SchedulerStore:
    def __init__(self, json_path: str | Path | None = None) -> None:
        self.path = Path(json_path or get_schedules_json_path())

    def _read_doc(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "items": []}
        try:
            text = self.path.read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception:
            return {"version": 1, "items": []}
        if isinstance(data, list):
            return {"version": 1, "items": data}
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                out = dict(data)
                out["version"] = int(out.get("version") or 1)
                out["items"] = items
                return out
        return {"version": 1, "items": []}

    def _write_doc(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_name, self.path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)
            except Exception:
                pass

    def list_items(self) -> list[ScheduleItem]:
        with _LOCK:
            doc = self._read_doc()
            out: list[ScheduleItem] = []
            for raw in doc.get("items") or []:
                if not isinstance(raw, dict):
                    continue
                try:
                    out.append(ScheduleItem.from_dict(raw))
                except Exception:
                    continue
            out.sort(key=lambda item: (item.next_fire_at, item.created_at, item.id))
            return out

    def save_items(self, items: list[ScheduleItem]) -> None:
        with _LOCK:
            doc = {
                "version": 1,
                "items": [item.normalized().as_dict() for item in items],
            }
            self._write_doc(doc)

    def add_item(self, item: ScheduleItem) -> ScheduleItem:
        with _LOCK:
            items = self.list_items()
            normalized = item.normalized().touch()
            items = [existing for existing in items if existing.id != normalized.id]
            items.append(normalized)
            self.save_items(items)
            return normalized

    def delete_item(self, schedule_id: str) -> bool:
        schedule_id = str(schedule_id or "").strip()
        if not schedule_id:
            return False
        with _LOCK:
            items = self.list_items()
            new_items = [item for item in items if item.id != schedule_id]
            if len(new_items) == len(items):
                return False
            self.save_items(new_items)
            return True

    def get_item(self, schedule_id: str) -> Optional[ScheduleItem]:
        schedule_id = str(schedule_id or "").strip()
        if not schedule_id:
            return None
        with _LOCK:
            for item in self.list_items():
                if item.id == schedule_id:
                    return item
        return None

    def set_items(self, items: list[ScheduleItem]) -> None:
        self.save_items(items)
