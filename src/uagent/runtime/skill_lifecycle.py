from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.paths import get_state_dir

_LOCK = threading.RLock()

SKILL_STATES = {"draft", "reviewed", "enabled", "improved", "deprecated"}
_ALLOWED = {
    "draft": {"reviewed"},
    "reviewed": {"enabled"},
    "enabled": {"improved", "deprecated"},
    "improved": {"enabled", "deprecated"},
    "deprecated": set(),
}


@dataclass
class SkillRecord:
    name: str
    state: str = "draft"
    version: str = ""
    validation_ok: bool = False
    security_review_ok: bool = False
    usage_count: int = 0
    last_used_at: float | None = None
    deprecated_reason: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "version": self.version,
            "validation_ok": self.validation_ok,
            "security_review_ok": self.security_review_ok,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at,
            "deprecated_reason": self.deprecated_reason,
            "history": self.history,
        }


class SkillLifecycleError(RuntimeError):
    pass


class SkillLifecycleManager:
    """Persisted, explicit lifecycle and approval state for installed skills."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or (get_state_dir() / "skill_lifecycle.json"))

    def _read(self) -> dict[str, SkillRecord]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            entries = raw.get("skills", {}) if isinstance(raw, dict) else {}
            return {
                name: SkillRecord(**value)
                for name, value in entries.items()
                if isinstance(name, str) and isinstance(value, dict)
            }
        except Exception as exc:
            raise SkillLifecycleError(f"could not read lifecycle store: {exc}") from exc

    def _write(self, records: dict[str, SkillRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(
                {
                    "version": 1,
                    "skills": {name: rec.as_dict() for name, rec in records.items()},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        fd, temp = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.remove(temp)

    def register(self, name: str, *, version: str = "") -> SkillRecord:
        name = str(name or "").strip()
        if not name:
            raise SkillLifecycleError("skill name is required")
        with _LOCK:
            records = self._read()
            record = records.setdefault(
                name, SkillRecord(name=name, version=str(version or ""))
            )
            if version:
                record.version = str(version)
            self._write(records)
            return record

    def get(self, name: str) -> SkillRecord:
        with _LOCK:
            record = self._read().get(str(name or "").strip())
            if record is None:
                raise SkillLifecycleError(f"unknown skill: {name}")
            return record

    def review(
        self, name: str, *, validation_ok: bool, security_review_ok: bool
    ) -> SkillRecord:
        with _LOCK:
            records = self._read()
            record = records.get(str(name or "").strip())
            if record is None:
                raise SkillLifecycleError(f"unknown skill: {name}")
            if record.state != "draft":
                raise SkillLifecycleError(
                    f"skill is not in draft state: {record.state}"
                )
            if not validation_ok or not security_review_ok:
                raise SkillLifecycleError(
                    "skill validation and security review are required"
                )
            record.validation_ok = True
            record.security_review_ok = True
            self._transition(record, "reviewed", "review")
            self._write(records)
            return record

    def enable(self, name: str, *, confirmed: bool = False) -> SkillRecord:
        with _LOCK:
            records = self._read()
            record = records.get(str(name or "").strip())
            if record is None:
                raise SkillLifecycleError(f"unknown skill: {name}")
            if not confirmed:
                raise SkillLifecycleError("explicit confirmation is required")
            if not record.validation_ok or not record.security_review_ok:
                raise SkillLifecycleError(
                    "skill validation and security review are required"
                )
            self._transition(record, "enabled", "enable")
            self._write(records)
            return record

    def record_use(self, name: str) -> SkillRecord:
        with _LOCK:
            records = self._read()
            record = records.get(str(name or "").strip())
            if record is None:
                raise SkillLifecycleError(f"unknown skill: {name}")
            if record.state not in {"enabled", "improved"}:
                raise SkillLifecycleError(f"skill is not enabled: {record.state}")
            record.usage_count += 1
            record.last_used_at = time.time()
            self._write(records)
            return record

    def deprecate(
        self, name: str, *, reason: str, confirmed: bool = False
    ) -> SkillRecord:
        with _LOCK:
            records = self._read()
            record = records.get(str(name or "").strip())
            if record is None:
                raise SkillLifecycleError(f"unknown skill: {name}")
            if not confirmed:
                raise SkillLifecycleError("explicit confirmation is required")
            record.deprecated_reason = str(reason or "").strip()
            self._transition(record, "deprecated", "deprecate")
            self._write(records)
            return record

    @staticmethod
    def _transition(record: SkillRecord, target: str, action: str) -> None:
        if target not in SKILL_STATES or target not in _ALLOWED.get(
            record.state, set()
        ):
            raise SkillLifecycleError(
                f"invalid skill transition: {record.state} -> {target}"
            )
        record.history.append(
            {"from": record.state, "to": target, "action": action, "ts": time.time()}
        )
        record.state = target


__all__ = [
    "SKILL_STATES",
    "SkillLifecycleError",
    "SkillLifecycleManager",
    "SkillRecord",
]
