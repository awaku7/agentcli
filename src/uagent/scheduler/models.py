from __future__ import annotations

from dataclasses import dataclass, field
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
    retry_limit: int = 0
    retry_backoff_sec: int = 0
    timeout_sec: int = 0
    required_tools: list[str] = field(default_factory=list)
    execution_mode: str = "llm"
    target_tool: str = ""
    target_args: dict[str, Any] = field(default_factory=dict)
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
            retry_limit=_coerce_int(raw.get("retry_limit"), 0),
            retry_backoff_sec=_coerce_int(raw.get("retry_backoff_sec"), 0),
            timeout_sec=_coerce_int(raw.get("timeout_sec"), 0),
            required_tools=raw.get("required_tools") or [],
            execution_mode=str(raw.get("execution_mode") or "llm").strip().lower(),
            target_tool=str(raw.get("target_tool") or "").strip(),
            target_args=raw.get("target_args") or {},
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
        self.retry_limit = max(0, _coerce_int(self.retry_limit, 0))
        self.retry_backoff_sec = max(0, _coerce_int(self.retry_backoff_sec, 0))
        self.timeout_sec = max(0, _coerce_int(self.timeout_sec, 0))
        if isinstance(self.required_tools, str):
            self.required_tools = [self.required_tools]
        if not isinstance(self.required_tools, (list, tuple, set, frozenset)):
            self.required_tools = []
        self.required_tools = list(
            dict.fromkeys(
                str(name or "").strip()
                for name in self.required_tools
                if str(name or "").strip()
            )
        )
        self.execution_mode = str(self.execution_mode or "llm").strip().lower()
        if self.execution_mode not in {"llm", "direct"}:
            self.execution_mode = "llm"
        self.target_tool = str(self.target_tool or "").strip()
        if not isinstance(self.target_args, dict):
            self.target_args = {}
        if self.execution_mode == "direct" and not self.target_tool:
            raise ValueError("direct schedule requires target_tool")
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
            "retry_limit": self.retry_limit,
            "retry_backoff_sec": self.retry_backoff_sec,
            "timeout_sec": self.timeout_sec,
            "required_tools": list(self.required_tools),
            "execution_mode": self.execution_mode,
            "target_tool": self.target_tool,
            "target_args": dict(self.target_args),
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
