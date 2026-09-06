"""Structured, provider-neutral state for long-running agent tasks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AgentState:
    """Serializable progress state independent of conversation history."""

    goal: str = ""
    completed_steps: tuple[str, ...] = ()
    current_step: str = ""
    files: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    next_action: str = ""
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("completed_steps", "files", "errors"):
            data[key] = list(data[key])
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "AgentState":
        value = value if isinstance(value, dict) else {}
        return cls(
            goal=str(value.get("goal") or ""),
            completed_steps=tuple(
                str(item) for item in value.get("completed_steps", []) if item
            ),
            current_step=str(value.get("current_step") or ""),
            files=tuple(str(item) for item in value.get("files", []) if item),
            errors=tuple(str(item) for item in value.get("errors", []) if item),
            next_action=str(value.get("next_action") or ""),
            updated_at=str(value.get("updated_at") or _utc_now()),
        )


class AgentStateManager:
    """Small immutable-update facade for structured agent progress."""

    def __init__(self, state: AgentState | None = None) -> None:
        self.state = state or AgentState()

    def update(self, **changes: Any) -> AgentState:
        allowed = {
            "goal",
            "completed_steps",
            "current_step",
            "files",
            "errors",
            "next_action",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unknown agent state fields: {sorted(unknown)}")
        normalized = dict(changes)
        for key in ("completed_steps", "files", "errors"):
            if key in normalized:
                normalized[key] = tuple(str(item) for item in normalized[key] if item)
        normalized["updated_at"] = _utc_now()
        self.state = replace(self.state, **normalized)
        return self.state

    def mark_step_complete(self, step: str, *, next_action: str = "") -> AgentState:
        step = str(step or "").strip()
        if not step:
            raise ValueError("step is empty")
        completed = list(self.state.completed_steps)
        if step not in completed:
            completed.append(step)
        return self.update(
            completed_steps=completed,
            current_step="",
            next_action=next_action,
        )

    def add_error(self, error: str) -> AgentState:
        error = str(error or "").strip()
        if not error:
            return self.state
        return self.update(errors=[*self.state.errors, error])

    def add_file(self, path: str) -> AgentState:
        path = str(path or "").strip()
        if not path or path in self.state.files:
            return self.state
        return self.update(files=[*self.state.files, path])


__all__ = ["AgentState", "AgentStateManager"]
