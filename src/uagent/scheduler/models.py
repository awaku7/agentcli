from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

SCHEDULE_TYPE_ONCE = "once"
SCHEDULE_TYPE_PERIODIC = "periodic"
VALID_SCHEDULE_TYPES = {SCHEDULE_TYPE_ONCE, SCHEDULE_TYPE_PERIODIC}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _local_tz():
    return datetime.now().astimezone().tzinfo or timezone.utc


def parse_iso_datetime(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty datetime")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_local_tz())
    return dt.astimezone(timezone.utc)


def format_iso_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass
class ScheduleItem:
    id: str
    type: str
    at: str
    message: str = ""
    llm_prompt: str = ""
    interval_sec: int = 0
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleItem":
        raw = dict(data or {})
        item = cls(
            id=str(raw.get("id") or "").strip() or str(uuid4()),
            type=str(raw.get("type") or SCHEDULE_TYPE_ONCE).strip().lower(),
            at=str(raw.get("at") or "").strip(),
            message=str(raw.get("message") or ""),
            llm_prompt=str(raw.get("llm_prompt") or raw.get("on_timeout_prompt") or ""),
            interval_sec=_coerce_int(raw.get("interval_sec"), 0),
            enabled=bool(raw.get("enabled", True)),
            created_at=str(raw.get("created_at") or "").strip(),
            updated_at=str(raw.get("updated_at") or "").strip(),
        )
        return item.normalized()

    def normalized(self) -> "ScheduleItem":
        if self.type not in VALID_SCHEDULE_TYPES:
            self.type = SCHEDULE_TYPE_ONCE
        if not self.at:
            self.at = format_iso_datetime(utc_now())
        else:
            self.at = format_iso_datetime(parse_iso_datetime(self.at))
        self.message = str(self.message or "")
        self.llm_prompt = str(self.llm_prompt or "")
        self.interval_sec = max(0, _coerce_int(self.interval_sec, 0))
        self.enabled = bool(self.enabled)
        now = format_iso_datetime(utc_now())
        if not self.created_at:
            self.created_at = now
        else:
            try:
                self.created_at = format_iso_datetime(
                    parse_iso_datetime(self.created_at)
                )
            except Exception:
                self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        else:
            try:
                self.updated_at = format_iso_datetime(
                    parse_iso_datetime(self.updated_at)
                )
            except Exception:
                self.updated_at = now
        return self

    def touch(self) -> "ScheduleItem":
        self.updated_at = format_iso_datetime(utc_now())
        return self

    @property
    def next_fire_at(self) -> datetime:
        return parse_iso_datetime(self.at)

    @property
    def effective_prompt(self) -> str:
        return (self.llm_prompt or self.message or "").strip()

    def due(self, now: datetime | None = None) -> bool:
        try:
            now_dt = now or utc_now()
            return self.enabled and self.next_fire_at <= now_dt
        except Exception:
            return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "at": self.at,
            "message": self.message,
            "llm_prompt": self.llm_prompt,
            "interval_sec": self.interval_sec,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def advance_periodic_at(at: str, interval_sec: int, now: datetime | None = None) -> str:
    interval = max(1, int(interval_sec))
    current = parse_iso_datetime(at)
    now_dt = now or utc_now()
    step = timedelta(seconds=interval)
    while current <= now_dt:
        current += step
    return format_iso_datetime(current)
